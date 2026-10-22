"""The download queue exposed to the GUI through Qt signals."""

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from easy_ytdlp.core import command_builder, paths
from easy_ytdlp.core.options import DownloadOptions
from easy_ytdlp.core.queue import DownloadQueue, Job, RunnerFactory, default_runner

ARCHIVE_FILE_NAME = "archive.txt"


class QueueController(QObject):
    """Owns the ``DownloadQueue``. Its callbacks arrive on reader threads; emitting Qt
    signals from there is safe, and receivers in the GUI thread get them queued."""

    job_changed = Signal(object)
    job_log = Signal(int, str)
    job_finished = Signal(object)
    counts_changed = Signal(int, int)

    def __init__(
        self,
        max_concurrent: int = 2,
        runner_factory: RunnerFactory = default_runner,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.queue = DownloadQueue(
            max_concurrent,
            runner_factory=runner_factory,
            on_change=self._on_change,
            on_log=lambda job, line: self.job_log.emit(job.id, line),
            on_finished=self.job_finished.emit,
        )

    def _on_change(self, job: Job) -> None:
        self.job_changed.emit(job)
        self.counts_changed.emit(self.queue.active_count, self.queue.pending_count)

    def add_download(
        self,
        options: DownloadOptions,
        urls: Sequence[str],
        title: str,
        *,
        playlist_items: str = "",
        thumbnail: str | None = None,
    ) -> Job:
        argv = command_builder.build(
            options,
            urls,
            playlist_items=playlist_items,
            archive_file=paths.data_dir() / ARCHIVE_FILE_NAME,
        )
        folder = options.output.folder or str(paths.default_download_dir())
        return self.queue.add(
            argv,
            title,
            url=urls[0] if urls else "",
            options=options.to_dict(),
            output_dir=folder,
            thumbnail=thumbnail,
        )

    def add_command(self, argv: Sequence[str], title: str, output_dir: str = "") -> Job:
        return self.queue.add(argv, title, output_dir=output_dir or str(Path.home()))

    def jobs(self) -> list[Job]:
        return self.queue.jobs()

    def get(self, job_id: int) -> Job | None:
        return self.queue.get(job_id)

    def cancel(self, job_id: int) -> None:
        self.queue.cancel(job_id)

    def retry(self, job_id: int) -> None:
        self.queue.retry(job_id)

    def remove(self, job_id: int) -> bool:
        removed = self.queue.remove(job_id)
        self.counts_changed.emit(self.queue.active_count, self.queue.pending_count)
        return removed

    def clear_finished(self) -> list[int]:
        removed = self.queue.clear_finished()
        self.counts_changed.emit(self.queue.active_count, self.queue.pending_count)
        return removed

    def set_paused(self, paused: bool) -> None:
        if paused:
            self.queue.pause()
        else:
            self.queue.resume()

    def set_max_concurrent(self, value: int) -> None:
        self.queue.set_max_concurrent(value)

    def shutdown(self) -> None:
        self.queue.pause()
        self.queue.cancel_all()
