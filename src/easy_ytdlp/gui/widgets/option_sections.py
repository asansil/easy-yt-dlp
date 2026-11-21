"""Groups of download options: subtitles, clip, output and advanced settings.

Each section shows part of a ``DownloadOptions`` and writes it back: ``load(options)``
fills the controls, ``read(options)`` stores the controls, ``changed`` fires on edits.
"""

import math

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from easy_ytdlp.core import command_builder, template_preview
from easy_ytdlp.core.options import (
    BROWSERS,
    DEFAULT_TEMPLATE,
    SPONSORBLOCK_CATEGORIES,
    SUBTITLE_FORMATS,
    DownloadOptions,
    Mode,
    Organize,
    SponsorBlock,
    format_hms,
    format_time,
    parse_time,
    template_escapes_folder,
)
from easy_ytdlp.core.probe import MediaInfo
from easy_ytdlp.gui.widgets.common import button, label, set_state
from easy_ytdlp.gui.widgets.time_input import TimeInput


class Section(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loading = False

    def _emit(self, *_args: object) -> None:
        if not self._loading:
            self.changed.emit()

    def _watch(self, *widgets: QWidget) -> None:
        for widget in widgets:
            if isinstance(widget, QCheckBox):
                widget.toggled.connect(self._emit)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._emit)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._emit)

    @staticmethod
    def _select(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)


class SubtitleSection(Section):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.enabled = QCheckBox(self.tr("Download subtitles"))
        layout.addWidget(self.enabled)
        self.fields = QWidget()
        form = QFormLayout(self.fields)
        form.setContentsMargins(0, 0, 0, 0)
        self.languages = QLineEdit()
        self.languages.setPlaceholderText(self.tr("e.g. en, es, all"))
        self.available = label("", "Caption", wrap=True)
        self.auto = QCheckBox(self.tr("Include auto-generated subtitles"))
        self.embed = QCheckBox(self.tr("Embed in the video file"))
        self.format = QComboBox()
        for value in SUBTITLE_FORMATS:
            self.format.addItem(value.upper(), value)
        form.addRow(self.tr("Languages"), self.languages)
        form.addRow("", self.available)
        form.addRow("", self.auto)
        form.addRow("", self.embed)
        form.addRow(self.tr("File format"), self.format)
        layout.addWidget(self.fields)
        self._watch(self.enabled, self.languages, self.auto, self.embed, self.format)
        self.enabled.toggled.connect(self._update)
        self.embed.toggled.connect(self._update)
        self._mode = Mode.VIDEO

    def set_mode(self, mode: Mode) -> None:
        self._mode = mode
        self._update()

    def set_info(self, info: MediaInfo | None) -> None:
        if info is None or info.is_collection:
            self.available.setText("")
            return
        langs = ", ".join(info.subtitles) or self.tr("none")
        self.available.setText(
            self.tr("Available: {languages} · {auto} auto-generated").format(
                languages=langs, auto=len(info.auto_captions)
            )
        )

    def _update(self) -> None:
        forced = self._mode == Mode.SUBTITLES
        self.enabled.setVisible(not forced)
        self.fields.setEnabled(forced or self.enabled.isChecked())
        self.embed.setVisible(self._mode == Mode.VIDEO)
        embedded = self._mode == Mode.VIDEO and self.embed.isChecked()
        self.format.setEnabled(not embedded)

    def load(self, options: DownloadOptions) -> None:
        self._loading = True
        subs = options.subtitles
        self.enabled.setChecked(subs.enabled)
        self.languages.setText(", ".join(subs.languages))
        self.auto.setChecked(subs.auto_generated)
        self.embed.setChecked(subs.embed)
        self._select(self.format, subs.format)
        self._loading = False
        self.set_mode(options.mode)

    def read(self, options: DownloadOptions) -> None:
        subs = options.subtitles
        subs.enabled = self.enabled.isChecked()
        subs.languages = [part.strip() for part in self.languages.text().split(",") if part.strip()]
        subs.auto_generated = self.auto.isChecked()
        subs.embed = self.embed.isChecked()
        subs.format = self.format.currentData() or "srt"


