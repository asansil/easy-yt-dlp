import sys
from collections.abc import Callable

import pytest

from easy_ytdlp.core import progress
from easy_ytdlp.core.queue import DownloadQueue, Job, JobState


class FakeRunner:
    def __init__(
        self, argv: list[str], on_line: Callable[[str], None], on_exit: Callable[[int], None]
    ) -> None:
        self.argv = argv
        self.on_line = on_line
        self.on_exit = on_exit
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True
        self.on_exit(1)


class Harness:
    def __init__(self, max_concurrent: int = 2) -> None:
        self.runners: list[FakeRunner] = []
        self.changes: list[Job] = []
        self.finished: list[Job] = []
        self.logs: list[str] = []
        self.queue = DownloadQueue(
            max_concurrent,
            runner_factory=self.factory,
            on_change=self.changes.append,
            on_log=lambda job, line: self.logs.append(line),
            on_finished=self.finished.append,
        )

    def factory(self, argv, on_line, on_exit) -> FakeRunner:
        runner = FakeRunner(argv, on_line, on_exit)
        self.runners.append(runner)
        return runner

    def state(self, job: Job) -> JobState:
        current = self.queue.get(job.id)
        assert current is not None
        return current.state


def progress_line(done: int, total: int, index: int | None = None, count: int | None = None) -> str:
    info = (
        f'{{"title": "T", "playlist_autonumber": {index or "null"},'
        f' "n_entries": {count or "null"}}}'
    )
    return (
        progress.DOWNLOAD_PREFIX
        + f'{{"status": "downloading", "downloaded_bytes": {done}, "total_bytes": {total},'
        f' "speed": 100.0, "eta": 3}} {info}'
    )


def test_concurrency_limit_and_scheduling() -> None:
    h = Harness(max_concurrent=2)
    jobs = [h.queue.add(["yt-dlp", str(i)], f"job {i}") for i in range(3)]
    assert [h.state(j) for j in jobs] == [
        JobState.DOWNLOADING,
        JobState.DOWNLOADING,
        JobState.WAITING,
    ]
    assert len(h.runners) == 2
    h.runners[0].on_exit(0)
    assert h.state(jobs[0]) == JobState.DONE
    assert h.state(jobs[2]) == JobState.DOWNLOADING
    assert h.runners[2].argv == ["yt-dlp", "2"]
    assert h.queue.active_count == 2
    assert h.queue.pending_count == 2


def test_progress_processing_files_and_done() -> None:
    h = Harness()
    job = h.queue.add(["x"], "video")
    runner = h.runners[0]
    runner.on_line(progress_line(50, 200))
    current = h.queue.get(job.id)
    assert current.progress == 0.25
    assert current.speed == 100.0
    assert current.eta == 3
    assert current.item_title == "T"
    runner.on_line(
        progress.POSTPROCESS_PREFIX + '{"status": "started", "postprocessor": "Merger"} {}'
    )
    current = h.queue.get(job.id)
    assert current.state == JobState.PROCESSING
    assert current.postprocessor == "Merger"
    assert current.speed is None
    runner.on_line(progress.FILE_PREFIX + '"C:\\\\out\\\\v.mkv"')
    runner.on_line("[Merger] some log")
    runner.on_exit(0)
    current = h.queue.get(job.id)
    assert current.state == JobState.DONE
    assert current.progress == 1.0
    assert current.files == ["C:\\out\\v.mkv"]
    assert current.finished_at is not None
    assert list(current.log)[-1] == "[Merger] some log"
    assert h.logs[-1] == "[Merger] some log"
    assert [j.state for j in h.finished] == [JobState.DONE]


def test_move_files_does_not_switch_to_processing() -> None:
    h = Harness()
    job = h.queue.add(["x"], "video")
    h.runners[0].on_line(
        progress.POSTPROCESS_PREFIX + '{"status": "started", "postprocessor": "MoveFiles"} {}'
    )
    assert h.state(job) == JobState.DOWNLOADING


def test_playlist_overall_progress() -> None:
    h = Harness()
    job = h.queue.add(["x"], "list")
    h.runners[0].on_line(progress_line(50, 100, index=2, count=4))
    current = h.queue.get(job.id)
    assert current.progress == pytest.approx(0.375)
    assert (current.item_index, current.item_count) == (2, 4)


