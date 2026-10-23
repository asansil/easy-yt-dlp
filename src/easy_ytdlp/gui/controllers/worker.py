"""Run a blocking function in the thread pool and get its result as a Qt signal."""

import contextlib
import logging
from collections.abc import Callable
from typing import Any

import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

log = logging.getLogger(__name__)


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(object)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: TaskSignals) -> None:
        super().__init__()
        self.fn = fn
        self.signals = signals

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:
            log.debug("Background task failed", exc_info=True)
            self._emit(self.signals.failed, exc)
        else:
            self._emit(self.signals.done, result)

    @staticmethod
    def _emit(signal, value: Any) -> None:
        # The receiver may be gone when the app quits while a task is still running.
        with contextlib.suppress(RuntimeError):
            signal.emit(value)


# Keep the signal objects alive until their task has reported back.
_pending: set[TaskSignals] = set()


def run_async(
    fn: Callable[[], Any],
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    *,
    owner: QObject | None = None,
) -> TaskSignals:
    """Run ``fn`` in a worker thread; the callbacks run in the GUI thread.

    With ``owner``, the callbacks are skipped once that object has been deleted.
    """
    signals = TaskSignals()
    _pending.add(signals)

    def finish(callback: Callable[[Any], None] | None, value: Any) -> None:
        _pending.discard(signals)
        if owner is not None and not shiboken6.isValid(owner):
            return
        if callback is not None:
            callback(value)

    signals.done.connect(lambda result: finish(on_done, result))
    signals.failed.connect(lambda exc: finish(on_error, exc))
    QThreadPool.globalInstance().start(_Task(fn, signals))
    return signals
