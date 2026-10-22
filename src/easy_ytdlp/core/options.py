"""The download options model: the single source of truth for what a download does.

Every GUI control maps to a field here, presets and history store these objects as
dictionaries, and ``command_builder`` turns them into a yt-dlp argv.
"""

import contextlib
import re
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from enum import StrEnum
from typing import Any, Self


class Mode(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLES = "subtitles"


class Organize(StrEnum):
    """Optional subfolder that groups downloaded files."""

    NONE = "none"
    UPLOADER = "uploader"
    PLAYLIST = "playlist"
    UPLOADER_PLAYLIST = "uploader_playlist"


class SponsorBlock(StrEnum):
    OFF = "off"
    REMOVE = "remove"
    MARK = "mark"


# "best" or a maximum height in pixels.
VIDEO_QUALITIES = ["best", "2160", "1440", "1080", "720", "480", "360"]
VIDEO_CONTAINERS = ["mp4", "mkv", "webm"]
AUDIO_FORMATS = ["mp3", "m4a", "opus", "flac", "wav", "best"]
LOSSLESS_AUDIO_FORMATS = {"flac", "wav"}
# kbit/s, or "best" for the highest VBR quality.
AUDIO_BITRATES = ["best", "320", "256", "192", "128", "96"]
SUBTITLE_FORMATS = ["srt", "vtt", "ass"]
BROWSERS = ["chrome", "edge", "firefox", "brave", "opera", "vivaldi", "chromium", "whale"]
SPONSORBLOCK_CATEGORIES = [
    "sponsor",
    "intro",
    "outro",
    "selfpromo",
    "preview",
    "filler",
    "interaction",
    "music_offtopic",
]

DEFAULT_TEMPLATE = "%(title)s [%(id)s].%(ext)s"


@dataclass
class FormatOptions:
    quality: str = "best"
    container: str = "mp4"


@dataclass
class AudioOptions:
    format: str = "mp3"
    bitrate: str = "192"


@dataclass
class SubtitleOptions:
    """Subtitles are downloaded in every mode when enabled; Subtitles mode forces them on."""

    enabled: bool = False
    languages: list[str] = field(default_factory=lambda: ["en"])
    auto_generated: bool = False
    embed: bool = False
    format: str = "srt"


@dataclass
class ClipOptions:
    enabled: bool = False
    # "hh:mm:ss", "mm:ss" or seconds; empty means the start or the end of the media.
    start: str = ""
    end: str = ""
    force_keyframes: bool = False


@dataclass
class OutputOptions:
    folder: str = ""
    template: str = DEFAULT_TEMPLATE
    organize: Organize = Organize.NONE


@dataclass
class AdvancedOptions:
    cookies_browser: str = ""
    embed_metadata: bool = True
    embed_thumbnail: bool = False
    embed_chapters: bool = True
    sponsorblock: SponsorBlock = SponsorBlock.OFF
    sponsorblock_categories: list[str] = field(default_factory=lambda: ["sponsor"])
    # yt-dlp rate syntax, e.g. "2M" or "500K"; empty means unlimited.
    rate_limit: str = ""
    use_archive: bool = False
    # Extra yt-dlp arguments appended after the generated ones.
    extra_args: str = ""


@dataclass
class DownloadOptions:
    mode: Mode = Mode.VIDEO
    format: FormatOptions = field(default_factory=FormatOptions)
    audio: AudioOptions = field(default_factory=AudioOptions)
    subtitles: SubtitleOptions = field(default_factory=SubtitleOptions)
    clip: ClipOptions = field(default_factory=ClipOptions)
    output: OutputOptions = field(default_factory=OutputOptions)
    advanced: AdvancedOptions = field(default_factory=AdvancedOptions)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Self:
        """Build options from a stored dictionary, ignoring unknown keys and bad values."""
        return _from_dict(cls, data or {})

    def copy(self) -> Self:
        return type(self).from_dict(self.to_dict())


def _from_dict[T](cls: type[T], data: dict[str, Any]) -> T:
    instance = cls()
    for f in fields(cls):  # type: ignore[arg-type]
        if f.name not in data:
            continue
        current = getattr(instance, f.name)
        value = data[f.name]
        if is_dataclass(current):
            if isinstance(value, dict):
                setattr(instance, f.name, _from_dict(type(current), value))
        elif isinstance(current, StrEnum):
            with contextlib.suppress(ValueError):
                setattr(instance, f.name, type(current)(value))
        elif isinstance(current, bool):
            if isinstance(value, bool):
                setattr(instance, f.name, value)
        elif isinstance(current, list):
            if isinstance(value, list):
                setattr(instance, f.name, [str(v) for v in value])
        elif isinstance(current, str) and isinstance(value, str):
            setattr(instance, f.name, value)
    return instance


_TIME_RE = re.compile(r"^(?:(\d+):)?(?:(\d{1,2}):)?(\d+(?:\.\d+)?)$")
_RATE_RE = re.compile(r"^\d+(?:\.\d+)?[KMG]?$", re.IGNORECASE)


def parse_time(text: str) -> float | None:
    """Parse "hh:mm:ss", "mm:ss" or plain seconds; return None when invalid."""
    text = text.strip()
    match = _TIME_RE.match(text)
    if not match:
        return None
    first, second, seconds = match.groups()
    if first is not None and second is None:
        hours, minutes = 0, int(first)
    else:
        hours, minutes = int(first or 0), int(second or 0)
    secs = float(seconds)
    if (first is not None and secs >= 60) or (second is not None and minutes >= 60):
        return None
    return hours * 3600 + minutes * 60 + secs


def format_time(seconds: float) -> str:
    """Format seconds as "h:mm:ss" or "m:ss"."""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class ValidationError(StrEnum):
    """Problems found by ``validate``; the GUI maps each code to a translated message."""

    CLIP_START_INVALID = "clip_start_invalid"
    CLIP_END_INVALID = "clip_end_invalid"
    CLIP_EMPTY_RANGE = "clip_empty_range"
    CLIP_BEYOND_DURATION = "clip_beyond_duration"
    RATE_LIMIT_INVALID = "rate_limit_invalid"
    TEMPLATE_EMPTY = "template_empty"
    TEMPLATE_OUTSIDE_FOLDER = "template_outside_folder"
    NO_SUBTITLE_LANGUAGES = "no_subtitle_languages"


def validate(options: DownloadOptions, duration: float | None = None) -> list[ValidationError]:
    errors: list[ValidationError] = []

    clip = options.clip
    if clip.enabled:
        start = parse_time(clip.start) if clip.start.strip() else 0.0
        end = parse_time(clip.end) if clip.end.strip() else None
        if start is None:
            errors.append(ValidationError.CLIP_START_INVALID)
        if clip.end.strip() and end is None:
            errors.append(ValidationError.CLIP_END_INVALID)
        if start is not None and end is not None and end <= start:
            errors.append(ValidationError.CLIP_EMPTY_RANGE)
        if duration is not None and start is not None and start >= duration:
            errors.append(ValidationError.CLIP_BEYOND_DURATION)

    rate = options.advanced.rate_limit.strip()
    if rate and not _RATE_RE.match(rate):
        errors.append(ValidationError.RATE_LIMIT_INVALID)

    template = options.output.template.strip()
    if not template:
        errors.append(ValidationError.TEMPLATE_EMPTY)
    elif template_escapes_folder(template):
        errors.append(ValidationError.TEMPLATE_OUTSIDE_FOLDER)

    subs_needed = options.mode == Mode.SUBTITLES or options.subtitles.enabled
    if subs_needed and not [lang for lang in options.subtitles.languages if lang.strip()]:
        errors.append(ValidationError.NO_SUBTITLE_LANGUAGES)

    return errors


def template_escapes_folder(template: str) -> bool:
    """True when an output template is absolute or climbs out of the download folder."""
    # Ignore the inside of %(...)s fields, where ".." can be legitimate syntax.
    literal = re.sub(r"%\([^)]*\)", "", template).replace("\\", "/")
    if literal.startswith("/") or re.match(r"^[A-Za-z]:", literal):
        return True
    return any(part == ".." for part in literal.split("/"))
