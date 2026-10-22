"""Small building blocks shared by the pages."""

from collections.abc import Sequence

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from easy_ytdlp.gui.theme import icons


def label(text: str = "", name: str = "", *, wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    # yt-dlp output and titles are untrusted: never interpret them as rich text.
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


def button(
    text: str = "",
    icon_name: str = "",
    *,
    variant: str = "",
    tooltip: str = "",
    icon_role: str = "",
) -> QPushButton:
    widget = QPushButton(text)
    if variant:
        widget.setProperty("variant", variant)
    if icon_name:
        role = icon_role or ("on_primary" if variant == "primary" else "foreground")
        icons.bind(widget, icon_name, role, 16)
    if tooltip:
        widget.setToolTip(tooltip)
    if not text:
        widget.setAccessibleName(tooltip)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    return widget


def icon_button(icon_name: str, tooltip: str, *, role: str = "foreground") -> QToolButton:
    """Icon-only button; always with a tooltip and an accessible name."""
    widget = QToolButton()
    widget.setProperty("variant", "ghost")
    icons.bind(widget, icon_name, role, 18)
    widget.setToolTip(tooltip)
    widget.setAccessibleName(tooltip)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    return widget


def card(layout_cls=QVBoxLayout) -> tuple[QFrame, QVBoxLayout | QHBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = layout_cls(frame)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(12)
    return frame, layout


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setObjectName("Muted")
    return line


def set_state(widget: QWidget, name: str, value: str) -> None:
    """Change a dynamic property used by the stylesheet and re-polish the widget."""
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class SegmentedControl(QFrame):
    """Mutually exclusive options shown as joined buttons."""

    changed = Signal(str)

    def __init__(self, options: Sequence[tuple[str, str, str]], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._buttons: dict[str, QPushButton] = {}
        for key, text, icon_name in options:
            item = QPushButton(text)
            item.setCheckable(True)
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            item.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            if icon_name:
                icons.bind(item, icon_name, "foreground", 16)
            self._group.addButton(item)
            self._buttons[key] = item
            layout.addWidget(item)
            item.toggled.connect(lambda checked, key=key: checked and self.changed.emit(key))
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def value(self) -> str:
        for key, item in self._buttons.items():
            if item.isChecked():
                return key
        return ""

    def set_value(self, key: str) -> None:
        if key in self._buttons:
            self._buttons[key].setChecked(True)

    def button(self, key: str) -> QPushButton:
        return self._buttons[key]


class FolderPicker(QWidget):
    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.edit = QLineEdit()
        self.browse = button(self.tr("Browse…"), "folder-open")
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.browse)
        self.browse.clicked.connect(self._pick)
        self.edit.textChanged.connect(self.changed)

    def text(self) -> str:
        return self.edit.text().strip()

    def set_text(self, value: str) -> None:
        self.edit.setText(value)

    def _pick(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self.tr("Choose a folder"), self.text())
        if folder:
            self.edit.setText(folder.replace("/", "\\"))


class Collapsible(QWidget):
    """A header button that shows or hides its content."""

    def __init__(self, title: str, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.header = QToolButton()
        self.header.setText(title)
        self.header.setProperty("variant", "ghost")
        self.header.setCheckable(True)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.content = content
        layout.addWidget(self.header, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(content)
        self.header.toggled.connect(self.set_expanded)
        self.set_expanded(False)

    def set_expanded(self, expanded: bool) -> None:
        if self.header.isChecked() != expanded:
            self.header.setChecked(expanded)
        icons.bind(self.header, "chevron-down" if expanded else "chevron-right", "foreground", 16)
        self.content.setVisible(expanded)

    def is_expanded(self) -> bool:
        return self.header.isChecked()


class Toast(QLabel):
    """A short, non-blocking confirmation at the bottom of a window."""

    DURATION_MS = 2500

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(180)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str) -> None:
        self.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 32)
        self.raise_()
        self.show()
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._timer.start(self.DURATION_MS)
