"""Theme: tokens, stylesheet, fonts, icons and light/dark switching."""

import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from easy_ytdlp.gui.theme import icons, stylesheet
from easy_ytdlp.gui.theme.tokens import DARK, LIGHT, Tokens

RESOURCES = Path(__file__).resolve().parents[2] / "resources"
FONTS = RESOURCES / "fonts"

THEMES = ("system", "light", "dark")


def load_fonts() -> None:
    for font in sorted(FONTS.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(font))


def system_is_dark() -> bool:
    hints = QGuiApplication.styleHints()
    return hints.colorScheme() == Qt.ColorScheme.Dark


def _palette(tokens: Tokens) -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: tokens.background,
        QPalette.ColorRole.WindowText: tokens.foreground,
        QPalette.ColorRole.Base: tokens.surface_muted,
        QPalette.ColorRole.AlternateBase: tokens.surface,
        QPalette.ColorRole.Text: tokens.foreground,
        QPalette.ColorRole.Button: tokens.surface,
        QPalette.ColorRole.ButtonText: tokens.foreground,
        QPalette.ColorRole.Highlight: tokens.primary,
        QPalette.ColorRole.HighlightedText: tokens.on_primary,
        QPalette.ColorRole.ToolTipBase: tokens.surface,
        QPalette.ColorRole.ToolTipText: tokens.foreground,
        QPalette.ColorRole.PlaceholderText: tokens.muted_foreground,
        QPalette.ColorRole.Link: tokens.primary,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(tokens.muted_foreground)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(tokens.muted_foreground),
    )
    return palette


class ThemeManager(QObject):
    """Applies the chosen theme and follows the Windows setting when it is "system"."""

    changed = Signal(object)

    def __init__(self, mode: str = "system", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._mode = mode if mode in THEMES else "system"
        self.tokens: Tokens = LIGHT
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_system_change)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_dark(self) -> bool:
        return self.tokens is DARK

    def set_mode(self, mode: str) -> None:
        self._mode = mode if mode in THEMES else "system"
        self.apply()

    def apply(self) -> None:
        dark = system_is_dark() if self._mode == "system" else self._mode == "dark"
        self.tokens = DARK if dark else LIGHT
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyle("Fusion")
            app.setPalette(_palette(self.tokens))
            app.setStyleSheet(stylesheet.build(self.tokens))
        icons.set_tokens(self.tokens)
        self.changed.emit(self.tokens)

    def _on_system_change(self, *_args: object) -> None:
        if self._mode == "system":
            self.apply()


def animations_enabled() -> bool:
    """False when Windows "Animation effects" (Accessibility > Visual effects) is off."""
    if sys.platform != "win32":
        return True
    spi_getclientareaanimation = 0x1042
    value = ctypes.c_int(1)
    ok = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
        spi_getclientareaanimation, 0, ctypes.byref(value), 0
    )
    return bool(value.value) if ok else True
