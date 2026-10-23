"""Shared application state handed to every page."""

import logging

from PySide6.QtCore import QObject, Signal

from easy_ytdlp.core import settings as settings_store
from easy_ytdlp.core.history import HistoryStore
from easy_ytdlp.core.presets import PresetStore
from easy_ytdlp.core.queue import Job
from easy_ytdlp.core.settings import Settings
from easy_ytdlp.gui.controllers.queue_controller import QueueController
from easy_ytdlp.gui.controllers.tools_controller import ToolsController
from easy_ytdlp.gui.controllers.update_controller import ToolAutoUpdater, UpdateController
from easy_ytdlp.gui.theme import ThemeManager

log = logging.getLogger(__name__)


class AppContext(QObject):
    # Ask the main window to show a page by key, e.g. "queue".
    page_requested = Signal(str)
    # Ask the main window to show a short confirmation.
    toast_requested = Signal(str)
    # Command-mode text to edit (from "Show command").
    command_requested = Signal(str)
    # Options to load into the Download page (from a preset or the history).
    options_requested = Signal(object)
    presets_changed = Signal()
    history_changed = Signal()

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        queue: QueueController | None = None,
        tools: ToolsController | None = None,
        theme: ThemeManager | None = None,
        presets: PresetStore | None = None,
        history: HistoryStore | None = None,
        updates: UpdateController | None = None,
        persist: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings if settings is not None else settings_store.load()
        self.persist = persist
        self.queue = queue or QueueController(self.settings.max_concurrent, parent=self)
        self.tools = tools or ToolsController(parent=self)
        self.theme = theme or ThemeManager(self.settings.theme, parent=self)
        self.presets = presets or PresetStore()
        self.history = history or HistoryStore()
        self.queue.job_finished.connect(self._record)
        self.updates = updates or UpdateController(
            self.settings, save=self.save_settings, parent=self
        )
        self.tool_updater = ToolAutoUpdater(
            self.settings,
            self.tools,
            is_idle=lambda: self.queue.queue.pending_count == 0,
            save=self.save_settings,
            parent=self,
        )

    def _record(self, job: Job) -> None:
        """Store every finished job in the history (runs in the GUI thread)."""
        try:
            self.history.add_job(job)
        except Exception:
            log.exception("Could not record job %s in the history", job.id)
            return
        self.history_changed.emit()

    def save_settings(self) -> None:
        if not self.persist:
            return
        try:
            settings_store.save(self.settings)
        except OSError:
            log.exception("Could not save settings")
