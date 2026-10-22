"""Analyze URLs in the background; only the latest request is reported."""

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from easy_ytdlp.core import probe
from easy_ytdlp.core.probe import MediaInfo, ProbeError
from easy_ytdlp.gui.controllers.worker import run_async


class ProbeController(QObject):
    started = Signal(str)
    finished = Signal(str, object)
    # url, short message, raw details
    failed = Signal(str, str, str)

    def __init__(
        self,
        analyze: Callable[[str], MediaInfo] = probe.analyze,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._analyze = analyze
        self._request = 0
        self.busy = False

    def analyze(self, url: str) -> None:
        self._request += 1
        request = self._request
        self.busy = True
        self.started.emit(url)

        def done(info: MediaInfo) -> None:
            if request == self._request:
                self.busy = False
                self.finished.emit(url, info)

        def error(exc: Exception) -> None:
            if request != self._request:
                return
            self.busy = False
            if isinstance(exc, ProbeError):
                self.failed.emit(url, exc.message, exc.details)
            else:
                self.failed.emit(url, str(exc), "")

        run_async(lambda: self._analyze(url), done, error)

    def cancel(self) -> None:
        """Forget the running request; its result will be ignored."""
        self._request += 1
        self.busy = False
