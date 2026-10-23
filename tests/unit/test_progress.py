import pytest

from easy_ytdlp.core import progress
from easy_ytdlp.core.progress import (
    DownloadProgress,
    ErrorLine,
    FileFinished,
    LogLine,
    PostProcess,
    WarningLine,
    parse_line,
)


def events(text: str) -> list[progress.Event]:
    return [parse_line(line) for line in text.splitlines()]


def test_video_merge_fixture(fixture_text) -> None:
    parsed = events(fixture_text("progress_video_merge.txt"))
    downloads = [e for e in parsed if isinstance(e, DownloadProgress)]
    posts = [e for e in parsed if isinstance(e, PostProcess)]
    files = [e for e in parsed if isinstance(e, FileFinished)]

    assert len(downloads) == 18
    assert downloads[0].item.title == "Me at the zoo"
    assert downloads[0].item.index is None
    assert downloads[0].fraction == pytest.approx(1024 / 223779)
    assert downloads[8].status == "finished"
    assert downloads[8].fraction == 1.0
    assert [p.postprocessor for p in posts if p.status == "started"] == ["Merger", "MoveFiles"]
    assert files == [FileFinished("C:\\Users\\user\\Downloads\\Me at the zoo [jNQXAC9IVRw].mkv")]
    assert any(isinstance(e, LogLine) and e.text.startswith("[Merger]") for e in parsed)


def test_playlist_fixture_tracks_items(fixture_text) -> None:
    parsed = events(fixture_text("progress_playlist_audio_clip.txt"))
    downloads = [e for e in parsed if isinstance(e, DownloadProgress)]
    assert {(d.item.index, d.item.count) for d in downloads} == {(1, 2), (2, 2)}
    files = [e.path for e in parsed if isinstance(e, FileFinished)]
    assert [f.rsplit("\\", 1)[-1] for f in files] == [
        "1 - 7 Minute Bedtime Yoga - Yoga With Adriene.mp3",
        "2 - Revolution - Day 8 - Practice Serenity.mp3",
    ]
    extract = [e for e in parsed if isinstance(e, PostProcess) and e.status == "started"]
    assert "ExtractAudio" in {e.postprocessor for e in extract}


def test_estimate_is_used_when_total_is_unknown() -> None:
    line = (
        progress.DOWNLOAD_PREFIX
        + '{"status": "downloading", "downloaded_bytes": 50, "total_bytes_estimate": 200,'
        ' "speed": 10.5, "eta": 15} {"id": "x", "playlist_autonumber": 3,'
        ' "playlist_index": 9, "n_entries": 4}'
    )
    event = parse_line(line)
    assert isinstance(event, DownloadProgress)
    assert event.total_bytes == 200
    assert event.fraction == 0.25
    assert event.eta == 15
    # The autonumber (position among selected items) wins over the playlist index.
    assert event.item.index == 3


def test_unknown_size_gives_no_fraction() -> None:
    line = progress.DOWNLOAD_PREFIX + '{"status": "downloading", "downloaded_bytes": 5} {}'
    event = parse_line(line)
    assert isinstance(event, DownloadProgress)
    assert event.fraction is None


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "ERROR: [youtube] x: This video is unavailable",
            ErrorLine("[youtube] x: This video is unavailable"),
        ),
        ("WARNING: slow", WarningLine("slow")),
        ("[download] 5%", LogLine("[download] 5%")),
        (progress.DOWNLOAD_PREFIX + "{broken", LogLine(progress.DOWNLOAD_PREFIX + "{broken")),
        (progress.FILE_PREFIX + "42", LogLine(progress.FILE_PREFIX + "42")),
        ("text\r\n", LogLine("text")),
    ],
)
def test_other_lines(line: str, expected: progress.Event) -> None:
    assert parse_line(line) == expected


def test_templates_reference_prefixes() -> None:
    assert progress.DOWNLOAD_TEMPLATE.startswith("download:" + progress.DOWNLOAD_PREFIX)
    assert "%(info.{id,title,playlist_index,playlist_autonumber,n_entries})j" in (
        progress.DOWNLOAD_TEMPLATE
    )
    assert progress.POSTPROCESS_TEMPLATE.startswith("postprocess:" + progress.POSTPROCESS_PREFIX)
    assert "%(progress.{status,postprocessor})j" in progress.POSTPROCESS_TEMPLATE
