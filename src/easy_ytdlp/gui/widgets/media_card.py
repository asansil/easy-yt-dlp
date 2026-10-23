"""Card that shows the analyzed URL: thumbnail, title, uploader, duration and type."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from easy_ytdlp.core.probe import MediaInfo, MediaKind
from easy_ytdlp.gui import formatting
from easy_ytdlp.gui.widgets.common import button, label
from easy_ytdlp.gui.widgets.thumbnails import loader

THUMB_WIDTH = 192
THUMB_HEIGHT = 108


class MediaCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT)
        self.thumb.setObjectName("Thumb")
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.thumb, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(6)
        self.badge = label("", "AccentBadge")
        self.title = label("", "SectionTitle", wrap=True)
        self.meta = label("", "Muted", wrap=True)
        self.details_button = button(self.tr("Show details"), variant="ghost")
        self.details = QPlainTextEdit()
        self.details.setObjectName("Console")
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(140)
        self.details.hide()
        self.details_button.clicked.connect(
            lambda: self.details.setVisible(not self.details.isVisible())
        )
        text.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignLeft)
        text.addWidget(self.title)
        text.addWidget(self.meta)
        text.addWidget(self.details_button, 0, Qt.AlignmentFlag.AlignLeft)
        text.addWidget(self.details)
        text.addStretch(1)
        layout.addLayout(text, 1)
        self._url = ""
        self.hide()

    def _reset(self) -> None:
        self.thumb.clear()
        self.badge.hide()
        self.details_button.hide()
        self.details.hide()
        self.details.clear()
        self.title.setObjectName("SectionTitle")
        self.title.style().polish(self.title)

    def show_loading(self, url: str) -> None:
        self._url = url
        self._reset()
        self.title.setText(self.tr("Analyzing…"))
        self.meta.setText(url)
        self.show()

    def show_error(self, message: str, details: str) -> None:
        self._reset()
        self.title.setObjectName("ErrorText")
        self.title.style().polish(self.title)
        self.title.setText(self.tr("This URL could not be analyzed"))
        self.meta.setText(message)
        if details.strip():
            self.details.setPlainText(details)
            self.details_button.show()
        self.show()

    def show_info(self, info: MediaInfo) -> None:
        self._reset()
        self._url = info.url
        if info.kind == MediaKind.VIDEO:
            self.badge.setText(self.tr("Video"))
        elif info.kind == MediaKind.PLAYLIST:
            self.badge.setText(self.tr("Playlist · {count} items").format(count=info.count or 0))
        else:
            self.badge.setText(self.tr("Channel · {count} items").format(count=info.count or 0))
        self.badge.show()
        self.title.setText(info.title)
        parts = [p for p in (info.uploader, formatting.duration(info.duration)) if p]
        self.meta.setText(" · ".join(parts))
        url = info.url
        loader().load(info.thumbnail, lambda pixmap: self._set_thumb(url, pixmap), self)
        self.show()

    def _set_thumb(self, url: str, pixmap: QPixmap) -> None:
        if url != self._url:
            return
        self.thumb.setPixmap(
            pixmap.scaled(
                THUMB_WIDTH,
                THUMB_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
