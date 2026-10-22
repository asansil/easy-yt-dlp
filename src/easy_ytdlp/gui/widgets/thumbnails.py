"""Asynchronous, cached thumbnail loading."""

from collections.abc import Callable

import shiboken6
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

MAX_CACHE = 200


class ThumbnailLoader(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._network = QNetworkAccessManager(self)
        self._cache: dict[str, QPixmap] = {}

    def load(self, url: str | None, callback: Callable[[QPixmap], None], receiver: QObject) -> None:
        """Call ``callback`` with the image while ``receiver`` is alive; nothing happens for
        missing or broken images."""
        if not url or not url.lower().startswith("https://"):
            return
        if url in self._cache:
            callback(self._cache[url])
            return
        request = QNetworkRequest(QUrl(url))
        request.setTransferTimeout(15000)
        reply = self._network.get(request)

        def finished() -> None:
            reply.deleteLater()
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            pixmap = QPixmap()
            if pixmap.loadFromData(reply.readAll()) and not pixmap.isNull():
                if len(self._cache) >= MAX_CACHE:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[url] = pixmap
                if shiboken6.isValid(receiver):
                    callback(pixmap)

        reply.finished.connect(finished)


_loader: ThumbnailLoader | None = None


def loader() -> ThumbnailLoader:
    global _loader
    if _loader is None:
        _loader = ThumbnailLoader()
    return _loader
