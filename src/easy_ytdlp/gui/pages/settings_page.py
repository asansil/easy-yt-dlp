"""Settings page."""

from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget

from easy_ytdlp.gui.context import AppContext
from easy_ytdlp.gui.pages.base import Page
from easy_ytdlp.gui.widgets.common import FolderPicker, card, label


class SettingsPage(Page):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(self.tr("Settings"), parent)
        self.ctx = ctx
        s = ctx.settings

        # General
        self.body.addWidget(label(self.tr("General"), "SectionTitle"))
        frame, layout = card()
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.language = QComboBox()
        for value, text in (
            ("system", self.tr("Same as Windows")),
            ("en", "English"),
            ("es", "Español"),
        ):
            self.language.addItem(text, value)
        self.language.setCurrentIndex(max(0, self.language.findData(s.language)))
        self.language_note = label(self.tr("Restart Easy yt-dlp to apply the language."), "Caption")
        self.language_note.hide()
        self.theme = QComboBox()
        for value, text in (
            ("system", self.tr("Same as Windows")),
            ("light", self.tr("Light")),
            ("dark", self.tr("Dark")),
        ):
            self.theme.addItem(text, value)
        self.theme.setCurrentIndex(max(0, self.theme.findData(s.theme)))
        self.folder = FolderPicker()
        self.folder.set_text(str(s.effective_download_dir()))
        form.addRow(self.tr("Language"), self.language)
        form.addRow("", self.language_note)
        form.addRow(self.tr("Theme"), self.theme)
        form.addRow(self.tr("Default folder"), self.folder)
        layout.addLayout(form)
        self.body.addWidget(frame)

        # Downloads
        self.body.addWidget(label(self.tr("Downloads"), "SectionTitle"))
        frame, layout = card()
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.concurrency = QComboBox()
        for value in range(1, 9):
            self.concurrency.addItem(str(value), value)
        self.concurrency.setCurrentIndex(self.concurrency.findData(s.max_concurrent))
        form.addRow(self.tr("Downloads at the same time"), self.concurrency)
        layout.addLayout(form)
        self.body.addWidget(frame)

        # Extension point for later sections (tools, updates, data, about).
        self.sections = self.body
        self.body.addStretch(1)

        self.language.currentIndexChanged.connect(self._language_changed)
        self.theme.currentIndexChanged.connect(self._theme_changed)
        self.folder.changed.connect(self._folder_changed)
        self.concurrency.currentIndexChanged.connect(
            lambda: self._concurrency_changed(self.concurrency.currentData())
        )

    def _language_changed(self) -> None:
        self.ctx.settings.language = self.language.currentData()
        self.language_note.show()
        self.ctx.save_settings()

    def _theme_changed(self) -> None:
        self.ctx.settings.theme = self.theme.currentData()
        self.ctx.theme.set_mode(self.ctx.settings.theme)
        self.ctx.save_settings()

    def _folder_changed(self, value: str) -> None:
        self.ctx.settings.download_dir = value.strip()
        self.ctx.save_settings()

    def _concurrency_changed(self, value: int) -> None:
        self.ctx.settings.max_concurrent = value
        self.ctx.queue.set_max_concurrent(value)
        self.ctx.save_settings()
