"""Loading of the Qt translations for the chosen language."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator

I18N_DIR = Path(__file__).resolve().parents[1] / "i18n"
LANGUAGES = ("system", "en", "es")
AVAILABLE = ("en", "es")

_installed: list[QTranslator] = []


def resolve(setting: str) -> str:
    """Turn the language setting into a language code the app has."""
    if setting in AVAILABLE:
        return setting
    system = QLocale.system().name().split("_")[0]
    return system if system in AVAILABLE else "en"


def install(setting: str) -> str:
    """Install the translators for ``setting``; return the language actually used."""
    app = QCoreApplication.instance()
    language = resolve(setting)
    for translator in _installed:
        QCoreApplication.removeTranslator(translator)
    _installed.clear()
    QLocale.setDefault(QLocale(language))
    if language == "en" or app is None:
        return language
    candidates = [
        (I18N_DIR, f"easy_ytdlp_{language}"),
        (Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)), f"qtbase_{language}"),
    ]
    for folder, name in candidates:
        translator = QTranslator(app)
        if translator.load(name, str(folder)):
            QCoreApplication.installTranslator(translator)
            _installed.append(translator)
    return language
