import json

import pytest

from easy_ytdlp.core.options import (
    DownloadOptions,
    Mode,
    Organize,
    SponsorBlock,
    ValidationError,
    format_time,
    parse_time,
    template_escapes_folder,
    validate,
)


def test_round_trip_through_json() -> None:
    options = DownloadOptions(mode=Mode.AUDIO)
    options.audio.format = "flac"
    options.subtitles.languages = ["es", "en"]
    options.output.organize = Organize.PLAYLIST
    options.advanced.sponsorblock = SponsorBlock.MARK
    restored = DownloadOptions.from_dict(json.loads(json.dumps(options.to_dict())))
    assert restored == options


def test_from_dict_ignores_unknown_and_invalid_values() -> None:
    restored = DownloadOptions.from_dict(
        {
            "mode": "hologram",
            "unknown": 1,
            "format": {"quality": 1080, "container": "mkv"},
            "clip": {"enabled": "yes"},
            "subtitles": "nope",
        }
    )
    assert restored.mode == Mode.VIDEO
    assert restored.format.quality == "best"
    assert restored.format.container == "mkv"
    assert restored.clip.enabled is False


def test_from_dict_none_gives_defaults() -> None:
    assert DownloadOptions.from_dict(None) == DownloadOptions()


def test_copy_is_independent() -> None:
    options = DownloadOptions()
    copy = options.copy()
    copy.subtitles.languages.append("fr")
    assert options.subtitles.languages == ["en"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("90", 90),
        ("1:30", 90),
        ("01:02:03", 3723),
        ("75:00", 4500),
        ("1.5", 1.5),
        ("0:10.25", 10.25),
        ("", None),
        ("1:60", None),
        ("1:61:00", None),
        ("abc", None),
        ("-5", None),
    ],
)
def test_parse_time(text: str, expected: float | None) -> None:
    assert parse_time(text) == expected


def test_format_time() -> None:
    assert format_time(59) == "0:59"
    assert format_time(3723) == "1:02:03"


def test_validate_defaults_ok() -> None:
    assert validate(DownloadOptions()) == []


def test_validate_clip() -> None:
    options = DownloadOptions()
    options.clip.enabled = True
    options.clip.start = "1:00"
    options.clip.end = "0:30"
    assert ValidationError.CLIP_EMPTY_RANGE in validate(options)

    options.clip.start = "x"
    options.clip.end = "y"
    errors = validate(options)
    assert ValidationError.CLIP_START_INVALID in errors
    assert ValidationError.CLIP_END_INVALID in errors

    options.clip.start = "10:00"
    options.clip.end = ""
    assert validate(options, duration=60) == [ValidationError.CLIP_BEYOND_DURATION]


def test_validate_rate_template_and_subtitles() -> None:
    options = DownloadOptions(mode=Mode.SUBTITLES)
    options.advanced.rate_limit = "fast"
    options.output.template = "../%(title)s.%(ext)s"
    options.subtitles.languages = [" "]
    assert set(validate(options)) == {
        ValidationError.RATE_LIMIT_INVALID,
        ValidationError.TEMPLATE_OUTSIDE_FOLDER,
        ValidationError.NO_SUBTITLE_LANGUAGES,
    }
    options.output.template = "  "
    assert ValidationError.TEMPLATE_EMPTY in validate(options)


@pytest.mark.parametrize(
    ("template", "escapes"),
    [
        ("%(title)s.%(ext)s", False),
        ("%(uploader)s/%(title)s.%(ext)s", False),
        ("%(title).50s..%(ext)s", False),
        ("../%(title)s.%(ext)s", True),
        ("a\\..\\..\\%(title)s", True),
        ("C:/Windows/%(title)s", True),
        ("/abs/%(title)s", True),
    ],
)
def test_template_escapes_folder(template: str, escapes: bool) -> None:
    assert template_escapes_folder(template) is escapes
