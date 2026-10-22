"""User-facing texts for codes that come from the Qt-free core."""

from PySide6.QtCore import QCoreApplication

from easy_ytdlp.core.options import ValidationError


def validation(code: ValidationError) -> str:
    translate = QCoreApplication.translate
    texts = {
        ValidationError.CLIP_START_INVALID: translate(
            "messages", "The clip start is not a valid time (use h:mm:ss, m:ss or seconds)."
        ),
        ValidationError.CLIP_END_INVALID: translate(
            "messages", "The clip end is not a valid time (use h:mm:ss, m:ss or seconds)."
        ),
        ValidationError.CLIP_EMPTY_RANGE: translate(
            "messages", "The clip end must be after its start."
        ),
        ValidationError.CLIP_BEYOND_DURATION: translate(
            "messages", "The clip starts after the end of the media."
        ),
        ValidationError.RATE_LIMIT_INVALID: translate(
            "messages", "The rate limit must look like 500K, 2M or 1.5M."
        ),
        ValidationError.TEMPLATE_EMPTY: translate("messages", "The file name template is empty."),
        ValidationError.TEMPLATE_OUTSIDE_FOLDER: translate(
            "messages",
            "The file name template would save files outside the chosen folder.",
        ),
        ValidationError.NO_SUBTITLE_LANGUAGES: translate(
            "messages", "Choose at least one subtitle language."
        ),
    }
    return texts[code]


def preset_name(name: str) -> str:
    """Display name of a preset; built-in presets are translated."""
    translate = QCoreApplication.translate
    builtin = {
        "Best video (MP4)": translate("presets", "Best video (MP4)"),
        "Video 1080p (MP4)": translate("presets", "Video 1080p (MP4)"),
        "Video 720p + subtitles": translate("presets", "Video 720p + subtitles"),
        "Music MP3 320 kbit/s": translate("presets", "Music MP3 320 kbit/s"),
        "Audio, original format": translate("presets", "Audio, original format"),
        "Subtitles only": translate("presets", "Subtitles only"),
    }
    return builtin.get(name, name)
