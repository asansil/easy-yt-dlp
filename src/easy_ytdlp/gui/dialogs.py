"""Dialogs: first-run setup and the app update."""

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from easy_ytdlp.gui import formatting
from easy_ytdlp.gui.controllers.tools_controller import ToolsController
from easy_ytdlp.gui.controllers.update_controller import UpdateController
from easy_ytdlp.gui.widgets.common import button, label
from easy_ytdlp.tools import migration
from easy_ytdlp.updater import app_update
from easy_ytdlp.updater.app_update import Release


class FirstRunDialog(QDialog):
    """Welcome screen that downloads yt-dlp, FFmpeg and deno, and cleans up v1."""

    def __init__(
        self,
        tools: ToolsController,
        *,
        channel: str = "stable",
        legacy: bool | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tools = tools
        self.channel = channel
        self.setWindowTitle(self.tr("Welcome to Easy yt-dlp"))
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(label(self.tr("Welcome to Easy yt-dlp"), "PageTitle"))
        layout.addWidget(
            label(
                self.tr(
                    "To download, Easy yt-dlp needs three free tools: yt-dlp (the downloader), "
                    "FFmpeg (to merge and convert) and deno (needed by YouTube). They are "
                    "downloaded from their official sites and checked before use (about 180 MB)."
                ),
                "Muted",
                wrap=True,
            )
        )

        grid = QGridLayout()
        self.rows: dict[str, tuple[QProgressBar, object]] = {}
        names = tools.missing()
        self.names = names
        for row, name in enumerate(names):
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(0)
            state = label(self.tr("Pending"), "Caption")
            grid.addWidget(label(name), row, 0)
            grid.addWidget(bar, row, 1)
            grid.addWidget(state, row, 2)
            self.rows[name] = (bar, state)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        legacy = migration.legacy_present() if legacy is None else legacy
        self.legacy = QCheckBox(
            self.tr(
                "Remove the tools of Easy yt-dlp 1.x (%USERPROFILE%\\.ytdlp_env) and its PATH entry"
            )
        )
        self.legacy.setChecked(True)
        self.legacy.setVisible(legacy)
        self._legacy_offered = legacy
        layout.addWidget(self.legacy)

        self.error = label("", "ErrorText", wrap=True)
        self.error.hide()
        layout.addWidget(self.error)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.skip_button = button(self.tr("Skip for now"))
        self.install_button = button(self.tr("Install"), "download", variant="primary")
        self.close_button = button(self.tr("Start"), "check", variant="primary")
        self.close_button.hide()
        actions.addWidget(self.skip_button)
        actions.addWidget(self.install_button)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

        self.skip_button.clicked.connect(self.reject)
        self.install_button.clicked.connect(self.install)
        self.close_button.clicked.connect(self.accept)
        tools.tool_started.connect(self._on_started)
        tools.progress.connect(self._on_progress)
        tools.tool_installed.connect(self._on_installed)
        tools.failed.connect(self._on_failed)
        tools.finished.connect(self._on_finished)
        self._failures: list[str] = []
        if not names:
            self.install_button.hide()
            self.skip_button.hide()
            self.close_button.show()

    def install(self) -> None:
        self._failures.clear()
        self.error.hide()
        self.install_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.install_button.setText(self.tr("Installing…"))
        self.tools.install(None, self.channel)

    def _row(self, name: str):
        return self.rows.get(name, (None, None))

    def _on_started(self, name: str) -> None:
        bar, state = self._row(name)
        if bar is not None:
            bar.setRange(0, 0)
            state.setText(self.tr("Downloading…"))

    def _on_progress(self, name: str, done: int, total: int) -> None:
        bar, state = self._row(name)
        if bar is None:
            return
        if total:
            bar.setRange(0, 1000)
            bar.setValue(int(done * 1000 / total))
        state.setText(formatting.size(done))

    def _on_installed(self, name: str, version: str) -> None:
        bar, state = self._row(name)
        if bar is not None:
            bar.setRange(0, 1000)
            bar.setValue(1000)
            state.setText(self.tr("✓ {version}").format(version=version))

    def _on_failed(self, name: str, message: str) -> None:
        self._failures.append(f"{name}: {message}" if name else message)
        bar, state = self._row(name)
        if bar is not None:
            bar.setRange(0, 1000)
            bar.setValue(0)
            state.setText(self.tr("✕ Failed"))

    def _on_finished(self, ok: bool) -> None:
        if self._legacy_offered and self.legacy.isChecked() and self.legacy.isEnabled():
            problems = migration.remove_legacy()
            if problems:
                self._failures.append(
                    self.tr("Could not remove: {items}").format(items=", ".join(problems))
                )
            self.legacy.setEnabled(False)
        if ok and not self._failures:
            self.install_button.hide()
            self.skip_button.hide()
            self.close_button.show()
            self.close_button.setFocus()
            return
        self.error.setText(
            self.tr(
                "Some tools could not be installed. Check your internet connection and try "
                "again.\n{details}"
            ).format(details="\n".join(self._failures))
        )
        self.error.show()
        self.install_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.install_button.setText(self.tr("Try again"))


class UpdateDialog(QDialog):
    def __init__(
        self, updates: UpdateController, release: Release, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.updates = updates
        self.release = release
        self.setWindowTitle(self.tr("Update available"))
        self.resize(620, 460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(
            label(
                self.tr("Easy yt-dlp {version} is available").format(version=release.tag),
                "PageTitle",
            )
        )
        layout.addWidget(
            label(self.tr("You have version {current}.").format(current=updates.current), "Muted")
        )
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        # Release notes come from the network: plain text only.
        self.notes.setPlainText(release.notes or release.name)
        layout.addWidget(self.notes, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.error = label("", "ErrorText", wrap=True)
        self.error.hide()
        layout.addWidget(self.error)

        actions = QHBoxLayout()
        self.skip_button = button(self.tr("Skip this version"), variant="ghost")
        self.later_button = button(self.tr("Later"))
        self.install_button = button(self.tr("Install now"), "download", variant="primary")
        actions.addWidget(self.skip_button)
        actions.addStretch(1)
        actions.addWidget(self.later_button)
        actions.addWidget(self.install_button)
        layout.addLayout(actions)
        layout.addWidget(
            label(
                self.tr("The app closes, updates itself and opens again. Your settings are kept."),
                "Caption",
                wrap=True,
            )
        )

        self.skip_button.clicked.connect(self._skip)
        self.later_button.clicked.connect(self.reject)
        self.install_button.clicked.connect(self._install)
        updates.download_progress.connect(self._on_progress)
        updates.ready.connect(self._on_ready)
        updates.download_failed.connect(self._on_failed)

    def _skip(self) -> None:
        self.updates.skip(self.release)
        self.reject()

    def _install(self) -> None:
        self.install_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.error.hide()
        self.progress.show()
        self.progress.setRange(0, 0)
        self.updates.download(self.release)

    def _on_progress(self, done: int, total: int) -> None:
        if total:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(done * 1000 / total))

    def _on_failed(self, message: str) -> None:
        self.progress.hide()
        self.install_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.error.setText(
            self.tr("The update could not be downloaded or verified: {error}").format(error=message)
        )
        self.error.show()

    def launch(self, setup) -> None:
        """Run the Setup and quit (replaced in tests)."""
        app_update.launch_installer(setup)
        app = QApplication.instance()
        if app is not None:
            for widget in app.topLevelWidgets():
                if hasattr(widget, "confirm_quit"):
                    widget.confirm_quit = lambda pending: True
            app.closeAllWindows()
            app.quit()

    def _on_ready(self, setup) -> None:
        self.progress.setValue(1000)
        self.accept()
        self.launch(setup)