class ClipSection(Section):
    """Clip range as two "HH:MM:SS" fields; the end defaults to "to the end"."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._duration: int | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.enabled = QCheckBox(self.tr("Download only a part (clip)"))
        layout.addWidget(self.enabled)
        self.fields = QWidget()
        fields = QVBoxLayout(self.fields)
        fields.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.start = TimeInput(self.tr("Clip start"))
        self.end = TimeInput(self.tr("Clip end"))
        self.to_end = QCheckBox(self.tr("To the end"))
        self.to_end.setChecked(True)
        start_label = label(self.tr("From"))
        start_label.setBuddy(self.start)
        end_label = label(self.tr("to"))
        end_label.setBuddy(self.end)
        self.keyframes = QCheckBox(self.tr("Precise cuts (slower, re-encodes)"))
        self.length = label("", "Caption")
        row.addWidget(start_label)
        row.addWidget(self.start)
        row.addWidget(end_label)
        row.addWidget(self.end)
        row.addWidget(self.to_end)
        row.addSpacing(12)
        row.addWidget(self.keyframes)
        row.addStretch(1)
        fields.addLayout(row)
        fields.addWidget(self.length)
        layout.addWidget(self.fields)
        self._watch(self.enabled, self.to_end, self.keyframes)
        self.start.valueChanged.connect(self._emit)
        self.end.valueChanged.connect(self._emit)
        self.enabled.toggled.connect(self._update)
        self.to_end.toggled.connect(self._on_to_end)
        self.start.valueChanged.connect(self._refresh)
        self.end.valueChanged.connect(self._refresh)
        self._update()

    def set_info(self, info: MediaInfo | None) -> None:
        """Limit the times to the duration of one analyzed video (not of a playlist)."""
        known = info is not None and not info.is_collection and info.duration
        self._duration = math.ceil(info.duration) if known else None
        # The start must leave something to download.
        self.start.setMaximum(self._duration - 1 if self._duration else None)
        self.end.setMaximum(self._duration)
        self._refresh()

    def _on_to_end(self, checked: bool) -> None:
        if not checked and self.end.value() == 0 and self._duration:
            self.end.setValue(self._duration)
        self._update()

    def _update(self) -> None:
        self.fields.setEnabled(self.enabled.isChecked())
        self.end.setEnabled(not self.to_end.isChecked())
        self._refresh()

    def _refresh(self) -> None:
        """Show the clip length and flag an end that is not after the start."""
        start, end = self.start.value(), self.end.value()
        bad_range = not self.to_end.isChecked() and end <= start
        set_state(self.end, "invalid", "true" if bad_range else "false")
        if bad_range:
            text = self.tr("The end must be after the start.")
        elif self.to_end.isChecked():
            text = (
                self.tr("Clip length: {time} (to the end)").format(
                    time=format_time(self._duration - start)
                )
                if self._duration
                else ""
            )
        else:
            text = self.tr("Clip length: {time}").format(time=format_time(end - start))
        self.length.setText(text)
        self.length.setVisible(bool(text))

    def load(self, options: DownloadOptions) -> None:
        self._loading = True
        clip = options.clip
        self.enabled.setChecked(clip.enabled)
        # Stored as "HH:MM:SS"; older values ("1:30", "90.5") still parse.
        start = parse_time(clip.start) if clip.start.strip() else None
        end = parse_time(clip.end) if clip.end.strip() else None
        self.start.setValue(math.floor(start or 0))
        self.end.setValue(math.ceil(end) if end is not None else 0)
        self.to_end.setChecked(end is None)
        self.keyframes.setChecked(clip.force_keyframes)
        self._loading = False
        self._update()

    def read(self, options: DownloadOptions) -> None:
        clip = options.clip
        clip.enabled = self.enabled.isChecked()
        start = self.start.value()
        clip.start = format_hms(start) if start else ""
        clip.end = "" if self.to_end.isChecked() else format_hms(self.end.value())
        clip.force_keyframes = self.keyframes.isChecked()


TEMPLATE_TOKENS = [
    ("title", "%(title)s"),
    ("id", "%(id)s"),
    ("uploader", "%(uploader)s"),
    ("upload_date", "%(upload_date>%Y-%m-%d)s"),
    ("playlist_index", "%(playlist_index)03d"),
    ("playlist_title", "%(playlist_title)s"),
    ("resolution", "%(resolution)s"),
    ("ext", "%(ext)s"),
]


class OutputSection(Section):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        template_row = QHBoxLayout()
        self.template = QLineEdit()
        self.template.setObjectName("CommandInput")
        self.reset = button(self.tr("Reset"), "rotate-ccw", variant="ghost")
        template_row.addWidget(self.template, 1)
        template_row.addWidget(self.reset)
        chips = QGridLayout()
        chips.setSpacing(4)
        for position, (name, token) in enumerate(TEMPLATE_TOKENS):
            chip = button(name, variant="ghost")
            chip.setToolTip(self.tr("Insert {token}").format(token=token))
            chip.clicked.connect(lambda _=False, token=token: self.template.insert(token))
            chips.addWidget(chip, position // 4, position % 4)
        chips.setColumnStretch(4, 1)
        self.organize = QComboBox()
        for value, text in (
            (Organize.NONE, self.tr("No subfolders")),
            (Organize.UPLOADER, self.tr("A folder per uploader")),
            (Organize.PLAYLIST, self.tr("A folder per playlist")),
            (Organize.UPLOADER_PLAYLIST, self.tr("Uploader, then playlist")),
        ):
            self.organize.addItem(text, value.value)
        self.preview = label("", "Muted", wrap=True)
        self.warning = label("", "WarningText", wrap=True)
        form.addRow(self.tr("File name"), template_row)
        form.addRow("", chips)
        form.addRow(self.tr("Subfolders"), self.organize)
        form.addRow(self.tr("Preview"), self.preview)
        form.addRow("", self.warning)
        self._watch(self.template, self.organize)
        self.reset.clicked.connect(lambda: self.template.setText(DEFAULT_TEMPLATE))
        self._fields: dict[str, object] = {}

    def set_info(self, info: MediaInfo | None) -> None:
        self._fields = {}
        if info is not None:
            self._fields["uploader"] = info.uploader
            self._fields["channel"] = info.uploader
            if info.is_collection:
                self._fields["playlist_title"] = info.title
                self._fields["playlist_index"] = 1
                if info.entries:
                    self._fields["title"] = info.entries[0].title
                    self._fields["id"] = info.entries[0].id
            else:
                self._fields["title"] = info.title
                self._fields["id"] = info.id

    def update_preview(self, options: DownloadOptions) -> None:
        template = command_builder.output_template(options)
        folder = options.output.folder.rstrip("\\/")
        name = template_preview.preview(options, template, self._fields)
        self.preview.setText(f"{folder}\\{name}" if folder else name)
        escapes = template_escapes_folder(options.output.template)
        self.warning.setText(
            self.tr("This template would save files outside the chosen folder.") if escapes else ""
        )
        self.warning.setVisible(escapes)

    def load(self, options: DownloadOptions) -> None:
        self._loading = True
        self.template.setText(options.output.template)
        self._select(self.organize, options.output.organize.value)
        self._loading = False

    def read(self, options: DownloadOptions) -> None:
        options.output.template = self.template.text()
        options.output.organize = Organize(self.organize.currentData() or Organize.NONE.value)


class AdvancedSection(Section):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)

        self.cookies = QComboBox()
        self.cookies.addItem(self.tr("Do not use cookies"), "")
        for browser in BROWSERS:
            self.cookies.addItem(browser.capitalize(), browser)
        cookies_hint = label(
            self.tr(
                "Use your browser's login for private or age-restricted videos. "
                "yt-dlp reads the cookies at download time; Easy yt-dlp never stores them."
            ),
            "Caption",
            wrap=True,
        )
        form.addRow(self.tr("Cookies from"), self.cookies)
        form.addRow("", cookies_hint)

        embeds = QHBoxLayout()
        self.metadata = QCheckBox(self.tr("Metadata"))
        self.thumbnail = QCheckBox(self.tr("Thumbnail"))
        self.chapters = QCheckBox(self.tr("Chapters"))
        embeds.addWidget(self.metadata)
        embeds.addWidget(self.thumbnail)
        embeds.addWidget(self.chapters)
        embeds.addStretch(1)
        form.addRow(self.tr("Embed"), embeds)

        self.sponsorblock = QComboBox()
        self.sponsorblock.addItem(self.tr("Off"), SponsorBlock.OFF.value)
        self.sponsorblock.addItem(self.tr("Remove segments"), SponsorBlock.REMOVE.value)
        self.sponsorblock.addItem(self.tr("Mark as chapters"), SponsorBlock.MARK.value)
        form.addRow(self.tr("SponsorBlock"), self.sponsorblock)
        self.categories_box = QWidget()
        grid = QGridLayout(self.categories_box)
        grid.setContentsMargins(0, 0, 0, 0)
        names = {
            "sponsor": self.tr("Sponsor"),
            "intro": self.tr("Intro"),
            "outro": self.tr("Outro"),
            "selfpromo": self.tr("Self-promotion"),
            "preview": self.tr("Preview"),
            "filler": self.tr("Filler"),
            "interaction": self.tr("Interaction reminder"),
            "music_offtopic": self.tr("Non-music section"),
        }
        self.categories: dict[str, QCheckBox] = {}
        for position, category in enumerate(SPONSORBLOCK_CATEGORIES):
            box = QCheckBox(names[category])
            self.categories[category] = box
            grid.addWidget(box, position // 4, position % 4)
        form.addRow("", self.categories_box)

        self.rate = QLineEdit()
        self.rate.setPlaceholderText(self.tr("Unlimited (e.g. 2M or 500K)"))
        form.addRow(self.tr("Rate limit"), self.rate)
        self.archive = QCheckBox(self.tr("Skip videos downloaded before (download archive)"))
        form.addRow("", self.archive)
        self.extra = QLineEdit()
        self.extra.setObjectName("CommandInput")
        self.extra.setPlaceholderText("--sleep-interval 5")
        form.addRow(self.tr("Extra arguments"), self.extra)

        self._watch(
            self.cookies,
            self.metadata,
            self.thumbnail,
            self.chapters,
            self.sponsorblock,
            self.rate,
            self.archive,
            self.extra,
            *self.categories.values(),
        )
        self.sponsorblock.currentIndexChanged.connect(self._update)

    def _update(self) -> None:
        self.categories_box.setEnabled(self.sponsorblock.currentData() != SponsorBlock.OFF.value)

    def set_mode(self, mode: Mode) -> None:
        self.chapters.setEnabled(mode == Mode.VIDEO)

    def load(self, options: DownloadOptions) -> None:
        self._loading = True
        adv = options.advanced
        self._select(self.cookies, adv.cookies_browser)
        self.metadata.setChecked(adv.embed_metadata)
        self.thumbnail.setChecked(adv.embed_thumbnail)
        self.chapters.setChecked(adv.embed_chapters)
        self._select(self.sponsorblock, adv.sponsorblock.value)
        for category, box in self.categories.items():
            box.setChecked(category in adv.sponsorblock_categories)
        self.rate.setText(adv.rate_limit)
        self.archive.setChecked(adv.use_archive)
        self.extra.setText(adv.extra_args)
        self._loading = False
        self._update()
        self.set_mode(options.mode)

    def read(self, options: DownloadOptions) -> None:
        adv = options.advanced
        adv.cookies_browser = self.cookies.currentData() or ""
        adv.embed_metadata = self.metadata.isChecked()
        adv.embed_thumbnail = self.thumbnail.isChecked()
        adv.embed_chapters = self.chapters.isChecked()
        adv.sponsorblock = SponsorBlock(self.sponsorblock.currentData() or SponsorBlock.OFF.value)
        adv.sponsorblock_categories = [c for c, box in self.categories.items() if box.isChecked()]
        adv.rate_limit = self.rate.text().strip()
        adv.use_archive = self.archive.isChecked()
        adv.extra_args = self.extra.text()