def test_failure_keeps_error_message() -> None:
    h = Harness()
    job = h.queue.add(["x"], "bad")
    h.runners[0].on_line("ERROR: [youtube] x: Video unavailable")
    h.runners[0].on_exit(1)
    current = h.queue.get(job.id)
    assert current.state == JobState.FAILED
    assert current.error == "[youtube] x: Video unavailable"
    assert current.returncode == 1


def test_failure_without_error_line() -> None:
    h = Harness()
    job = h.queue.add(["x"], "bad")
    h.runners[0].on_exit(2)
    assert h.queue.get(job.id).error == "yt-dlp exited with code 2"


def test_cancel_running_and_waiting_jobs() -> None:
    h = Harness(max_concurrent=1)
    running = h.queue.add(["x"], "a")
    waiting = h.queue.add(["y"], "b")
    h.queue.cancel(waiting.id)
    assert h.state(waiting) == JobState.CANCELLED
    assert len(h.runners) == 1
    h.queue.cancel(running.id)
    assert h.runners[0].cancelled
    assert h.state(running) == JobState.CANCELLED
    assert h.queue.pending_count == 0


def test_lines_after_cancel_do_not_change_state() -> None:
    h = Harness()
    job = h.queue.add(["x"], "a")
    runner = h.runners[0]
    runner.cancel = lambda: None  # the process is still dying
    h.queue.cancel(job.id)
    runner.on_line(progress_line(10, 100))
    assert h.state(job) == JobState.CANCELLED
    runner.on_exit(1)
    assert h.state(job) == JobState.CANCELLED


def test_retry_restarts_failed_job() -> None:
    h = Harness()
    job = h.queue.add(["x"], "a")
    h.runners[0].on_line(progress_line(10, 100))
    h.runners[0].on_exit(1)
    h.queue.retry(job.id)
    current = h.queue.get(job.id)
    assert current.state == JobState.DOWNLOADING
    assert current.progress is None
    assert current.error == ""
    assert len(h.runners) == 2


def test_retry_ignores_running_or_done_jobs() -> None:
    h = Harness()
    job = h.queue.add(["x"], "a")
    h.queue.retry(job.id)
    h.runners[0].on_exit(0)
    h.queue.retry(job.id)
    assert len(h.runners) == 1


def test_pause_and_resume() -> None:
    h = Harness(max_concurrent=1)
    h.queue.pause()
    job = h.queue.add(["x"], "a")
    assert h.state(job) == JobState.WAITING
    assert h.queue.paused
    h.queue.resume()
    assert h.state(job) == JobState.DOWNLOADING


def test_raise_concurrency_starts_waiting_jobs() -> None:
    h = Harness(max_concurrent=1)
    jobs = [h.queue.add(["x"], str(i)) for i in range(3)]
    h.queue.set_max_concurrent(3)
    assert all(h.state(j) == JobState.DOWNLOADING for j in jobs)
    h.queue.set_max_concurrent(0)
    assert h.queue.max_concurrent == 1


def test_remove_and_clear_finished() -> None:
    h = Harness()
    a = h.queue.add(["x"], "a")
    b = h.queue.add(["y"], "b")
    assert not h.queue.remove(a.id)
    h.runners[0].on_exit(0)
    assert h.queue.remove(a.id)
    h.runners[1].on_exit(1)
    assert h.queue.clear_finished() == [b.id]
    assert h.queue.jobs() == []


def test_start_failure_marks_job_failed() -> None:
    class Broken(FakeRunner):
        def start(self) -> None:
            raise FileNotFoundError("yt-dlp.exe not found")

    queue = DownloadQueue(runner_factory=Broken)
    job = queue.add(["x"], "a")
    current = queue.get(job.id)
    assert current.state == JobState.FAILED
    assert "not found" in current.error


def test_snapshots_are_copies() -> None:
    h = Harness()
    job = h.queue.add(["x"], "a")
    snap = h.queue.get(job.id)
    snap.files.append("changed")
    assert h.queue.get(job.id).files == []


def test_real_process_end_to_end() -> None:
    code = (
        'print(\'[easyytdlp:download] {"status": "downloading", "downloaded_bytes": 1,'
        ' "total_bytes": 2} {}\'); print(\'[easyytdlp:file] "out.mp4"\')'
    )
    queue = DownloadQueue()
    job = queue.add([sys.executable, "-c", code], "real")
    assert queue.wait_idle(30)
    current = queue.get(job.id)
    assert current.state == JobState.DONE
    assert current.files == ["out.mp4"]
