"""Build the .ico files and PNG masters from the SVG masters in docs/images/icon/.

uv run python scripts/make_icons.py

Frames of 32 px and below drop the elements marked class="detail" (the ">_dlp" text),
which turn into noise at that size.
"""

import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "docs" / "images" / "icon"
TARGETS = {
    "app": ROOT / "src" / "easy_ytdlp" / "resources" / "app.ico",
    "installer": ROOT / "packaging" / "inno" / "installer.ico",
}
SIZES = (16, 24, 32, 48, 64, 128, 256)
SIMPLE_MAX = 32
MASTER_SIZE = 1024
SVG_NS = "http://www.w3.org/2000/svg"


def svg_bytes(path: Path, *, simple: bool) -> bytes:
    ET.register_namespace("", SVG_NS)
    tree = ET.parse(path)
    if simple:
        for parent in tree.iter():
            for child in list(parent):
                if child.get("class") == "detail":
                    parent.remove(child)
    return ET.tostring(tree.getroot())


def render(svg: bytes, size: int) -> QImage:
    renderer = QSvgRenderer(QByteArray(svg))
    if not renderer.isValid():
        raise ValueError("invalid SVG")
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def png(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def ico(frames: list[tuple[int, bytes]]) -> bytes:
    """An ICO file with PNG-compressed frames (Windows Vista and later)."""
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = len(header) + 16 * len(frames)
    entries, payload = b"", b""
    for size, data in frames:
        side = 0 if size >= 256 else size  # 0 means 256
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)
    return header + entries + payload


def main() -> int:
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    for name, target in TARGETS.items():
        master = MASTERS / f"{name}.svg"
        full = svg_bytes(master, simple=False)
        simple = svg_bytes(master, simple=True)
        frames = [
            (size, png(render(simple if size <= SIMPLE_MAX else full, size))) for size in SIZES
        ]
        target.write_bytes(ico(frames))
        render(full, MASTER_SIZE).save(str(MASTERS / f"{name}.png"))
        print(f"Wrote {target.relative_to(ROOT)} and {name}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
