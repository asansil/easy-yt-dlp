"""Download page: URL, analysis, the main options and the "Show command" panel."""

import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from easy_ytdlp.core import command_builder, paths
from easy_ytdlp.core.options import (
    AUDIO_BITRATES,
    AUDIO_FORMATS,
    LOSSLESS_AUDIO_FORMATS,
    VIDEO_CONTAINERS,
    VIDEO_QUALITIES,
    DownloadOptions,
    Mode,
    validate,
)
from easy_ytdlp.core.presets import PresetError
from easy_ytdlp.core.probe import MediaInfo
from easy_ytdlp.gui import messages
from easy_ytdlp.gui.context import AppContext
from easy_ytdlp.gui.controllers.probe_controller import ProbeController
from easy_ytdlp.gui.pages.base import Page
from easy_ytdlp.gui.widgets.common import (
    Collapsible,
    FolderPicker,
    SegmentedControl,
    button,
    card,
    icon_button,
    label,
    set_state,
)
from easy_ytdlp.gui.widgets.item_picker import ItemPicker
from easy_ytdlp.gui.widgets.media_card import MediaCard
from easy_ytdlp.gui.widgets.option_sections import (
    AdvancedSection,
    ClipSection,
    OutputSection,
    SubtitleSection,
)

URL_RE = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)
ANALYZE_DELAY_MS = 500


def looks_like_url(text: str) -> bool:
    return bool(URL_RE.match(text))


