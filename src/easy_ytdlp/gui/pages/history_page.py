"""History page: search past downloads, open them, download them again."""

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from easy_ytdlp.core import command_builder, paths, progress
from easy_ytdlp.core.history import HistoryEntry
from easy_ytdlp.core.options import DownloadOptions
from easy_ytdlp.core.queue import JobState
from easy_ytdlp.gui import formatting
from easy_ytdlp.gui.context import AppContext
from easy_ytdlp.gui.pages.base import Page
from easy_ytdlp.gui.widgets.common import button, label
from easy_ytdlp.gui.widgets.job_row import STATE_SYMBOL, state_text


class HistoryPage(Page):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(self.tr("History"), parent)
        self.ctx = ctx
        self.clear_button = button(self.tr("Clear history"), "trash-2", variant="destructive")
        self.header.addWidget(self.clear_button)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr("Search by title or URL"))
        self.search.setAccessibleName(self.tr("Search by title or URL"))
        self.search.setClearButtonEnabled(True)
        self.state = QComboBox()
        self.state.setAccessibleName(self.tr("Filter by state"))
        self.state.addItem(self.tr("All"), "")
        for state in (JobState.DONE, JobState.FAILED, JobState.CANCELLED):
            self.state.addItem(state_text(state), state.value)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.state)
        self.body.addLayout(filters)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([self.tr("Title"), self.tr("State"), self.tr("Date")])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setMinimumHeight(360)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, self.tree.header().ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, self.tree.header().ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, self.tree.header().ResizeMode.ResizeToContents)
        self.body.addWidget(self.tree, 1)
        self.detail = label("", "Caption", wrap=True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.addWidget(self.detail)

        actions = QHBoxLayout()
        self.again_button = button(self.tr("Download again"), "rotate-ccw", variant="primary")
        self.load_button = button(self.tr("Load options"), "sliders-horizontal")
        self.open_file_button = button(self.tr("Open file"), "external-link")
        self.open_folder_button = button(self.tr("Open folder"), "folder-open")
        self.remove_button = button(self.tr("Remove"), "x")
        for widget in (
            self.again_button,
            self.load_button,
            self.open_file_button,
            self.open_folder_button,
            self.remove_button,
        ):
            actions.addWidget(widget)
        actions.addStretch(1)
        self.body.addLayout(actions)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(self._timer.start)
        self.state.currentIndexChanged.connect(self.refresh)
        self.tree.currentItemChanged.connect(self._update_actions)
        self.tree.itemDoubleClicked.connect(lambda *_: self.open_file())
        self.again_button.clicked.connect(self.download_again)
        self.load_button.clicked.connect(self.load_options)
        self.open_file_button.clicked.connect(self.open_file)
        self.open_folder_button.clicked.connect(self.open_folder)
        self.remove_button.clicked.connect(self.remove)
        self.clear_button.clicked.connect(self.clear)
        ctx.history_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        selected = self.current()
        self.tree.clear()
        for entry in self.ctx.history.search(
            self.search.text(), state=self.state.currentData() or ""
        ):
            state = JobState(entry.state) if entry.state in JobState else JobState.DONE
            item = QTreeWidgetItem(
                [
                    entry.title,
                    f"{STATE_SYMBOL[state]} {state_text(state)}",
                    formatting.timestamp(entry.finished_at),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, entry.id)
            item.setToolTip(0, entry.url)
            self.tree.addTopLevelItem(item)
            if selected is not None and entry.id == selected.id:
                self.tree.setCurrentItem(item)
        self._update_actions()

    def current(self) -> HistoryEntry | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        return self.ctx.history.get(int(item.data(0, Qt.ItemDataRole.UserRole)))

    def _update_actions(self, *_args: object) -> None:
        entry = self.current()
        has = entry is not None
        files = [f for f in (entry.files if entry else []) if Path(f).exists()]
        self.again_button.setEnabled(has and entry.rerunnable)
        self.load_button.setEnabled(has and entry.options is not None)
        self.open_file_button.setEnabled(bool(files))
        self.open_folder_button.setEnabled(has and Path(entry.output_dir).is_dir())
        self.remove_button.setEnabled(has)
        if entry is None:
            self.detail.setText("")
            return
        lines = [entry.url] if entry.url else []
        if entry.args is not None:
            lines.append(command_builder.to_display(["yt-dlp", *entry.args]))
        lines += entry.files
        if entry.error:
            lines.append(entry.error)
        self.detail.setText("\n".join(lines))

    def download_again(self) -> None:
        entry = self.current()
        if entry is None or not entry.rerunnable:
            return
        if not paths.ytdlp_exe().is_file():
            self.ctx.toast_requested.emit(self.tr("yt-dlp is not installed yet."))
            return
        if entry.options is not None:
            self.ctx.queue.add_download(
                DownloadOptions.from_dict(entry.options), [entry.url], entry.title
            )
        else:
            argv = [str(paths.ytdlp_exe()), *progress.MACHINE_FLAGS, *(entry.args or [])]
            self.ctx.queue.add_command(argv, entry.title, entry.output_dir)
        self.ctx.toast_requested.emit(self.tr("Added to the queue"))

    def load_options(self) -> None:
        entry = self.current()
        if entry is None or entry.options is None:
            return
        self.ctx.options_requested.emit(DownloadOptions.from_dict(entry.options))
        self.ctx.page_requested.emit("download")

    def open_file(self) -> None:
        entry = self.current()
        files = [f for f in (entry.files if entry else []) if Path(f).exists()]
        if files:
            QDesktopServices.openUrl(QUrl.fromLocalFile(files[-1]))

    def open_folder(self) -> None:
        entry = self.current()
        if entry is None:
            return
        files = [f for f in entry.files if Path(f).exists()]
        if files:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(files[-1])])
        elif Path(entry.output_dir).is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(entry.output_dir))

    def remove(self) -> None:
        entry = self.current()
        if entry is not None:
            self.ctx.history.delete(entry.id)
            self.refresh()

    def confirm_clear(self) -> bool:
        """Ask before clearing the history (replaced in tests)."""
        answer = QMessageBox.question(
            self,
            self.tr("Clear history"),
            self.tr("Remove every entry from the history? Downloaded files are kept."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def clear(self) -> None:
        if self.ctx.history.count() and self.confirm_clear():
            self.ctx.history.clear()
            self.refresh()
