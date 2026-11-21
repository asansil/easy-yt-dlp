"""Time entry as one "HH:MM:SS" field: the ":" are fixed and typing moves through the parts."""

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QLineEdit, QWidget

from easy_ytdlp.core.options import format_hms, parse_time

# Two hour digits.
MAX_SECONDS = 99 * 3600 + 59 * 60 + 59

_DIGITS = (0, 1, 3, 4, 6, 7)  # positions of the digits in "HH:MM:SS"
_SECTION_STARTS = (0, 3, 6)
_CANONICAL = re.compile(r"\d\d:[0-5]\d:[0-5]\d")
_NAVIGATION = {
    Qt.Key.Key_Left,
    Qt.Key.Key_Right,
    Qt.Key.Key_Home,
    Qt.Key.Key_End,
    Qt.Key.Key_Tab,
    Qt.Key.Key_Backtab,
    Qt.Key.Key_Return,
    Qt.Key.Key_Enter,
    Qt.Key.Key_Escape,
}


class TimeInput(QLineEdit):
    """Whole seconds typed as ``HH:MM:SS``, limited to an optional maximum.

    Typing overwrites one digit at a time and skips the ":". Two digits finish a part; in
    the minutes and seconds a first digit of 6-9 cannot start a two-digit value below 60,
    so it is read as ``0X`` and the cursor moves on. Up and Down change the part under the
    cursor, with carry-over. Pasted text such as "1:30" or "90" is converted.
    """

    valueChanged = Signal(int)

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._maximum = MAX_SECONDS
        self._value = 0
        self.setAccessibleName(name)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(False)
        self.setText(format_hms(0))
        self.setFixedWidth(self.fontMetrics().horizontalAdvance("00:00:00") + 40)
        self.textChanged.connect(self._on_text_changed)
        self.editingFinished.connect(self._normalize)

    # -- value -------------------------------------------------------------------------

    def value(self) -> int:
        return self._value

    def maximum(self) -> int:
        return self._maximum

    def setValue(self, seconds: int) -> None:
        value = min(max(0, int(seconds)), self._maximum)
        cursor = self.cursorPosition()
        self.setText(format_hms(value))
        self.setCursorPosition(min(cursor, 8))
        self._set(value)

    def setMaximum(self, seconds: int | None) -> None:
        """Limit the time; ``None`` lifts the limit. A larger current value is clamped."""
        self._maximum = MAX_SECONDS if seconds is None else min(max(0, seconds), MAX_SECONDS)
        if self._value > self._maximum:
            self.setValue(self._maximum)

    def _set(self, value: int) -> None:
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)

    def _on_text_changed(self, text: str) -> None:
        if _CANONICAL.fullmatch(text):
            hours, minutes, seconds = (int(part) for part in text.split(":"))
            self._set(min(hours * 3600 + minutes * 60 + seconds, self._maximum))
            return
        # Text from outside the key handling (context-menu paste, undo): convert or undo.
        parsed = parse_time(text)
        self.setValue(int(parsed) if parsed is not None else self._value)

    def _normalize(self) -> None:
        """Show the clamped value once editing ends (a typed time may exceed the maximum)."""
        if self.text() != format_hms(self._value):
            self.setValue(self._value)

    # -- typing ------------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        text = event.text()
        if event.matches(QKeySequence.StandardKey.Paste):
            parsed = parse_time(QGuiApplication.clipboard().text())
            if parsed is not None:
                self.setValue(int(parsed))
        elif event.matches(QKeySequence.StandardKey.Copy) or event.matches(
            QKeySequence.StandardKey.SelectAll
        ):
            super().keyPressEvent(event)
        elif text.isdigit() and text.isascii():
            self._type_digit(int(text))
        elif key == Qt.Key.Key_Backspace:
            self._erase(backwards=True)
        elif key == Qt.Key.Key_Delete:
            self._erase(backwards=False)
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self._step(1 if key == Qt.Key.Key_Up else -1)
        elif text in {":", ".", ",", " "}:
            self._jump_to_next_part()
        elif key in _NAVIGATION:
            super().keyPressEvent(event)
        # Anything else (letters, cut, undo) would break the format: ignored.

    def _digit_position(self) -> int | None:
        """Where the next digit goes: the selection start or the cursor, past any ":"."""
        if self.hasSelectedText() and len(self.selectedText()) == len(self.text()):
            self.setText(format_hms(0))
            return 0
        pos = self.selectionStart() if self.hasSelectedText() else self.cursorPosition()
        return next((p for p in _DIGITS if p >= pos), None)

    def _type_digit(self, digit: int) -> None:
        pos = self._digit_position()
        if pos is None:
            return
        chars = list(self.text())
        if pos in (3, 6) and digit >= 6:
            chars[pos : pos + 2] = ["0", str(digit)]
            after = pos + 3
        else:
            chars[pos] = str(digit)
            after = pos + 1 if pos % 3 == 0 else pos + 2
        self._replace("".join(chars), min(after, 8))

    def _erase(self, *, backwards: bool) -> None:
        pos = self.cursorPosition()
        if backwards:
            target = next((p for p in reversed(_DIGITS) if p < pos), None)
        else:
            target = next((p for p in _DIGITS if p >= pos), None)
        if target is None:
            return
        chars = list(self.text())
        chars[target] = "0"
        self._replace("".join(chars), target if backwards else min(target + 1, 8))

    def _replace(self, text: str, cursor: int) -> None:
        self.setText(text)
        self.setCursorPosition(cursor)

    def _step(self, direction: int) -> None:
        pos = self.cursorPosition()
        unit = 3600 if pos <= 2 else 60 if pos <= 5 else 1
        self.setValue(self._value + direction * unit)
        self.setCursorPosition(pos)

    def _jump_to_next_part(self) -> None:
        pos = self.cursorPosition()
        self.setCursorPosition(next((p for p in _SECTION_STARTS if p > pos), 8))
