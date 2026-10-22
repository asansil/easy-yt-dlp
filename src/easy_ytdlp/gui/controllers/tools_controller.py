"""Install and update the external tools in the background."""

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from easy_ytdlp.gui.controllers.worker import run_async
from easy_ytdlp.tools import manager
from easy_ytdlp.tools.base import Tool, ToolStatus
from easy_ytdlp.tools.download import DownloadCancelled


class ToolsController(QObject):
    # tool name, bytes done, total bytes (0 when unknown)
    progress = Signal(str, int, int)
    tool_started = Signal(str)
    tool_installed = Signal(str, str)
    # tool name, error message
    failed = Signal(str, str)
    # True when every requested tool was installed
    finished = Signal(bool)
    statuses = Signal(object)

    def __init__(
        self,
        tools: Callable[[], list[Tool]] = manager.all_tools,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tools = tools
        self._cancel = threading.Event()
        self.busy = False

    def missing(self) -> list[str]:
        return [tool.name for tool in self._tools() if not tool.is_installed()]

    def install(self, names: list[str] | None = None, channel: str = "stable") -> None:
        """Install (or update) the named tools, or the missing ones when ``names`` is None."""
        if self.busy:
            return
        selected = [
            tool
            for tool in self._tools()
            if (names is None and not tool.is_installed()) or (names and tool.name in names)
        ]
        self.busy = True
        self._cancel.clear()

        def work() -> bool:
            ok = True
            for tool in selected:
                self.tool_started.emit(tool.name)
                try:
                    version = tool.install(
                        channel,
                        progress=lambda done, total, name=tool.name: self.progress.emit(
                            name, done, total or 0
                        ),
                        cancel=self._cancel,
                    )
                except DownloadCancelled:
                    return False
                except Exception as exc:
                    ok = False
                    self.failed.emit(tool.name, str(exc))
                else:
                    self.tool_installed.emit(tool.name, version)
            return ok

        def done(ok: bool) -> None:
            self.busy = False
            self.finished.emit(ok)

        def error(exc: Exception) -> None:
            self.busy = False
            self.failed.emit("", str(exc))
            self.finished.emit(False)

        run_async(work, done, error)

    def cancel(self) -> None:
        self._cancel.set()

    def check(self, channel: str = "stable", check_latest: bool = True) -> None:
        """Emit ``statuses`` with a ``ToolStatus`` (or an error string) per tool."""

        def work() -> list[ToolStatus | tuple[str, str]]:
            result: list[ToolStatus | tuple[str, str]] = []
            for tool in self._tools():
                try:
                    result.append(tool.status(channel, check_latest=check_latest))
                except Exception as exc:
                    installed = tool.installed_version() if tool.is_installed() else None
                    result.append(ToolStatus(tool.name, installed, None))
                    result.append((tool.name, str(exc)))
            return result

        run_async(work, self.statuses.emit, lambda exc: self.statuses.emit([("", str(exc))]))
