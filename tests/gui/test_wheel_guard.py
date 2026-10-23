import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox, QScrollArea, QVBoxLayout, QWidget

from easy_ytdlp.gui import wheel_guard


def page_with_combo(qtbot) -> tuple[QScrollArea, QComboBox]:
    content = QWidget()
    layout = QVBoxLayout(content)
    combo = QComboBox()
    combo.addItems(["one", "two", "three"])
    combo.setCurrentIndex(1)
    layout.addWidget(combo)
    layout.addSpacing(3000)
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(content)
    area.resize(300, 200)
    qtbot.addWidget(area)
    area.show()
    return area, combo


def scroll_down(widget: QWidget) -> QWheelEvent:
    pos = QPointF(widget.rect().center())
    event = QWheelEvent(
        pos,
        QPointF(widget.mapToGlobal(pos.toPoint())),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)
    return event


def test_without_guard_the_wheel_changes_the_combo(qtbot) -> None:
    _, combo = page_with_combo(qtbot)
    assert scroll_down(combo).isAccepted()
    assert combo.currentIndex() == 2


@pytest.fixture
def guard(qapp):
    guard = wheel_guard.install(qapp)
    yield guard
    qapp.removeEventFilter(guard)
    guard.setParent(None)
    guard.deleteLater()


def test_wheel_over_combo_is_left_for_the_page(qtbot, guard) -> None:
    _, combo = page_with_combo(qtbot)
    event = scroll_down(combo)
    assert combo.currentIndex() == 1
    # Ignored, so Qt passes a real (spontaneous) wheel event on to the scroll area.
    # Synthetic events are never propagated, so the scrolling itself is checked by hand.
    assert not event.isAccepted()


def test_install_is_idempotent(qapp, guard) -> None:
    assert wheel_guard.install(qapp) is guard
