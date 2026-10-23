"""Background app-update checks and tool auto-updates."""

import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from easy_ytdlp import __version__
from easy_ytdlp.core.settings import Settings
from easy_ytdlp.gui.controllers.tools_controller import ToolsController
from easy_ytdlp.gui.controllers.worker import run_async
from easy_ytdlp.tools.base import ToolStatus
from easy_ytdlp.tools.download import DownloadCancelled
from easy_ytdlp.updater import app_update
from easy_ytdlp.updater.app_update import Release


class UpdateController(QObject):
    available = Signal(object)
    # Emitted after a manual check that found nothing.
    up_to_date = Signal()
    failed = Signal(str)
    download_progress = Signal(int, int)
    ready = Signal(object)
    download_failed = Signal(str)

    def __init__(
        self,
        settings: Settings,
        *,
        save: Callable[[], None] = lambda: None,
        find: Callable[..., Release | None] = app_update.find_update,
        download: Callable[..., Path] = app_update.download_setup,
        current: str = __version__,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self._save = save
        self._find = find
        self._download = download
        self.current = current
        self.release: Release | None = None
        self._cancel = threading.Event()
        self.checking = False

    def check(self, *, manual: bool = False) -> bool:
        """Look for a newer release. Automatic checks honor the setting and run daily."""
        if self.checking:
            return False
        if not manual and (
            not self.settings.check_app_updates
            or not app_update.check_due(self.settings.last_app_check)
        ):
            return False
        self.checking = True
        include_beta = self.settings.beta_updates
        skipped = "" if manual else self.settings.skipped_app_version

        def work() -> Release | None:
            return self._find(self.current, include_prereleases=include_beta, skipped=skipped)

        def done(release: Release | None) -> None:
            self.checking = False
            self.settings.last_app_check = time.time()
            self._save()
            self.release = release
            if release is not None:
                self.available.emit(release)
            elif manual:
                self.up_to_date.emit()

        def error(exc: Exception) -> None:
            self.checking = False
            if manual:
                self.failed.emit(str(exc))

        run_async(work, done, error, owner=self)
        return True

    def skip(self, release: Release) -> None:
        self.settings.skipped_app_version = release.version.pep440()
        self._save()

    def download(self, release: Release) -> None:
        self._cancel.clear()
        folder = Path(tempfile.gettempdir()) / "EasyYtDlp-update"
        folder.mkdir(exist_ok=True)

        def work() -> Path:
            return self._download(
                release,
                folder,
                progress=lambda done, total: self.download_progress.emit(done, total or 0),
                cancel=self._cancel,
            )

        def error(exc: Exception) -> None:
            if not isinstance(exc, DownloadCancelled):
                self.download_failed.emit(str(exc))

        run_async(work, self.ready.emit, error, owner=self)

    def cancel_download(self) -> None:
        self._cancel.set()


class ToolAutoUpdater(QObject):
    """At startup (at most once a day), update installed tools that have a newer version."""

    started = Signal(list)

    def __init__(
        self,
        settings: Settings,
        tools: ToolsController,
        *,
        is_idle: Callable[[], bool],
        save: Callable[[], None] = lambda: None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.tools = tools
        self._is_idle = is_idle
        self._save = save
        self._waiting = False

    def run(self) -> bool:
        s = self.settings
        if not s.auto_update_tools or not app_update.check_due(s.last_tools_check):
            return False
        if self.tools.busy or self.tools.missing():
            return False
        self._waiting = True
        self.tools.statuses.connect(self._on_statuses)
        self.tools.check(s.ytdlp_channel)
        return True

    def _on_statuses(self, statuses: list) -> None:
        if not self._waiting:
            return
        self._waiting = False
        self.tools.statuses.disconnect(self._on_statuses)
        if any(isinstance(item, tuple) for item in statuses):
            return  # offline or rate-limited: try again next start
        self.settings.last_tools_check = time.time()
        self._save()
        names = [s.name for s in statuses if isinstance(s, ToolStatus) and s.update_available]
        # Never swap a binary that a running download uses.
        if names and self._is_idle():
            self.started.emit(names)
            self.tools.install(names, self.settings.ytdlp_channel)
