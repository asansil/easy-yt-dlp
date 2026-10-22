"""One download in the Queue page."""

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QProgressBar, QVBoxLayout, QWidget

from easy_ytdlp.core.queue import Job, JobState
from easy_ytdlp.gui import formatting
from easy_ytdlp.gui.widgets.common import icon_button, label, set_state


def state_text(state: JobState) -> str:
    translate = QCoreApplication.translate
    names = {
        JobState.WAITING: translate("JobState", "Waiting"),
        JobState.DOWNLOADING: translate("JobState", "Downloading"),
        JobState.PROCESSING: translate("JobState", "Processing"),
        JobState.DONE: translate("JobState", "Done"),
        JobState.FAILED: translate("JobState", "Failed"),
        JobState.CANCELLED: translate("JobState", "Cancelled"),
    }
    return names[state]


STATE_SYMBOL = {
    JobState.WAITING: "○",
    JobState.DOWNLOADING: "↓",
    JobState.PROCESSING: "⚙",
    JobState.DONE: "✓",
    JobState.FAILED: "✕",
    JobState.CANCELLED: "⊘",
}


class JobRow(QFrame):
    cancel_requested = Signal(int)
    retry_requested = Signal(int)
    open_requested = Signal(int)
    log_requested = Signal(int)
    remove_requested = Signal(int)

    def __init__(self, job: Job, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.job_id = job.id
        self.setObjectName("Card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(12)

        body = QVBoxLayout()
        body.setSpacing(6)
        top = QHBoxLayout()
        self.title = label(job.title, "SectionTitle")
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.chip = label("", "Chip")
        top.addWidget(self.title, 1)
        top.addWidget(self.chip)
        body.addLayout(top)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        body.addWidget(self.progress)
        self.status = label("", "Caption", wrap=True)
        self.error = label("", "ErrorText", wrap=True)
        body.addWidget(self.status)
        body.addWidget(self.error)
        layout.addLayout(body, 1)

        self.cancel = icon_button("x", self.tr("Cancel download"), role="destructive")
        self.retry = icon_button("rotate-ccw", self.tr("Retry"))
        self.open = icon_button("folder-open", self.tr("Open folder"))
        self.log = icon_button("file-text", self.tr("Show log"))
        self.remove = icon_button("trash-2", self.tr("Remove from list"))
        for widget, signal in (
            (self.cancel, self.cancel_requested),
            (self.retry, self.retry_requested),
            (self.open, self.open_requested),
            (self.log, self.log_requested),
            (self.remove, self.remove_requested),
        ):
            widget.clicked.connect(lambda _=False, s=signal: s.emit(self.job_id))
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)
        self.update_job(job)

    def update_job(self, job: Job) -> None:
        self.title.setText(job.title)
        self.chip.setText(f"{STATE_SYMBOL[job.state]} {state_text(job.state)}")
        set_state(self.chip, "state", job.state.value)
        set_state(self.progress, "state", job.state.value)
        if job.progress is None and job.state.active:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int((job.progress or 0) * 1000))
        self.status.setText(self._status_text(job))
        self.error.setText(job.error if job.state == JobState.FAILED else "")
        self.error.setVisible(job.state == JobState.FAILED and bool(job.error))
        self.cancel.setVisible(not job.state.finished)
        self.retry.setVisible(job.state in {JobState.FAILED, JobState.CANCELLED})
        self.remove.setVisible(job.state.finished)
        self.open.setEnabled(bool(job.files or job.output_dir))

    def _status_text(self, job: Job) -> str:
        parts: list[str] = []
        if job.item_count and job.item_count > 1 and job.item_index:
            parts.append(
                self.tr("Item {index} of {count}").format(
                    index=job.item_index, count=job.item_count
                )
            )
        if job.item_title and job.item_title != job.title:
            parts.append(job.item_title)
        if job.state == JobState.DOWNLOADING:
            if job.progress is not None:
                parts.append(f"{job.progress * 100:.0f} %")
            parts += [p for p in (formatting.speed(job.speed), formatting.eta(job.eta)) if p]
        elif job.state == JobState.PROCESSING and job.postprocessor:
            parts.append(self.tr("Processing: {step}").format(step=job.postprocessor))
        elif job.state == JobState.DONE and job.files:
            parts.append(self.tr("Files: {count}").format(count=len(job.files)))
        return " · ".join(parts)
