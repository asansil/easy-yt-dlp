"""Queue page: one row per download with progress and actions."""

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QPlainTextEdit, QVBoxLayout, QWidget

from easy_ytdlp.core.queue import Job
from easy_ytdlp.gui.context import AppContext
from easy_ytdlp.gui.pages.base import Page
from easy_ytdlp.gui.widgets.common import button, label
from easy_ytdlp.gui.widgets.job_row import JobRow


def open_in_explorer(job: Job) -> None:
    """Select the downloaded file in Explorer, or open the destination folder."""
    for file in reversed(job.files):
        if Path(file).exists():
            subprocess.Popen(["explorer", "/select,", os.path.normpath(file)])
            return
    if job.output_dir and Path(job.output_dir).is_dir():
        QDesktopServices.openUrl(QUrl.fromLocalFile(job.output_dir))


class LogDialog(QDialog):
    def __init__(self, job: Job, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Log — {title}").format(title=job.title))
        self.resize(820, 480)
        layout = QVBoxLayout(self)
        if job.error:
            layout.addWidget(label(job.error, "ErrorText", wrap=True))
        self.text = QPlainTextEdit()
        self.text.setObjectName("Console")
        self.text.setReadOnly(True)
        self.text.setPlainText("\n".join(job.log))
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())
        layout.addWidget(self.text)


class QueuePage(Page):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(self.tr("Queue"), parent)
        self.ctx = ctx
        self.rows: dict[int, JobRow] = {}

        self.summary = label("", "Muted")
        self.pause_button = button(self.tr("Pause queue"), "pause")
        self.pause_button.setCheckable(True)
        self.clear_button = button(self.tr("Clear finished"), "trash-2")
        self.header.addWidget(self.summary)
        self.header.addWidget(self.pause_button)
        self.header.addWidget(self.clear_button)

        self.empty = label(
            self.tr("No downloads yet. Paste a URL in the Download page to start."), "Muted"
        )
        self.body.addWidget(self.empty)
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(8)
        self.body.addLayout(self.list_layout)
        self.body.addStretch(1)

        self.pause_button.toggled.connect(self._toggle_pause)
        self.clear_button.clicked.connect(self._clear_finished)
        ctx.queue.job_changed.connect(self.update_job)
        ctx.queue.counts_changed.connect(self._update_summary)
        for job in ctx.queue.jobs():
            self.update_job(job)
        self._update_summary()

    def update_job(self, job: Job) -> None:
        row = self.rows.get(job.id)
        if row is None:
            row = JobRow(job)
            row.cancel_requested.connect(self.ctx.queue.cancel)
            row.retry_requested.connect(self.ctx.queue.retry)
            row.open_requested.connect(self._open)
            row.log_requested.connect(self._show_log)
            row.remove_requested.connect(self._remove)
            self.rows[job.id] = row
            # Newest first.
            self.list_layout.insertWidget(0, row)
        else:
            row.update_job(job)
        self.empty.setVisible(not self.rows)

    def _update_summary(self, *_args: object) -> None:
        queue = self.ctx.queue.queue
        self.summary.setText(
            self.tr("{active} active · {max} at a time").format(
                active=queue.active_count, max=queue.max_concurrent
            )
        )

    def _toggle_pause(self, paused: bool) -> None:
        self.ctx.queue.set_paused(paused)
        self.pause_button.setText(self.tr("Resume queue") if paused else self.tr("Pause queue"))

    def _clear_finished(self) -> None:
        for job_id in self.ctx.queue.clear_finished():
            self._drop_row(job_id)

    def _remove(self, job_id: int) -> None:
        if self.ctx.queue.remove(job_id):
            self._drop_row(job_id)

    def _drop_row(self, job_id: int) -> None:
        row = self.rows.pop(job_id, None)
        if row is not None:
            row.setParent(None)
            row.deleteLater()
        self.empty.setVisible(not self.rows)

    def _open(self, job_id: int) -> None:
        job = self.ctx.queue.get(job_id)
        if job is not None:
            open_in_explorer(job)

    def _show_log(self, job_id: int) -> None:
        job = self.ctx.queue.get(job_id)
        if job is not None:
            LogDialog(job, self).exec()
