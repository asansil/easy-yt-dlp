import json
import subprocess
from pathlib import Path

import pytest

from easy_ytdlp.core import probe
from easy_ytdlp.core.probe import MediaKind, ProbeError


def test_video(fixture_json) -> None:
    info = probe.parse_info(fixture_json("probe_video.json"))
    assert info.kind == MediaKind.VIDEO
    assert info.title == "Me at the zoo"
    assert info.uploader == "jawed"
    assert info.duration == 19
    assert info.thumbnail and info.thumbnail.startswith("https://")
    assert info.heights == [240, 144]
    assert info.subtitles == ["de", "en"]
    assert "en" in info.auto_captions
    assert not info.is_collection
    assert info.entries == []


def test_playlist(fixture_json) -> None:
    info = probe.parse_info(fixture_json("probe_playlist.json"))
    assert info.kind == MediaKind.PLAYLIST
    assert info.title == "Morning or Night"
    assert info.count == 37
    assert len(info.entries) == 5
    first = info.entries[0]
    assert first.index == 1
    assert first.title == "7 Minute Bedtime Yoga - Yoga With Adriene"
    assert first.url == "https://www.youtube.com/watch?v=LI9upn4t9n8"
    assert first.duration == 419


def test_channel(fixture_json) -> None:
    info = probe.parse_info(fixture_json("probe_channel.json"))
    assert info.kind == MediaKind.CHANNEL
    assert info.uploader == "Blender Studio"
    assert info.is_collection
    assert [e.index for e in info.entries] == [1, 2, 3, 4, 5]


def test_thumbnail_from_list() -> None:
    data = {
        "_type": "playlist",
        "id": "PL1",
        "thumbnails": [
            {"url": "small", "width": 10, "height": 10},
            {"url": "big", "width": 99, "height": 99},
        ],
        "entries": [],
    }
    info = probe.parse_info(data, "https://x")
    assert info.thumbnail == "big"
    assert info.url == "https://x"
    assert info.count is None


def test_error_message(fixture_text) -> None:
    assert probe.error_message(fixture_text("probe_error.txt")) == (
        "[youtube] xxxxxxxxxxx: This video is unavailable"
    )
    assert probe.error_message("WARNING: a\nsomething else") == "something else"
    assert probe.error_message("") == "yt-dlp failed without output"


def test_probe_argv_puts_url_after_separator() -> None:
    argv = probe.probe_argv("-x", Path("yt.exe"))
    assert argv[-2:] == ["--", "-x"]
    assert "-J" in argv and "--flat-playlist" in argv


def fake_run(stdout: bytes = b"", stderr: bytes = b"", code: int = 0):
    def run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, code, stdout, stderr)

    return run


def test_analyze_success(fixture_json) -> None:
    payload = json.dumps(fixture_json("probe_video.json")).encode()
    info = probe.analyze("u", ytdlp=Path("y.exe"), run=fake_run(payload))
    assert info.title == "Me at the zoo"


def test_analyze_failure(fixture_text) -> None:
    run = fake_run(stderr=fixture_text("probe_error.txt").encode(), code=1)
    with pytest.raises(ProbeError) as exc:
        probe.analyze("u", ytdlp=Path("y.exe"), run=run)
    assert "unavailable" in exc.value.message
    assert "ERROR:" in exc.value.details


def test_analyze_invalid_json() -> None:
    with pytest.raises(ProbeError):
        probe.analyze("u", ytdlp=Path("y.exe"), run=fake_run(b"not json"))
    with pytest.raises(ProbeError):
        probe.analyze("u", ytdlp=Path("y.exe"), run=fake_run(b"[1, 2]"))


def test_analyze_missing_executable() -> None:
    with pytest.raises(ProbeError, match="not installed"):
        probe.analyze("u", ytdlp=Path("Z:/missing/yt-dlp.exe"))


def test_analyze_timeout() -> None:
    def run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)

    with pytest.raises(ProbeError, match="in time"):
        probe.analyze("u", ytdlp=Path("y.exe"), run=run)
