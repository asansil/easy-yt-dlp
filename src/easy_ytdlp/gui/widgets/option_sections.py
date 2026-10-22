"""Groups of download options: subtitles, clip, output and advanced settings.

Each section shows part of a ``DownloadOptions`` and writes it back: ``load(options)``
fills the controls, ``read(options)`` stores the controls, ``changed`` fires on edits.
"""

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
    parse_time,
    template_escapes_folder,
)
from easy_ytdlp.core.probe import MediaInfo
from easy_ytdlp.gui.widgets.common import button, label, set_state


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
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.enabled = QCheckBox(self.tr("Download only a part (clip)"))
        layout.addWidget(self.enabled)
        self.fields = QWidget()
        row = QHBoxLayout(self.fields)
        row.setContentsMargins(0, 0, 0, 0)
        self.start = QLineEdit()
        self.start.setPlaceholderText("0:00")
        self.end = QLineEdit()
        self.end.setPlaceholderText(self.tr("end"))
        start_label = label(self.tr("From"))
        start_label.setBuddy(self.start)
        end_label = label(self.tr("to"))
        end_label.setBuddy(self.end)
        self.keyframes = QCheckBox(self.tr("Precise cuts (slower, re-encodes)"))
        row.addWidget(start_label)
        row.addWidget(self.start)
        row.addWidget(end_label)
        row.addWidget(self.end)
        row.addWidget(self.keyframes)
        row.addStretch(1)
        layout.addWidget(self.fields)
        self.hint = label(self.tr("Times as h:mm:ss, m:ss or seconds."), "Caption")
        layout.addWidget(self.hint)
        self._watch(self.enabled, self.start, self.end, self.keyframes)
        self.enabled.toggled.connect(self._update)
        self.start.textChanged.connect(self._validate)
        self.end.textChanged.connect(self._validate)
        self._update()

    def _update(self) -> None:
        self.fields.setEnabled(self.enabled.isChecked())
        self.hint.setVisible(self.enabled.isChecked())

    def _validate(self) -> None:
        for edit in (self.start, self.end):
            text = edit.text().strip()
            set_state(edit, "invalid", "true" if text and parse_time(text) is None else "false")

    def load(self, options: DownloadOptions) -> None:
        self._loading = True
        clip = options.clip
        self.enabled.setChecked(clip.enabled)
        self.start.setText(clip.start)
        self.end.setText(clip.end)
        self.keyframes.setChecked(clip.force_keyframes)
        self._loading = False
        self._update()

    def read(self, options: DownloadOptions) -> None:
        clip = options.clip
        clip.enabled = self.enabled.isChecked()
        clip.start = self.start.text().strip()
        clip.end = self.end.text().strip()
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
