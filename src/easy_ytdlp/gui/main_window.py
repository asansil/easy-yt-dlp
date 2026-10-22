"""Main window: sidebar navigation, page stack, tools banner and toasts."""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QCloseEvent, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from easy_ytdlp.gui.context import AppContext
from easy_ytdlp.gui.dialogs import UpdateDialog
from easy_ytdlp.gui.pages.command_page import CommandPage
from easy_ytdlp.gui.pages.download_page import DownloadPage
from easy_ytdlp.gui.pages.history_page import HistoryPage
from easy_ytdlp.gui.pages.presets_page import PresetsPage
from easy_ytdlp.gui.pages.queue_page import QueuePage
from easy_ytdlp.gui.pages.settings_page import SettingsPage
from easy_ytdlp.gui.theme import RESOURCES, icons
from easy_ytdlp.gui.widgets.common import Toast, label
from easy_ytdlp.gui.widgets.tools_banner import ToolsBanner

MIN_WIDTH = 960
MIN_HEIGHT = 640


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext | None = None) -> None:
        super().__init__()
        self.ctx = ctx or AppContext()
        self.setWindowTitle("Easy yt-dlp")
        self.setWindowIcon(QIcon(str(RESOURCES / "app.ico")))
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(220)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(12, 16, 12, 16)
        side.setSpacing(4)
        side.addWidget(label("Easy yt-dlp", "SidebarTitle"))
        self.nav_layout = QVBoxLayout()
        self.nav_layout.setSpacing(4)
        side.addLayout(self.nav_layout)
        side.addStretch(1)
        self.update_button = QPushButton(self.tr("Update available"))
        self.update_button.setObjectName("AccentBadge")
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.hide()
        side.addWidget(self.update_button)
        self.bottom_nav = QVBoxLayout()
        side.addLayout(self.bottom_nav)
        root.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.banner = ToolsBanner(self.ctx.tools)
        banner_holder = QHBoxLayout()
        banner_holder.setContentsMargins(32, 16, 32, 0)
        banner_holder.addWidget(self.banner)
        right.addLayout(banner_holder)
        self.stack = QStackedWidget()
        self.stack.setObjectName("MainStack")
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.pages: dict[str, QWidget] = {}
        self.nav_buttons: dict[str, QPushButton] = {}
        self._build_pages()

        self.toast = Toast(central)
        self.ctx.toast_requested.connect(self.toast.show_message)
        self.ctx.page_requested.connect(self.show_page)
        self.ctx.queue.counts_changed.connect(self._update_queue_badge)
        self.ctx.tools.finished.connect(lambda _ok: self.banner.refresh())
        self.ctx.updates.available.connect(self._on_update_available)
        self.update_button.clicked.connect(self.show_update)
        self.ctx.tool_updater.started.connect(self._on_tools_updating)
        self._auto_updating = False
        self.ctx.tools.tool_installed.connect(self._on_tool_installed)

        for number, key in enumerate(self.pages, start=1):
            QShortcut(QKeySequence(f"Ctrl+{number}"), self, lambda key=key: self.show_page(key))

        self._restore_state()

    # -- pages --------------------------------------------------------------------------

    def _build_pages(self) -> None:
        self.download_page = DownloadPage(self.ctx)
        self.queue_page = QueuePage(self.ctx)
        self.history_page = HistoryPage(self.ctx)
        self.presets_page = PresetsPage(self.ctx)
        self.command_page = CommandPage(self.ctx)
        self.settings_page = SettingsPage(self.ctx)
        self.add_page("download", self.tr("Download"), "download", self.download_page)
        self.add_page("queue", self.tr("Queue"), "list-video", self.queue_page)
        self.add_page("history", self.tr("History"), "history", self.history_page)
        self.add_page("presets", self.tr("Presets"), "star", self.presets_page)
        self.add_page("command", self.tr("Command"), "terminal", self.command_page)
        self.add_page("settings", self.tr("Settings"), "settings", self.settings_page, bottom=True)

    def add_page(
        self, key: str, title: str, icon_name: str, page: QWidget, *, bottom: bool = False
    ) -> None:
        nav = QPushButton(title)
        nav.setObjectName("SidebarButton")
        nav.setCheckable(True)
        nav.setCursor(Qt.CursorShape.PointingHandCursor)
        nav.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        icons.bind(nav, icon_name, "foreground", 18)
        number = len(self.pages) + 1
        nav.setToolTip(self.tr("{page} (Ctrl+{number})").format(page=title, number=number))
        self._group.addButton(nav)
        (self.bottom_nav if bottom else self.nav_layout).addWidget(nav)
        self.stack.addWidget(page)
        self.pages[key] = page
        self.nav_buttons[key] = nav
        nav.clicked.connect(lambda _=False, key=key: self.show_page(key))

    def show_page(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        self.nav_buttons[key].setChecked(True)
        if page is self.download_page:
            self.download_page.url.setFocus()

    def current_page(self) -> str:
        current = self.stack.currentWidget()
        return next((key for key, page in self.pages.items() if page is current), "")

    def _update_queue_badge(self, active: int, pending: int) -> None:
        title = self.tr("Queue")
        self.nav_buttons["queue"].setText(f"{title} ({pending})" if pending else title)

    # -- updates ------------------------------------------------------------------------

    def startup_checks(self) -> None:
        """Daily checks for new tool versions and a new app version."""
        self.ctx.tool_updater.run()
        self.ctx.updates.check()

    def _on_update_available(self, release) -> None:
        self.update_button.setText(
            self.tr("Update available: {version}").format(version=release.tag)
        )
        self.update_button.show()

    def show_update(self) -> None:
        release = self.ctx.updates.release
        if release is not None:
            UpdateDialog(self.ctx.updates, release, self).exec()

    def _on_tools_updating(self, names: list) -> None:
        self._auto_updating = True
        self.toast.show_message(self.tr("Updating {tools}…").format(tools=", ".join(names)))

    def _on_tool_installed(self, name: str, version: str) -> None:
        if self._auto_updating:
            self.toast.show_message(
                self.tr("{tool} updated to {version}").format(tool=name, version=version)
            )

    # -- state --------------------------------------------------------------------------

    def _restore_state(self) -> None:
        settings = self.ctx.settings
        if settings.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(settings.window_geometry.encode("ascii")))
        else:
            self.resize(1180, 780)
        keys = list(self.pages)
        index = settings.last_page if 0 <= settings.last_page < len(keys) else 0
        self.show_page(keys[index])

    def save_state(self) -> None:
        settings = self.ctx.settings
        settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        keys = list(self.pages)
        current = self.current_page()
        settings.last_page = keys.index(current) if current in keys else 0
        settings.last_options = self.download_page.options.to_dict()
        self.ctx.save_settings()

    def closeEvent(self, event: QCloseEvent) -> None:
        pending = self.ctx.queue.queue.pending_count
        if pending and not self.confirm_quit(pending):
            event.ignore()
            return
        self.save_state()
        self.ctx.queue.shutdown()
        self.ctx.tools.cancel()
        event.accept()

    def confirm_quit(self, pending: int) -> bool:
        """Ask before quitting with unfinished downloads (replaced in tests)."""
        answer = QMessageBox.question(
            self,
            self.tr("Downloads in progress"),
            self.tr("Unfinished downloads: {count}. Cancel them and quit?").format(count=pending),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
