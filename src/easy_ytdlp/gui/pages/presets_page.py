"""Presets page: list, apply, duplicate, rename, delete and choose the default."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QWidget,
)

from easy_ytdlp.core.options import DownloadOptions, Mode
from easy_ytdlp.core.presets import Preset, PresetError
from easy_ytdlp.gui import messages
from easy_ytdlp.gui.context import AppContext
from easy_ytdlp.gui.pages.base import Page
from easy_ytdlp.gui.widgets.common import button, label


class PresetsPage(Page):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(self.tr("Presets"), parent)
        self.ctx = ctx
        # Preset to select after the next refresh (e.g. after a rename).
        self._select_next = ""
        self.body.addWidget(
            label(
                self.tr(
                    "Presets save a set of download options. Built-in presets cannot be "
                    "changed, but you can duplicate them. Save new presets from the Download page."
                ),
                "Muted",
                wrap=True,
            )
        )
        self.list = QListWidget()
        self.list.setMinimumHeight(320)
        self.body.addWidget(self.list, 1)
        self.summary = label("", "Caption", wrap=True)
        self.body.addWidget(self.summary)

        actions = QHBoxLayout()
        self.apply_button = button(self.tr("Use"), "check", variant="primary")
        self.default_button = button(self.tr("Make default"), "star")
        self.duplicate_button = button(self.tr("Duplicate"), "copy")
        self.rename_button = button(self.tr("Rename"), "pencil")
        self.delete_button = button(self.tr("Delete"), "trash-2", variant="destructive")
        for widget in (
            self.apply_button,
            self.default_button,
            self.duplicate_button,
            self.rename_button,
            self.delete_button,
        ):
            actions.addWidget(widget)
        actions.addStretch(1)
        self.body.addLayout(actions)

        self.list.currentItemChanged.connect(self._update_actions)
        self.list.itemDoubleClicked.connect(lambda *_: self.apply())
        self.apply_button.clicked.connect(self.apply)
        self.default_button.clicked.connect(self.toggle_default)
        self.duplicate_button.clicked.connect(self.duplicate)
        self.rename_button.clicked.connect(self.rename)
        self.delete_button.clicked.connect(self.delete)
        ctx.presets_changed.connect(self.refresh)
        self.refresh()

    def describe(self, options: DownloadOptions) -> str:
        if options.mode == Mode.AUDIO:
            fmt = (
                options.audio.format.upper()
                if options.audio.format != "best"
                else self.tr("original format")
            )
            text = self.tr("Audio · {format}").format(format=fmt)
        elif options.mode == Mode.SUBTITLES:
            text = self.tr("Subtitles · {languages}").format(
                languages=", ".join(options.subtitles.languages)
            )
        else:
            quality = (
                self.tr("best quality")
                if options.format.quality == "best"
                else f"{options.format.quality}p"
            )
            text = self.tr("Video · {quality} · {container}").format(
                quality=quality, container=options.format.container.upper()
            )
        if options.mode != Mode.SUBTITLES and options.subtitles.enabled:
            text += " · " + self.tr("subtitles")
        return text

    def refresh(self) -> None:
        current = self._select_next or (self.selected().name if self.selected() else "")
        self._select_next = ""
        self.list.clear()
        for preset in self.ctx.presets.all():
            name = messages.preset_name(preset.name)
            if preset.name == self.ctx.settings.default_preset:
                name += " ★"
            suffix = self.tr("built-in") if preset.builtin else self.tr("yours")
            item = QListWidgetItem(f"{name}\n{self.describe(preset.options)} · {suffix}")
            item.setData(Qt.ItemDataRole.UserRole, preset.name)
            self.list.addItem(item)
            if preset.name == current:
                self.list.setCurrentItem(item)
        self._update_actions()

    def selected(self) -> Preset | None:
        item = self.list.currentItem()
        return self.ctx.presets.get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _update_actions(self, *_args: object) -> None:
        preset = self.selected()
        has = preset is not None
        editable = has and not preset.builtin
        for widget in (self.apply_button, self.default_button, self.duplicate_button):
            widget.setEnabled(has)
        self.rename_button.setEnabled(editable)
        self.delete_button.setEnabled(editable)
        is_default = has and preset.name == self.ctx.settings.default_preset
        self.default_button.setText(
            self.tr("Remove as default") if is_default else self.tr("Make default")
        )
        self.summary.setText(
            self.tr("The default preset is loaded when Easy yt-dlp starts.") if has else ""
        )

    def apply(self) -> None:
        preset = self.selected()
        if preset is not None:
            self.ctx.options_requested.emit(preset.options)
            self.ctx.page_requested.emit("download")

    def toggle_default(self) -> None:
        preset = self.selected()
        if preset is None:
            return
        same = self.ctx.settings.default_preset == preset.name
        self.ctx.settings.default_preset = "" if same else preset.name
        self.ctx.save_settings()
        self.refresh()

    def ask_name(self, title: str, suggestion: str) -> str | None:
        """Ask for a preset name (replaced in tests)."""
        name, ok = QInputDialog.getText(self, title, self.tr("Preset name"), text=suggestion)
        return name if ok else None

    def confirm_delete(self, name: str) -> bool:
        answer = QMessageBox.question(
            self,
            self.tr("Delete preset"),
            self.tr("Delete the preset “{name}”?").format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _run(self, action) -> None:
        try:
            action()
        except PresetError:
            self.summary.setText(self.tr("Choose another name: that one is already used."))
            return
        self.ctx.presets_changed.emit()

    def duplicate(self) -> None:
        preset = self.selected()
        if preset is None:
            return
        base = self.tr("{name} (copy)").format(name=messages.preset_name(preset.name))
        name = self.ask_name(self.tr("Duplicate preset"), self.ctx.presets.unique_name(base))
        if name and name.strip():

            def action() -> None:
                self._select_next = self.ctx.presets.duplicate(preset.name, name).name

            self._run(action)

    def rename(self) -> None:
        preset = self.selected()
        if preset is None or preset.builtin:
            return
        name = self.ask_name(self.tr("Rename preset"), preset.name)
        if name and name.strip():
            old = preset.name

            def action() -> None:
                renamed = self.ctx.presets.rename(old, name)
                self._select_next = renamed.name
                if self.ctx.settings.default_preset == old:
                    self.ctx.settings.default_preset = renamed.name
                    self.ctx.save_settings()

            self._run(action)

    def delete(self) -> None:
        preset = self.selected()
        if preset is None or preset.builtin or not self.confirm_delete(preset.name):
            return
        if self.ctx.settings.default_preset == preset.name:
            self.ctx.settings.default_preset = ""
            self.ctx.save_settings()
        self._run(lambda: self.ctx.presets.delete(preset.name))
