"""Download queue: jobs, their states, the concurrency limit, retry and cancel.

The queue is thread-safe. Callbacks run on the thread that caused the change (often a
process reader thread), so GUI code must marshal them to its own thread.
"""

import itertools
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from easy_ytdlp.core import progress
from easy_ytdlp.core.runner import ProcessRunner

LOG_LIMIT = 5000


class JobState(StrEnum):
    WAITING = "waiting"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def finished(self) -> bool:
        return self in {JobState.DONE, JobState.FAILED, JobState.CANCELLED}

    @property
    def active(self) -> bool:
        return self in {JobState.DOWNLOADING, JobState.PROCESSING}


@dataclass
class Job:
    id: int
    argv: list[str]
    title: str
    url: str = ""
    # Serialized DownloadOptions (None for command-mode jobs); stored in history.
    options: dict[str, Any] | None = None
    output_dir: str = ""
    thumbnail: str | None = None
    state: JobState = JobState.WAITING
    # Overall progress from 0 to 1, or None while unknown.
    progress: float | None = None
    speed: float | None = None
    eta: int | None = None
    item_title: str = ""
    item_index: int | None = None
    item_count: int | None = None
    postprocessor: str = ""
    files: list[str] = field(default_factory=list)
    log: deque[str] = field(default_factory=lambda: deque(maxlen=LOG_LIMIT))
    error: str = ""
    returncode: int | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def snapshot(self) -> "Job":
        """A copy that is safe to read from another thread."""
        copy = Job(**{k: v for k, v in self.__dict__.items() if k not in {"files", "log"}})
        copy.files = list(self.files)
        copy.log = deque(self.log, maxlen=LOG_LIMIT)
        return copy


class Runner(Protocol):
    def start(self) -> None: ...
    def cancel(self) -> None: ...


type RunnerFactory = Callable[[list[str], Callable[[str], None], Callable[[int], None]], Runner]


def _default_runner(
    argv: list[str], on_line: Callable[[str], None], on_exit: Callable[[int], None]
) -> Runner:
    return ProcessRunner(argv, on_line, on_exit)


