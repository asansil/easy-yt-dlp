"""Main window. Minimal walking skeleton; the full layout arrives in M3."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow

from easy_ytdlp import __version__


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.tr("Easy yt-dlp"))
        self.setMinimumSize(960, 640)
        label = QLabel(self.tr("Easy yt-dlp {version}").format(version=__version__))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(label)
