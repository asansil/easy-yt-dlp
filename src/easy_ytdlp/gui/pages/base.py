"""Common page layout: a title and a centered, scrollable column."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from easy_ytdlp.gui.widgets.common import label

MAX_CONTENT_WIDTH = 1100


class Page(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(32, 24, 32, 32)
        column = QWidget()
        column.setMaximumWidth(MAX_CONTENT_WIDTH)
        # Tiny side stretches center the column once it reaches its maximum width.
        row.addStretch(1)
        row.addWidget(column, 1000)
        row.addStretch(1)
        scroll.setWidget(holder)

        self.body = QVBoxLayout(column)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(16)
        self.header = QHBoxLayout()
        self.title = label(title, "PageTitle")
        self.header.addWidget(self.title, 1)
        self.body.addLayout(self.header)