class DownloadQueue:
    def __init__(
        self,
        max_concurrent: int = 2,
        *,
        runner_factory: RunnerFactory = _default_runner,
        on_change: Callable[[Job], None] | None = None,
        on_log: Callable[[Job, str], None] | None = None,
        on_finished: Callable[[Job], None] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[int, Job] = {}
        self._runners: dict[int, Runner] = {}
        self._ids = itertools.count(1)
        self._max = max(1, max_concurrent)
        self._paused = False
        self._runner_factory = runner_factory
        self.on_change = on_change
        self.on_log = on_log
        self.on_finished = on_finished

    # -- public API ---------------------------------------------------------------------

    def add(
        self,
        argv: Sequence[str],
        title: str,
        *,
        url: str = "",
        options: dict[str, Any] | None = None,
        output_dir: str = "",
        thumbnail: str | None = None,
    ) -> Job:
        with self._lock:
            job = Job(
                id=next(self._ids),
                argv=list(argv),
                title=title,
                url=url,
                options=options,
                output_dir=output_dir,
                thumbnail=thumbnail,
            )
            self._jobs[job.id] = job
        self._notify(job)
        self._schedule()
        return job

    def jobs(self) -> list[Job]:
        with self._lock:
            return [job.snapshot() for job in self._jobs.values()]

    def get(self, job_id: int) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot() if job else None

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(1 for job in self._jobs.values() if job.state.active)

    @property
    def pending_count(self) -> int:
        """Jobs that are waiting or running."""
        with self._lock:
            return sum(1 for job in self._jobs.values() if not job.state.finished)

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def max_concurrent(self) -> int:
        return self._max

    def set_max_concurrent(self, value: int) -> None:
        with self._lock:
            self._max = max(1, value)
        self._schedule()

    def pause(self) -> None:
        """Stop starting new jobs; running jobs continue."""
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._paused = False
        self._schedule()

    def cancel(self, job_id: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state.finished:
                return
            runner = self._runners.get(job_id)
            if runner is None:
                self._finish(job, JobState.CANCELLED)
            else:
                # The exit callback records the end time once the process is gone.
                job.state = JobState.CANCELLED
        if runner is not None:
            runner.cancel()
            self._notify(job)
        else:
            self._notify(job)
            self._emit_finished(job)
            self._schedule()

    def cancel_all(self) -> None:
        with self._lock:
            ids = [job.id for job in self._jobs.values() if not job.state.finished]
        for job_id in ids:
            self.cancel(job_id)

    def retry(self, job_id: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state not in {JobState.FAILED, JobState.CANCELLED}:
                return
            self._reset(job)
        self._notify(job)
        self._schedule()

    def remove(self, job_id: int) -> bool:
        """Forget a finished job. Running or waiting jobs must be cancelled first."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or not job.state.finished:
                return False
            del self._jobs[job_id]
            return True

    def clear_finished(self) -> list[int]:
        with self._lock:
            removed = [job_id for job_id, job in self._jobs.items() if job.state.finished]
            for job_id in removed:
                del self._jobs[job_id]
            return removed

    def wait_idle(self, timeout: float = 30.0) -> bool:
        """Block until no job is waiting or running (for tests and shutdown)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.pending_count == 0:
                return True
            time.sleep(0.02)
        return False

    # -- internals ----------------------------------------------------------------------

    def _reset(self, job: Job) -> None:
        job.state = JobState.WAITING
        job.progress = None
        job.speed = None
        job.eta = None
        job.postprocessor = ""
        job.error = ""
        job.returncode = None
        job.finished_at = None
        job.files.clear()

    def _schedule(self) -> None:
        to_start: list[Job] = []
        with self._lock:
            if self._paused:
                return
            running = sum(1 for job in self._jobs.values() if job.state.active)
            for job in self._jobs.values():
                if running >= self._max:
                    break
                if job.state == JobState.WAITING:
                    job.state = JobState.DOWNLOADING
                    running += 1
                    to_start.append(job)
        for job in to_start:
            self._start(job)

    def _start(self, job: Job) -> None:
        runner = self._runner_factory(
            job.argv,
            lambda line, job=job: self._handle_line(job, line),
            lambda code, job=job: self._handle_exit(job, code),
        )
        with self._lock:
            self._runners[job.id] = runner
        self._notify(job)
        try:
            runner.start()
        except OSError as exc:
            with self._lock:
                self._runners.pop(job.id, None)
                job.error = str(exc)
                self._finish(job, JobState.FAILED)
            self._notify(job)
            self._emit_finished(job)
            self._schedule()

    def _handle_line(self, job: Job, line: str) -> None:
        event = progress.parse_line(line)
        with self._lock:
            job.log.append(line)
            changed = False if job.state == JobState.CANCELLED else self._apply(job, event)
        if self.on_log is not None:
            self.on_log(job, line)
        if changed:
            self._notify(job)

    def _apply(self, job: Job, event: progress.Event) -> bool:
        match event:
            case progress.DownloadProgress():
                job.state = JobState.DOWNLOADING
                job.speed = event.speed
                job.eta = event.eta
                self._set_item(job, event.item)
                fraction = event.fraction
                if fraction is not None:
                    job.progress = self._overall(job, fraction)
                return True
            case progress.PostProcess(status="started"):
                if event.postprocessor != "MoveFiles":
                    job.state = JobState.PROCESSING
                    job.postprocessor = event.postprocessor
                    job.speed = None
                    job.eta = None
                return True
            case progress.FileFinished():
                job.files.append(event.path)
                return True
            case progress.ErrorLine():
                job.error = event.message
                return True
        return False

    @staticmethod
    def _set_item(job: Job, item: progress.ItemInfo) -> None:
        if item.title:
            job.item_title = item.title
        job.item_index = item.index
        job.item_count = item.count

    @staticmethod
    def _overall(job: Job, fraction: float) -> float:
        if job.item_index and job.item_count and job.item_count > 1:
            return min((job.item_index - 1 + fraction) / job.item_count, 1.0)
        return fraction

    def _handle_exit(self, job: Job, code: int) -> None:
        with self._lock:
            self._runners.pop(job.id, None)
            job.returncode = code
            if job.state == JobState.CANCELLED:
                state = JobState.CANCELLED
            elif code == 0:
                state = JobState.DONE
            else:
                state = JobState.FAILED
                if not job.error:
                    job.error = f"yt-dlp exited with code {code}"
            self._finish(job, state)
        self._notify(job)
        self._emit_finished(job)
        self._schedule()

    @staticmethod
    def _finish(job: Job, state: JobState) -> None:
        job.state = state
        job.finished_at = time.time()
        job.speed = None
        job.eta = None
        if state == JobState.DONE:
            job.progress = 1.0

    def _notify(self, job: Job) -> None:
        if self.on_change is not None:
            self.on_change(self.get(job.id) or job.snapshot())

    def _emit_finished(self, job: Job) -> None:
        if self.on_finished is not None:
            self.on_finished(self.get(job.id) or job.snapshot())
