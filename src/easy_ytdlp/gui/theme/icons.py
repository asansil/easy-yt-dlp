"""Lucide SVG icons recolored from the design tokens at runtime."""

import tempfile
import weakref
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from easy_ytdlp.gui.theme.tokens import LIGHT, Tokens

ICONS = Path(__file__).resolve().parents[2] / "resources" / "icons"
_tokens: Tokens = LIGHT
# Widgets whose icon follows the theme: widget -> (name, role, size).
_bound: "weakref.WeakKeyDictionary[object, tuple[str, str, int]]" = weakref.WeakKeyDictionary()


def set_tokens(tokens: Tokens) -> None:
    global _tokens
    _tokens = tokens
    _render.cache_clear()
    for widget, (name, role, size) in list(_bound.items()):
        try:
            widget.setIcon(icon(name, role, size))
        except RuntimeError:
            # The C++ object is already gone.
            _bound.pop(widget, None)


@lru_cache(maxsize=512)
def _render(name: str, color: str, size: int, ratio: float) -> QPixmap:
    svg = (ICONS / f"{name}.svg").read_text(encoding="utf-8").replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixels = round(size * ratio)
    pixmap = QPixmap(pixels, pixels)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def icon(name: str, role: str = "foreground", size: int = 18) -> QIcon:
    """An icon colored with a token (``foreground``, ``primary``, ``on_primary``...)."""
    color = getattr(_tokens, role)
    result = QIcon()
    for ratio in (1.0, 1.5, 2.0):
        result.addPixmap(_render(name, color, size, ratio))
    disabled = _render(name, _tokens.muted_foreground, size, 2.0)
    result.addPixmap(disabled, QIcon.Mode.Disabled)
    return result


def icon_size(size: int = 18) -> QSize:
    return QSize(size, size)


def bind(widget, name: str, role: str = "foreground", size: int = 18) -> None:
    """Set an icon on a button or action and keep it in sync with theme changes."""
    _bound[widget] = (name, role, size)
    widget.setIcon(icon(name, role, size))
    if hasattr(widget, "setIconSize"):
        widget.setIconSize(icon_size(size))


def icon_file(name: str, color: str) -> str:
    """Path of a recolored copy of an icon, for stylesheet ``url()`` references."""
    folder = Path(tempfile.gettempdir()) / "easy-ytdlp-icons"
    folder.mkdir(exist_ok=True)
    target = folder / f"{name}-{color.lstrip('#').lower()}.svg"
    if not target.exists():
        svg = (ICONS / f"{name}.svg").read_text(encoding="utf-8").replace("currentColor", color)
        target.write_text(svg, encoding="utf-8")
    return target.as_posix()
