"""Choose which items of a playlist or channel to download."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from easy_ytdlp.core.probe import MediaInfo
from easy_ytdlp.core.selection import SelectionError, format_ranges, parse_ranges
from easy_ytdlp.gui import formatting
from easy_ytdlp.gui.widgets.common import button, label, set_state


class ItemPicker(QFrame):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.summary = label("", "SectionTitle")
        self.all_button = button(self.tr("Select all"), variant="ghost")
        self.none_button = button(self.tr("Select none"), variant="ghost")
        top.addWidget(self.summary, 1)
        top.addWidget(self.all_button)
        top.addWidget(self.none_button)
        layout.addLayout(top)

        filters = QHBoxLayout()
        ranges_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr("Search titles"))
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName(self.tr("Search titles"))
        self.ranges = QLineEdit()
        self.ranges.setPlaceholderText(self.tr("Items, e.g. 1-5, 8, 10-"))
        self.ranges.setAccessibleName(self.tr("Item ranges"))
        self.apply_ranges = button(self.tr("Select"), "list-checks")
        search_label = label(self.tr("Search"), "Muted")
        search_label.setBuddy(self.search)
        ranges_label = label(self.tr("Items"), "Muted")
        ranges_label.setBuddy(self.ranges)
        filters.addWidget(search_label)
        filters.addWidget(self.search, 1)
        ranges_row.addWidget(ranges_label)
        ranges_row.addWidget(self.ranges, 1)
        ranges_row.addWidget(self.apply_ranges)
        layout.addLayout(filters)
        layout.addLayout(ranges_row)
        self.range_error = label("", "ErrorText")
        self.range_error.hide()
        layout.addWidget(self.range_error)

        self.list = QListWidget()
        self.list.setMinimumHeight(220)
        self.list.setUniformItemSizes(True)
        layout.addWidget(self.list)
        self.note = label("", "Caption", wrap=True)
        layout.addWidget(self.note)

        self._total = 0
        self.all_button.clicked.connect(lambda: self._check_all(True))
        self.none_button.clicked.connect(lambda: self._check_all(False))
        self.search.textChanged.connect(self._filter)
        self.apply_ranges.clicked.connect(self._apply_ranges)
        self.ranges.returnPressed.connect(self._apply_ranges)
        self.list.itemChanged.connect(lambda _item: self._update_summary())
        self.hide()

    def set_info(self, info: MediaInfo | None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        self.search.clear()
        self.ranges.clear()
        self.range_error.hide()
        if info is None or not info.is_collection:
            self.list.blockSignals(False)
            self._total = 0
            self.hide()
            return
        for entry in info.entries:
            text = f"{entry.index}. {entry.title}"
            if entry.duration:
                text += f"  ·  {formatting.duration(entry.duration)}"
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, entry.index)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._total = len(info.entries)
        listed = info.count or self._total
        self.note.setVisible(listed > self._total)
        self.note.setText(
            self.tr("Only the first {shown} of {count} items were listed.").format(
                shown=self._total, count=listed
            )
        )
        self._update_summary()
        self.show()

    def _items(self) -> list[QListWidgetItem]:
        return [self.list.item(i) for i in range(self.list.count())]

    def selected_indices(self) -> list[int]:
        return [
            int(item.data(Qt.ItemDataRole.UserRole))
            for item in self._items()
            if item.checkState() == Qt.CheckState.Checked
        ]

    def playlist_items(self) -> str:
        """The ``-I`` value; empty when everything is selected (download the whole list)."""
        selected = self.selected_indices()
        if not self._total or len(selected) == self._total:
            return ""
        return format_ranges(selected)

    def has_selection(self) -> bool:
        return not self._total or bool(self.selected_indices())

    def _check_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.list.blockSignals(True)
        for item in self._items():
            if not item.isHidden():
                item.setCheckState(state)
        self.list.blockSignals(False)
        self._update_summary()

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for item in self._items():
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _apply_ranges(self) -> None:
        try:
            wanted = parse_ranges(self.ranges.text(), self._total)
        except SelectionError:
            set_state(self.ranges, "invalid", "true")
            self.range_error.setText(self.tr("Use numbers and ranges like 1-5, 8, 10-."))
            self.range_error.show()
            return
        set_state(self.ranges, "invalid", "false")
        self.range_error.hide()
        self.list.blockSignals(True)
        for item in self._items():
            index = int(item.data(Qt.ItemDataRole.UserRole))
            item.setCheckState(
                Qt.CheckState.Checked if index in wanted else Qt.CheckState.Unchecked
            )
        self.list.blockSignals(False)
        self._update_summary()

    def _update_summary(self) -> None:
        self.summary.setText(
            self.tr("{selected} of {total} items selected").format(
                selected=len(self.selected_indices()), total=self._total
            )
        )
        self.changed.emit()
