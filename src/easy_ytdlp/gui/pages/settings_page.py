"""Settings page: general, downloads, tools, updates, data and about."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QWidget,
)

from easy_ytdlp import __version__
from easy_ytdlp.core import paths
from easy_ytdlp.gui.context import AppContext
from easy_ytdlp.gui.pages.base import Page
from easy_ytdlp.gui.widgets.common import FolderPicker, button, card, label
from easy_ytdlp.tools import path_env
from easy_ytdlp.tools.base import ToolStatus

REPO_URL = "https://github.com/asansil/easy-yt-dlp"


class SettingsPage(Page):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(self.tr("Settings"), parent)
        self.ctx = ctx
        s = ctx.settings

        # General
        self.body.addWidget(label(self.tr("General"), "SectionTitle"))
        frame, layout = card()
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.language = QComboBox()
        for value, text in (
            ("system", self.tr("Same as Windows")),
            ("en", "English"),
            ("es", "Español"),
        ):
            self.language.addItem(text, value)
        self.language.setCurrentIndex(max(0, self.language.findData(s.language)))
        self.language_note = label(self.tr("Restart Easy yt-dlp to apply the language."), "Caption")
        self.language_note.hide()
        self.theme = QComboBox()
        for value, text in (
            ("system", self.tr("Same as Windows")),
            ("light", self.tr("Light")),
            ("dark", self.tr("Dark")),
        ):
            self.theme.addItem(text, value)
        self.theme.setCurrentIndex(max(0, self.theme.findData(s.theme)))
        self.folder = FolderPicker()
        self.folder.set_text(str(s.effective_download_dir()))
        form.addRow(self.tr("Language"), self.language)
        form.addRow("", self.language_note)
        form.addRow(self.tr("Theme"), self.theme)
        form.addRow(self.tr("Default folder"), self.folder)
        layout.addLayout(form)
        self.body.addWidget(frame)

        # Downloads
        self.body.addWidget(label(self.tr("Downloads"), "SectionTitle"))
        frame, layout = card()
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.concurrency = QComboBox()
        for value in range(1, 9):
            self.concurrency.addItem(str(value), value)
        self.concurrency.setCurrentIndex(self.concurrency.findData(s.max_concurrent))
        form.addRow(self.tr("Downloads at the same time"), self.concurrency)
        layout.addLayout(form)
        self.body.addWidget(frame)

        self._build_tools()
        self._build_updates()
        self._build_data_and_about()
        self.body.addStretch(1)

        self.language.currentIndexChanged.connect(self._language_changed)
        self.theme.currentIndexChanged.connect(self._theme_changed)
        self.folder.changed.connect(self._folder_changed)
        self.concurrency.currentIndexChanged.connect(
            lambda: self._concurrency_changed(self.concurrency.currentData())
        )

    def _language_changed(self) -> None:
        self.ctx.settings.language = self.language.currentData()
        self.language_note.show()
        self.ctx.save_settings()

    def _theme_changed(self) -> None:
        self.ctx.settings.theme = self.theme.currentData()
        self.ctx.theme.set_mode(self.ctx.settings.theme)
        self.ctx.save_settings()

    def _folder_changed(self, value: str) -> None:
        self.ctx.settings.download_dir = value.strip()
        self.ctx.save_settings()

    def _concurrency_changed(self, value: int) -> None:
        self.ctx.settings.max_concurrent = value
        self.ctx.queue.set_max_concurrent(value)
        self.ctx.save_settings()

    # -- tools --------------------------------------------------------------------------

    def _build_tools(self) -> None:
        self.body.addWidget(label(self.tr("Tools"), "SectionTitle"))
        frame, layout = card()
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        headers = (self.tr("Tool"), self.tr("Installed"), self.tr("Latest"))
        for column, text in enumerate(headers):
            grid.addWidget(label(text, "Muted"), 0, column)
        self.tool_rows: dict[str, tuple] = {}
        for row, name in enumerate(("yt-dlp", "FFmpeg", "deno"), start=1):
            installed = label("…")
            latest = label("—")
            grid.addWidget(label(name), row, 0)
            grid.addWidget(installed, row, 1)
            grid.addWidget(latest, row, 2)
            self.tool_rows[name] = (installed, latest)
        grid.setColumnStretch(3, 1)
        layout.addLayout(grid)
        self.tools_status = label("", "Caption", wrap=True)
        layout.addWidget(self.tools_status)

        actions = QHBoxLayout()
        self.check_tools_button = button(self.tr("Check for updates"), "refresh-cw")
        self.update_tools_button = button(self.tr("Update"), "download", variant="primary")
        self.update_tools_button.setEnabled(False)
        actions.addWidget(self.check_tools_button)
        actions.addWidget(self.update_tools_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.channel = QComboBox()
        self.channel.addItem(self.tr("Stable"), "stable")
        self.channel.addItem(self.tr("Nightly (newest fixes)"), "nightly")
        self.channel.setCurrentIndex(max(0, self.channel.findData(self.ctx.settings.ytdlp_channel)))
        self.auto_tools = QCheckBox(self.tr("Update the tools automatically at startup"))
        self.auto_tools.setChecked(self.ctx.settings.auto_update_tools)
        form.addRow(self.tr("yt-dlp channel"), self.channel)
        form.addRow("", self.auto_tools)
        layout.addLayout(form)

        path_row = QHBoxLayout()
        self.path_status = label("", wrap=True)
        self.path_button = button("")
        path_row.addWidget(self.path_status, 1)
        path_row.addWidget(self.path_button)
        layout.addLayout(path_row)
        self.body.addWidget(frame)

        self._updatable: list[str] = []
        self._checking_latest = False
        self.check_tools_button.clicked.connect(lambda: self.check_tools(latest=True))
        self.update_tools_button.clicked.connect(self.update_tools)
        self.channel.currentIndexChanged.connect(self._channel_changed)
        self.auto_tools.toggled.connect(self._auto_tools_changed)
        self.path_button.clicked.connect(self.toggle_path)
        self.ctx.tools.statuses.connect(self._on_statuses)
        self.ctx.tools.finished.connect(lambda _ok: self.check_tools(latest=False))
        self.ctx.tools.failed.connect(self._on_tool_failed)
        self.refresh_path()
        self.check_tools(latest=False)

    def check_tools(self, *, latest: bool = True) -> None:
        self.check_tools_button.setEnabled(False)
        self.tools_status.setText(self.tr("Checking…") if latest else "")
        self._checking_latest = latest
        self.ctx.tools.check(self.ctx.settings.ytdlp_channel, check_latest=latest)

    def _on_statuses(self, statuses: list) -> None:
        self.check_tools_button.setEnabled(True)
        errors = [item[1] for item in statuses if isinstance(item, tuple)]
        self._updatable = []
        for status in statuses:
            if not isinstance(status, ToolStatus) or status.name not in self.tool_rows:
                continue
            installed, latest = self.tool_rows[status.name]
            installed.setText(status.installed or self.tr("Not installed"))
            if status.latest:
                latest.setText(status.latest)
            if status.missing or (status.latest and status.update_available):
                self._updatable.append(status.name)
        self.update_tools_button.setEnabled(bool(self._updatable) and not self.ctx.tools.busy)
        if errors:
            self.tools_status.setText(
                self.tr("Could not check for updates: {error}").format(error=errors[-1])
            )
        elif self._checking_latest:
            if self._updatable:
                text = self.tr("Updates available: {tools}").format(
                    tools=", ".join(self._updatable)
                )
            else:
                text = self.tr("Everything is up to date.")
            self.tools_status.setText(text)

    def update_tools(self) -> None:
        if self.ctx.queue.queue.pending_count:
            self.tools_status.setText(
                self.tr("Wait until the downloads finish before updating the tools.")
            )
            return
        self.update_tools_button.setEnabled(False)
        self.tools_status.setText(
            self.tr("Updating {tools}…").format(tools=", ".join(self._updatable))
        )
        self.ctx.tools.install(list(self._updatable), self.ctx.settings.ytdlp_channel)

    def _on_tool_failed(self, name: str, message: str) -> None:
        self.tools_status.setText(f"{name}: {message}" if name else message)

    def _channel_changed(self) -> None:
        self.ctx.settings.ytdlp_channel = self.channel.currentData()
        self.ctx.save_settings()
        self.tool_rows["yt-dlp"][1].setText("—")

    def _auto_tools_changed(self, checked: bool) -> None:
        self.ctx.settings.auto_update_tools = checked
        self.ctx.save_settings()

    def refresh_path(self) -> None:
        try:
            in_path = path_env.is_in_user_path(paths.tools_dir())
        except OSError:
            in_path = False
        self._in_path = in_path
        if in_path:
            text = self.tr(
                "yt-dlp and FFmpeg can be used from any terminal (they are in your PATH)."
            )
            action = self.tr("Remove from PATH")
        else:
            text = self.tr("yt-dlp and FFmpeg are not in your PATH; terminals cannot find them.")
            action = self.tr("Add to PATH")
        self.path_status.setText(text)
        self.path_button.setText(action)

    def toggle_path(self) -> None:
        try:
            if self._in_path:
                path_env.remove_from_user_path(paths.tools_dir())
            else:
                path_env.add_to_user_path(paths.tools_dir())
        except (OSError, RuntimeError) as exc:
            self.path_status.setText(str(exc))
            return
        self.refresh_path()

    # -- updates ------------------------------------------------------------------------

    def _build_updates(self) -> None:
        self.body.addWidget(label(self.tr("Updates"), "SectionTitle"))
        frame, layout = card()
        self.auto_app = QCheckBox(self.tr("Check for new versions of Easy yt-dlp once a day"))
        self.auto_app.setChecked(self.ctx.settings.check_app_updates)
        self.beta = QCheckBox(self.tr("Include beta versions"))
        self.beta.setChecked(self.ctx.settings.beta_updates)
        layout.addWidget(self.auto_app)
        layout.addWidget(self.beta)
        row = QHBoxLayout()
        self.check_app_button = button(self.tr("Check now"), "refresh-cw")
        self.app_status = label("", "Caption", wrap=True)
        row.addWidget(self.check_app_button)
        row.addWidget(self.app_status, 1)
        layout.addLayout(row)
        self.body.addWidget(frame)

        self.auto_app.toggled.connect(self._auto_app_changed)
        self.beta.toggled.connect(self._beta_changed)
        self.check_app_button.clicked.connect(self.check_app)
        updates = self.ctx.updates
        updates.up_to_date.connect(self._on_up_to_date)
        updates.failed.connect(self._on_check_failed)
        updates.available.connect(self._on_available)

    def _on_up_to_date(self) -> None:
        self.app_status.setText(self.tr("You have the latest version."))

    def _on_check_failed(self, error: str) -> None:
        self.app_status.setText(self.tr("Could not check for updates: {error}").format(error=error))

    def _on_available(self, release) -> None:
        self.app_status.setText(
            self.tr("Version {version} is available.").format(version=release.tag)
        )

    def check_app(self) -> None:
        if self.ctx.updates.check(manual=True):
            self.app_status.setText(self.tr("Checking…"))

    def _auto_app_changed(self, checked: bool) -> None:
        self.ctx.settings.check_app_updates = checked
        self.ctx.save_settings()

    def _beta_changed(self, checked: bool) -> None:
        self.ctx.settings.beta_updates = checked
        self.ctx.save_settings()

    # -- data and about -----------------------------------------------------------------

    def _build_data_and_about(self) -> None:
        self.body.addWidget(label(self.tr("Data"), "SectionTitle"))
        frame, layout = card(QHBoxLayout)
        self.open_data_button = button(self.tr("Open data folder"), "folder-open")
        self.clear_history_button = button(
            self.tr("Clear history"), "trash-2", variant="destructive"
        )
        layout.addWidget(self.open_data_button)
        layout.addWidget(self.clear_history_button)
        layout.addStretch(1)
        self.body.addWidget(frame)
        self.open_data_button.clicked.connect(self._open_data)
        self.clear_history_button.clicked.connect(self.clear_history)

        self.body.addWidget(label(self.tr("About"), "SectionTitle"))
        frame, layout = card()
        layout.addWidget(label(self.tr("Easy yt-dlp {version}").format(version=__version__)))
        links = label("", "Muted", wrap=True)
        links.setTextFormat(Qt.TextFormat.RichText)
        links.setOpenExternalLinks(True)
        parts = [
            (REPO_URL, self.tr("Project page")),
            (f"{REPO_URL}/blob/main/LICENSE", self.tr("MIT License")),
            (
                f"{REPO_URL}/blob/main/packaging/THIRD_PARTY_NOTICES.md",
                self.tr("Third-party licenses"),
            ),
        ]
        links.setText(" · ".join(f'<a href="{url}">{text}</a>' for url, text in parts))
        layout.addWidget(links)
        self.body.addWidget(frame)

    def _open_data(self) -> None:
        paths.data_dir().mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.data_dir())))

    def confirm_clear_history(self) -> bool:
        """Ask before clearing the history (replaced in tests)."""
        answer = QMessageBox.question(
            self,
            self.tr("Clear history"),
            self.tr("Remove every entry from the history? Downloaded files are kept."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def clear_history(self) -> None:
        if self.confirm_clear_history():
            self.ctx.history.clear()
            self.ctx.history_changed.emit()
            self.ctx.toast_requested.emit(self.tr("History cleared"))
