"""Banner shown while yt-dlp, FFmpeg or deno are missing, with an install button."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QProgressBar, QVBoxLayout, QWidget

from easy_ytdlp.gui import formatting
from easy_ytdlp.gui.controllers.tools_controller import ToolsController
from easy_ytdlp.gui.widgets.common import button, label


class ToolsBanner(QFrame):
    def __init__(self, tools: ToolsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tools = tools
        self.setObjectName("Banner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        text = QVBoxLayout()
        self.message = label("", wrap=True)
        self.detail = label("", "Caption", wrap=True)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        text.addWidget(self.message)
        text.addWidget(self.detail)
        text.addWidget(self.progress)
        layout.addLayout(text, 1)
        self.install_button = button(self.tr("Install now"), "download", variant="primary")
        layout.addWidget(self.install_button)
        self.install_button.clicked.connect(self.install)

        tools.tool_started.connect(self._on_started)
        tools.progress.connect(self._on_progress)
        tools.failed.connect(self._on_failed)
        tools.finished.connect(self._on_finished)
        self._errors: list[str] = []
        self.refresh()

    def refresh(self) -> None:
        missing = self.tools.missing()
        self.setVisible(bool(missing))
        if missing:
            self.message.setText(
                self.tr("Easy yt-dlp needs these free tools to download: {tools}.").format(
                    tools=", ".join(missing)
                )
            )
            self.detail.setText(
                self.tr(
                    "They are downloaded from their official sources and verified (about 180 MB)."
                )
            )

    def install(self) -> None:
        self._errors.clear()
        self.install_button.setEnabled(False)
        self.progress.show()
        self.progress.setRange(0, 0)
        self.tools.install()

    def _on_started(self, name: str) -> None:
        self.message.setText(self.tr("Downloading {tool}…").format(tool=name))
        self.progress.setRange(0, 0)

    def _on_progress(self, name: str, done: int, total: int) -> None:
        if total:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(done * 1000 / total))
            self.detail.setText(f"{formatting.size(done)} / {formatting.size(total)}")
        else:
            self.detail.setText(formatting.size(done))

    def _on_failed(self, name: str, message: str) -> None:
        self._errors.append(f"{name}: {message}" if name else message)

    def _on_finished(self, ok: bool) -> None:
        self.install_button.setEnabled(True)
        self.progress.hide()
        self.refresh()
        if not ok and self.isVisible():
            self.install_button.setText(self.tr("Try again"))
            self.message.setText(
                self.tr("The tools could not be installed. Check your internet connection.")
            )
            self.detail.setText("\n".join(self._errors))
