"""Keep the mouse wheel from changing closed drop-downs and spin boxes while a page scrolls."""

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox


class WheelGuard(QObject):
    """Application-wide event filter: wheel events skip value widgets and reach their parents.

    Ignoring the event and filtering it out makes Qt pass it on to the parent widgets, so
    the surrounding scroll area scrolls. An open drop-down list is a separate widget and
    still scrolls normally.
    """

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel and isinstance(obj, QComboBox | QAbstractSpinBox):
            event.ignore()
            return True
        return False


def install(app: QApplication) -> WheelGuard:
    """Install the guard on ``app`` once; later calls return the same guard."""
    guard = app.findChild(WheelGuard)
    if guard is None:
        guard = WheelGuard(app)
        app.installEventFilter(guard)
    return guard
