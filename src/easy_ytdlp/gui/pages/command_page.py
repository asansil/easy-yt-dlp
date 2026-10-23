"""Command page: run any yt-dlp arguments and watch the raw output."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QWidget

from easy_ytdlp.core import command_builder, paths
from easy_ytdlp.core.queue import Job
from easy_ytdlp.gui.context import AppContext
from easy_ytdlp.gui.pages.base import Page
from easy_ytdlp.gui.widgets.common import FolderPicker, button, card, label
from easy_ytdlp.gui.widgets.job_row import state_text

HISTORY_LIMIT = 50
CONSOLE_LIMIT = 5000
DOCS_URL = "https://github.com/yt-dlp/yt-dlp#usage-and-options"


class CommandPage(Page):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(self.tr("Command"), parent)
        self.ctx = ctx
        self.current_job: int | None = None
        self._history_index = len(ctx.settings.command_history)

        intro = label(
            self.tr(
                "Run yt-dlp with your own arguments. The job goes to the queue like any other "
                "download, and its output appears below."
            ),
            "Muted",
            wrap=True,
        )
        self.body.addWidget(intro)
        docs = label("", "Muted")
        docs.setTextFormat(Qt.TextFormat.RichText)
        docs.setOpenExternalLinks(True)
        docs.setText(
            '<a href="{url}">{text}</a>'.format(
                url=DOCS_URL, text=self.tr("yt-dlp options reference")
            )
        )
        self.body.addWidget(docs)

        frame, layout = card()
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.args = QLineEdit()
        self.args.setObjectName("CommandInput")
        self.args.setPlaceholderText("-f bv*+ba/b --embed-subs")
        self.args.installEventFilter(self)
        self.url = QLineEdit()
        self.url.setPlaceholderText(self.tr("Optional; you can also put URLs in the arguments"))
        self.folder = FolderPicker()
        self.folder.set_text(str(ctx.settings.effective_download_dir()))
        form.addRow(self.tr("Arguments"), self.args)
        form.addRow(self.tr("URL"), self.url)
        form.addRow(self.tr("Save to"), self.folder)
        layout.addLayout(form)

        self.error = label("", "ErrorText", wrap=True)
        self.error.hide()
        layout.addWidget(self.error)
        row = QHBoxLayout()
        self.run_button = button(self.tr("Run"), "play", variant="primary")
        self.stop_button = button(self.tr("Stop"), "x", variant="destructive")
        self.stop_button.setEnabled(False)
        row.addWidget(self.run_button)
        row.addWidget(self.stop_button)
        row.addStretch(1)
        layout.addLayout(row)
        self.body.addWidget(frame)

        self.body.addWidget(label(self.tr("Output"), "SectionTitle"))
        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(CONSOLE_LIMIT)
        self.console.setMinimumHeight(260)
        self.console.setAccessibleName(self.tr("Command output"))
        self.body.addWidget(self.console, 1)

        self.run_button.clicked.connect(self.run)
        self.args.returnPressed.connect(self.run)
        self.stop_button.clicked.connect(self._stop)
        ctx.queue.job_log.connect(self._on_log)
        ctx.queue.job_changed.connect(self._on_job_changed)
        ctx.command_requested.connect(self.set_command)

    def set_command(self, text: str) -> None:
        self.args.setText(text)
        self.url.clear()
        self.args.setFocus()

    def run(self) -> None:
        text = self.args.text().strip()
        if not text:
            self._show_error(self.tr("Type some yt-dlp arguments first."))
            return
        if not paths.ytdlp_exe().is_file():
            self._show_error(self.tr("yt-dlp is not installed yet. Install the tools first."))
            return
        try:
            argv = command_builder.manual_argv(text, url=self.url.text(), folder=self.folder.text())
        except command_builder.ManualCommandError:
            self._show_error(self.tr("The arguments could not be read. Check the quotes."))
            return
        self._show_error("")
        history = [h for h in self.ctx.settings.command_history if h != text]
        self.ctx.settings.command_history = [*history, text][-HISTORY_LIMIT:]
        self._history_index = len(self.ctx.settings.command_history)
        self.ctx.save_settings()

        self.console.clear()
        self.console.appendPlainText(command_builder.to_display(argv))
        job = self.ctx.queue.add_command(argv, f"yt-dlp {text}", self.folder.text())
        self.current_job = job.id
        self._on_job_changed(job)

    def _stop(self) -> None:
        if self.current_job is not None:
            self.ctx.queue.cancel(self.current_job)

    def _on_log(self, job_id: int, line: str) -> None:
        if job_id == self.current_job:
            self.console.appendPlainText(line)

    def _on_job_changed(self, job: Job) -> None:
        if job.id != self.current_job:
            return
        self.stop_button.setEnabled(not job.state.finished)
        if job.state.finished:
            self.console.appendPlainText(
                self.tr("— finished: {state} (exit code {code}) —").format(
                    state=state_text(job.state), code=job.returncode
                )
            )

    def _show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Up/Down in the arguments field browse the command history."""
        if watched is self.args and event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            history = self.ctx.settings.command_history
            if event.key() == Qt.Key.Key_Up and history:
                self._history_index = max(0, self._history_index - 1)
                self.args.setText(history[self._history_index])
                return True
            if event.key() == Qt.Key.Key_Down and history:
                self._history_index = min(len(history), self._history_index + 1)
                self.args.setText(
                    history[self._history_index] if self._history_index < len(history) else ""
                )
                return True
        return super().eventFilter(watched, event)