class DownloadPage(Page):
    def __init__(
        self,
        ctx: AppContext,
        probe: ProbeController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(self.tr("Download"), parent)
        self.ctx = ctx
        self.probe = probe or ProbeController(parent=self)
        self.info: MediaInfo | None = None
        self._analyzed_url = ""
        self._loading = False
        self.options = DownloadOptions.from_dict(ctx.settings.last_options)
        default_name = ctx.settings.default_preset
        default = ctx.presets.get(default_name) if default_name else None
        if default is not None:
            self.options = default.options.copy()
        if not self.options.output.folder:
            self.options.output.folder = str(ctx.settings.effective_download_dir())

        self._build_url_row()
        self.card = MediaCard()
        self.body.addWidget(self.card)
        self.picker = ItemPicker()
        self.picker.changed.connect(self._refresh)
        self.body.addWidget(self.picker)
        self._build_options()
        self._build_sections()
        self._build_footer()
        self.body.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(ANALYZE_DELAY_MS)
        self._timer.timeout.connect(self._auto_analyze)

        self.probe.started.connect(self._on_probe_started)
        self.probe.finished.connect(self._on_probe_finished)
        self.probe.failed.connect(self._on_probe_failed)

        QShortcut(QKeySequence("Ctrl+Return"), self, self.download)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self.download)
        paste = QShortcut(QKeySequence.StandardKey.Paste, self, self.paste_and_analyze)
        paste.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        ctx.options_requested.connect(self.set_options)
        ctx.presets_changed.connect(self._fill_presets)

        self._load_options()
        self._refresh()

    # -- construction -------------------------------------------------------------------

    def _build_url_row(self) -> None:
        self.url_label = label(self.tr("Video, playlist or channel URL"), "Muted")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.url = QLineEdit()
        self.url.setObjectName("UrlInput")
        self.url.setPlaceholderText("https://")
        self.url.setClearButtonEnabled(True)
        self.url_label.setBuddy(self.url)
        self.paste_button = icon_button("clipboard-paste", self.tr("Paste and analyze"))
        self.analyze_button = button(self.tr("Analyze"), "search")
        row.addWidget(self.url, 1)
        row.addWidget(self.paste_button)
        row.addWidget(self.analyze_button)
        self.body.addWidget(self.url_label)
        self.body.addLayout(row)

        self.url.textChanged.connect(self._on_url_changed)
        self.url.returnPressed.connect(self.analyze)
        self.paste_button.clicked.connect(self.paste_and_analyze)
        self.analyze_button.clicked.connect(self.analyze)

    def _combo(self, items: list[tuple[str, str]]) -> QComboBox:
        combo = QComboBox()
        for value, text in items:
            combo.addItem(text, value)
        combo.currentIndexChanged.connect(self._read_controls)
        return combo

    def _build_options(self) -> None:
        frame, layout = card()
        top = QHBoxLayout()
        self.mode = SegmentedControl(
            [
                (Mode.VIDEO.value, self.tr("Video"), "video"),
                (Mode.AUDIO.value, self.tr("Audio"), "music"),
                (Mode.SUBTITLES.value, self.tr("Subtitles"), "captions"),
            ]
        )
        self.mode.changed.connect(self._read_controls)
        preset_label = label(self.tr("Preset"), "Muted")
        self.preset = QComboBox()
        preset_label.setBuddy(self.preset)
        self.save_preset_button = icon_button("star", self.tr("Save as preset"))
        top.addWidget(preset_label)
        top.addWidget(self.preset, 1)
        top.addWidget(self.save_preset_button)
        layout.addLayout(top)
        layout.addWidget(self.mode)
        self._fill_presets()
        self.preset.activated.connect(self._apply_preset)
        self.save_preset_button.clicked.connect(self.save_preset)

        self.mode_stack = QStackedWidget()
        video = QWidget()
        video_form = QFormLayout(video)
        video_form.setContentsMargins(0, 0, 0, 0)
        self.quality = self._combo(self._quality_items(None))
        self.container = self._combo([(c, c.upper()) for c in VIDEO_CONTAINERS])
        video_form.addRow(self.tr("Quality"), self.quality)
        video_form.addRow(self.tr("Format"), self.container)
        self.mode_stack.addWidget(video)

        audio = QWidget()
        audio_form = QFormLayout(audio)
        audio_form.setContentsMargins(0, 0, 0, 0)
        self.audio_format = self._combo(
            [
                (f, self.tr("Original (no conversion)") if f == "best" else f.upper())
                for f in AUDIO_FORMATS
            ]
        )
        self.bitrate = self._combo(
            [
                (
                    b,
                    self.tr("Best (VBR)")
                    if b == "best"
                    else self.tr("{rate} kbit/s").format(rate=b),
                )
                for b in AUDIO_BITRATES
            ]
        )
        audio_form.addRow(self.tr("Format"), self.audio_format)
        audio_form.addRow(self.tr("Quality"), self.bitrate)
        self.mode_stack.addWidget(audio)

        self.mode_stack.addWidget(
            label(
                self.tr("Only the subtitles are downloaded; choose the languages below."),
                "Muted",
                wrap=True,
            )
        )
        layout.addWidget(self.mode_stack)

        folder_form = QFormLayout()
        folder_form.setContentsMargins(0, 0, 0, 0)
        self.folder = FolderPicker()
        self.folder.changed.connect(self._read_controls)
        folder_form.addRow(self.tr("Save to"), self.folder)
        layout.addLayout(folder_form)
        self.body.addWidget(frame)

    def _build_sections(self) -> None:
        frame, layout = card()
        self.subtitles = SubtitleSection()
        self.clip = ClipSection()
        self.output = OutputSection()
        self.advanced = AdvancedSection()
        self.sections = [self.subtitles, self.clip, self.output, self.advanced]
        self.subtitles_box = Collapsible(self.tr("Subtitles"), self.subtitles)
        self.clip_box = Collapsible(self.tr("Clip"), self.clip)
        self.output_box = Collapsible(self.tr("File name and folders"), self.output)
        self.advanced_box = Collapsible(self.tr("Advanced"), self.advanced)
        for box in (self.subtitles_box, self.clip_box, self.output_box, self.advanced_box):
            layout.addWidget(box)
        for section in self.sections:
            section.changed.connect(self._read_controls)
        self.body.addWidget(frame)

    def _build_footer(self) -> None:
        self.error = label("", "ErrorText", wrap=True)
        self.error.hide()
        self.body.addWidget(self.error)

        row = QHBoxLayout()
        self.download_button = button(self.tr("Download"), "download", variant="primary")
        self.download_button.setToolTip(self.tr("Download (Ctrl+Enter)"))
        self.queue_button = button(self.tr("Add to queue"), "plus")
        row.addWidget(self.download_button)
        row.addWidget(self.queue_button)
        row.addStretch(1)
        self.body.addLayout(row)
        self.download_button.clicked.connect(self.download)
        self.queue_button.clicked.connect(lambda: self.enqueue(navigate=False))

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        self.command_view = QPlainTextEdit()
        self.command_view.setObjectName("CommandView")
        self.command_view.setReadOnly(True)
        self.command_view.setMaximumHeight(110)
        self.command_view.setAccessibleName(self.tr("yt-dlp command"))
        actions = QHBoxLayout()
        self.copy_button = button(self.tr("Copy"), "copy")
        self.edit_button = button(self.tr("Edit in command mode"), "terminal")
        actions.addWidget(self.copy_button)
        actions.addWidget(self.edit_button)
        actions.addStretch(1)
        panel_layout.addWidget(self.command_view)
        panel_layout.addLayout(actions)
        self.command_section = Collapsible(self.tr("Show command"), panel)
        self.body.addWidget(self.command_section)
        self.copy_button.clicked.connect(self._copy_command)
        self.edit_button.clicked.connect(self._edit_command)

    # -- options <-> controls -----------------------------------------------------------

    def _quality_items(self, heights: list[int] | None) -> list[tuple[str, str]]:
        values = [q for q in VIDEO_QUALITIES if q != "best"]
        if heights:
            values = [str(h) for h in heights]
        items = [("best", self.tr("Best available"))]
        items += [(v, f"{v}p") for v in values]
        return items

    @staticmethod
    def _select(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index < 0:
            combo.addItem(value, value)
            index = combo.count() - 1
        combo.setCurrentIndex(index)

    def _load_options(self) -> None:
        """Put ``self.options`` into the controls."""
        self._loading = True
        try:
            o = self.options
            self.mode.set_value(o.mode.value)
            self._select(self.quality, o.format.quality)
            self._select(self.container, o.format.container)
            self._select(self.audio_format, o.audio.format)
            self._select(self.bitrate, o.audio.bitrate)
            self.folder.set_text(o.output.folder)
            for section in self.sections:
                section.load(o)
        finally:
            self._loading = False

    def _read_controls(self, *_args: object) -> None:
        if self._loading:
            return
        o = self.options
        o.mode = Mode(self.mode.value() or Mode.VIDEO.value)
        o.format.quality = self.quality.currentData() or "best"
        o.format.container = self.container.currentData() or "mp4"
        o.audio.format = self.audio_format.currentData() or "mp3"
        o.audio.bitrate = self.bitrate.currentData() or "192"
        o.output.folder = self.folder.text()
        for section in self.sections:
            section.read(o)
        self._refresh()

    def set_options(self, options: DownloadOptions) -> None:
        folder = self.options.output.folder
        self.options = options.copy()
        if not self.options.output.folder:
            self.options.output.folder = folder
        if not self.options.output.folder:
            self.options.output.folder = str(self.ctx.settings.effective_download_dir())
        self._load_options()
        self._refresh()

    def _refresh(self) -> None:
        mode = self.options.mode
        self.mode_stack.setCurrentIndex([Mode.VIDEO, Mode.AUDIO, Mode.SUBTITLES].index(mode))
        self.subtitles.set_mode(mode)
        self.advanced.set_mode(mode)
        if mode == Mode.SUBTITLES:
            self.subtitles_box.set_expanded(True)
        self.clip_box.setEnabled(mode != Mode.SUBTITLES)
        self.output.update_preview(self.options)
        lossless = self.options.audio.format in LOSSLESS_AUDIO_FORMATS | {"best"}
        self.bitrate.setEnabled(not lossless)
        self.command_view.setPlainText(self.command_text())
        self._show_error("")

    # -- analysis -----------------------------------------------------------------------

    def _on_url_changed(self, text: str) -> None:
        set_state(self.url, "invalid", "false")
        if looks_like_url(text) and text.strip() != self._analyzed_url:
            self._timer.start()
        self.command_view.setPlainText(self.command_text())

    def _auto_analyze(self) -> None:
        if looks_like_url(self.url.text()):
            self.analyze()

    def paste_and_analyze(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        if text:
            self.url.setText(text)
            self.analyze()
        self.url.setFocus()

    def analyze(self) -> None:
        self._timer.stop()
        url = self.url.text().strip()
        if not url:
            return
        if not looks_like_url(url):
            set_state(self.url, "invalid", "true")
            self._show_error(
                self.tr("This does not look like a web address (http:// or https://).")
            )
            return
        if not paths.ytdlp_exe().is_file():
            self._show_error(self._missing_tools_text())
            return
        self._analyzed_url = url
        self.probe.analyze(url)

    def _set_info(self, info: MediaInfo | None) -> None:
        self.info = info
        self.picker.set_info(info)
        self.subtitles.set_info(info)
        self.output.set_info(info)
        self.output.update_preview(self.options)

    def _on_probe_started(self, url: str) -> None:
        self._set_info(None)
        self.card.show_loading(url)
        self.analyze_button.setEnabled(False)
        self.analyze_button.setText(self.tr("Analyzing…"))

    def _on_probe_finished(self, url: str, info: MediaInfo) -> None:
        self._end_busy()
        self._set_info(info)
        self.card.show_info(info)
        current = self.options.format.quality
        self._loading = True
        self.quality.clear()
        for value, text in self._quality_items(info.heights):
            self.quality.addItem(text, value)
        self._loading = False
        self._select(self.quality, current if self.quality.findData(current) >= 0 else "best")
        self._read_controls()

    def _on_probe_failed(self, url: str, message: str, details: str) -> None:
        self._end_busy()
        self._set_info(None)
        self.card.show_error(message, details)

    def _end_busy(self) -> None:
        self.analyze_button.setEnabled(True)
        self.analyze_button.setText(self.tr("Analyze"))

    # -- actions ------------------------------------------------------------------------

    def _missing_tools_text(self) -> str:
        return self.tr("yt-dlp is not installed yet. Install the tools first (banner above).")

    def _show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    def urls(self) -> list[str]:
        url = self.url.text().strip()
        return [url] if url else []

    def playlist_items(self) -> str:
        return self.picker.playlist_items() if self.picker.isVisibleTo(self) else ""

    def build_argv(self) -> list[str]:
        return self.ctx.queue.build_argv(
            self.options, self.urls() or ["URL"], playlist_items=self.playlist_items()
        )

    def command_text(self) -> str:
        return command_builder.to_display(self.build_argv())

    def download(self) -> None:
        self.enqueue(navigate=True)

    def enqueue(self, *, navigate: bool) -> bool:
        urls = self.urls()
        if not urls:
            set_state(self.url, "invalid", "true")
            self._show_error(self.tr("Paste a URL first."))
            self.url.setFocus()
            return False
        if not looks_like_url(urls[0]):
            set_state(self.url, "invalid", "true")
            self._show_error(
                self.tr("This does not look like a web address (http:// or https://).")
            )
            return False
        if self.picker.isVisibleTo(self) and not self.picker.has_selection():
            self._show_error(self.tr("Select at least one item of the list."))
            return False
        duration = self.info.duration if self.info else None
        errors = validate(self.options, duration)
        if errors:
            self._show_error(messages.validation(errors[0]))
            return False
        if not paths.ytdlp_exe().is_file():
            self._show_error(self._missing_tools_text())
            return False
        info = self.info if self.info and self._analyzed_url == urls[0] else None
        self.ctx.queue.add_download(
            self.options,
            urls,
            info.title if info else urls[0],
            playlist_items=self.playlist_items(),
            thumbnail=info.thumbnail if info else None,
        )
        self.ctx.settings.last_options = self.options.to_dict()
        self.ctx.save_settings()
        self.ctx.toast_requested.emit(self.tr("Added to the queue"))
        if navigate:
            self.ctx.page_requested.emit("queue")
        return True

    def _copy_command(self) -> None:
        QGuiApplication.clipboard().setText(self.command_text())
        self.ctx.toast_requested.emit(self.tr("Command copied"))

    def _edit_command(self) -> None:
        self.ctx.command_requested.emit(self.command_text())
        self.ctx.page_requested.emit("command")

    # -- presets ------------------------------------------------------------------------

    def _fill_presets(self) -> None:
        self.preset.blockSignals(True)
        self.preset.clear()
        self.preset.addItem(self.tr("Choose a preset…"), "")
        for preset in self.ctx.presets.all():
            self.preset.addItem(messages.preset_name(preset.name), preset.name)
        self.preset.setCurrentIndex(0)
        self.preset.blockSignals(False)

    def _apply_preset(self, index: int) -> None:
        name = self.preset.itemData(index)
        preset = self.ctx.presets.get(name) if name else None
        if preset is not None:
            self.set_options(preset.options)
            self.ctx.toast_requested.emit(
                self.tr("Preset applied: {name}").format(name=messages.preset_name(name))
            )
        self.preset.setCurrentIndex(0)

    def ask_preset_name(self, suggestion: str) -> str | None:
        """Ask for a preset name (replaced in tests)."""
        name, ok = QInputDialog.getText(
            self, self.tr("Save as preset"), self.tr("Preset name"), text=suggestion
        )
        return name if ok else None

    def save_preset(self) -> bool:
        name = self.ask_preset_name(self.ctx.presets.unique_name(self.tr("My preset")))
        if not name or not name.strip():
            return False
        options = self.options.copy()
        # Presets do not pin a folder; they use the current destination when applied.
        options.output.folder = ""
        existing = self.ctx.presets.get(name.strip())
        try:
            if existing is not None and not existing.builtin:
                self.ctx.presets.save(name, options, overwrite=True)
            else:
                self.ctx.presets.save(name, options)
        except PresetError:
            self._show_error(self.tr("Choose another name: that one is already used."))
            return False
        self.ctx.presets_changed.emit()
        self.ctx.toast_requested.emit(self.tr("Preset saved"))
        return True
