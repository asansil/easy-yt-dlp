import json
from pathlib import Path

import pytest

from easy_ytdlp.core import command_builder, paths, presets, template_preview
from easy_ytdlp.core.history import HistoryStore
from easy_ytdlp.core.options import DownloadOptions, Mode, Organize
from easy_ytdlp.core.presets import PresetError, PresetStore
from easy_ytdlp.core.queue import Job, JobState
from easy_ytdlp.core.selection import SelectionError, format_ranges, parse_ranges

# -- selection ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1-3, 7", {1, 2, 3, 7}),
        ("5", {5}),
        ("8-", {8, 9, 10}),
        ("9-20", {9, 10}),
        ("", set()),
        (" 2 , 2-3 ,", {2, 3}),
        ("11", set()),
    ],
)
def test_parse_ranges(text: str, expected: set[int]) -> None:
    assert parse_ranges(text, 10) == expected


@pytest.mark.parametrize("text", ["a", "0", "3-1", "1--2", "-4"])
def test_parse_ranges_errors(text: str) -> None:
    with pytest.raises(SelectionError):
        parse_ranges(text, 10)


def test_format_ranges() -> None:
    assert format_ranges([7, 1, 2, 3, 9, 10]) == "1-3,7,9-10"
    assert format_ranges([4]) == "4"
    assert format_ranges([]) == ""


# -- template preview --------------------------------------------------------------------


def test_preview_default_template() -> None:
    options = DownloadOptions()
    template = command_builder.output_template(options)
    assert template_preview.preview(options, template, {"title": "Me at the zoo", "id": "abc"}) == (
        "Me at the zoo [abc].mp4"
    )


def test_preview_organize_and_playlist_fields() -> None:
    options = DownloadOptions(mode=Mode.AUDIO)
    options.output.organize = Organize.UPLOADER_PLAYLIST
    options.output.template = "%(playlist_index)03d - %(title).5s.%(ext)s"
    template = command_builder.output_template(options)
    single = template_preview.preview(options, template, {"uploader": "Jawed"})
    assert single == "Jawed\\NA - Video.mp3"
    listed = template_preview.preview(
        options, template, {"uploader": "A/B", "playlist_title": "Mix", "playlist_index": 7}
    )
    assert listed == "A_B\\Mix\\007 - Video.mp3"


def test_preview_replacement_and_default() -> None:
    fields = {"title": "T", "upload_date": "20240131"}
    assert template_preview.render("%(album|No album)s", fields) == "No album"
    assert template_preview.render("%(title&[{}]|)s", fields) == "[T]"
    assert template_preview.render("%(missing,title)s", fields) == "T"
    assert template_preview.render("%(upload_date>%Y-%m-%d)s", fields) == "2024-01-31"


def test_output_ext() -> None:
    assert template_preview.output_ext(DownloadOptions(mode=Mode.SUBTITLES)) == "en.srt"
    audio = DownloadOptions(mode=Mode.AUDIO)
    audio.audio.format = "best"
    assert template_preview.output_ext(audio) == "m4a"


# -- presets -----------------------------------------------------------------------------


def test_builtin_presets() -> None:
    store = PresetStore()
    names = [p.name for p in store.all()]
    assert names[: len(presets.BUILTIN_PRESETS)] == [p.name for p in presets.BUILTIN_PRESETS]
    music = store.get("Music MP3 320 kbit/s")
    assert music.builtin
    assert music.options.mode == Mode.AUDIO
    assert music.options.audio.bitrate == "320"
    assert store.get("Subtitles only").options.mode == Mode.SUBTITLES
    with pytest.raises(PresetError):
        store.delete("Subtitles only")
    with pytest.raises(PresetError):
        store.rename("Subtitles only", "x")


def test_user_presets_persist() -> None:
    store = PresetStore()
    options = DownloadOptions(mode=Mode.AUDIO)
    options.audio.format = "opus"
    store.save("Podcasts", options)
    options.audio.format = "flac"  # the store keeps its own copy
    with pytest.raises(PresetError):
        store.save("Podcasts", options)
    with pytest.raises(PresetError):
        store.save("  ", options)
    store.save("Podcasts", options, overwrite=True)

    again = PresetStore()
    assert again.get("Podcasts").options.audio.format == "flac"
    again.rename("Podcasts", "Talks")
    again.duplicate("Talks", "Talks copy")
    again.duplicate("Best video (MP4)", "My video")
    assert [p.name for p in PresetStore().user_presets()] == ["Talks", "Talks copy", "My video"]
    again.delete("Talks copy")
    assert [p.name for p in PresetStore().user_presets()] == ["Talks", "My video"]
    assert again.unique_name("Talks") == "Talks (2)"
    assert again.unique_name("New") == "New"


def test_corrupt_presets_file() -> None:
    paths.presets_file().parent.mkdir(parents=True, exist_ok=True)
    paths.presets_file().write_text('{"presets": [{"name": 3}, {"name": "ok"}, 5]}')
    assert [p.name for p in PresetStore().user_presets()] == ["ok"]
    paths.presets_file().write_text("nope")
    assert PresetStore().user_presets() == []


# -- history -----------------------------------------------------------------------------


def job(title: str, *, options: dict | None = None, argv=None, state=JobState.DONE, at=1.0) -> Job:
    return Job(
        id=1,
        argv=argv or ["yt-dlp", "--", "u"],
        title=title,
        url=f"https://example.com/{title}",
        options=options,
        output_dir="D:\\out",
        state=state,
        files=["D:\\out\\a.mp4"],
        finished_at=at,
    )


def test_history_add_search_delete(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "h.sqlite")
    first = store.add_job(job("first_video", options=DownloadOptions().to_dict(), at=1))
    store.add_job(job("second 100%", state=JobState.FAILED, at=2))
    assert [e.title for e in store.search()] == ["second 100%", "first_video"]
    assert [e.title for e in store.search("first")] == ["first_video"]
    assert [e.title for e in store.search("100%")] == ["second 100%"]
    assert store.search("_v")[0].title == "first_video"
    assert [e.title for e in store.search(state="failed")] == ["second 100%"]
    entry = store.get(first)
    assert entry.options["mode"] == "video"
    assert entry.files == ["D:\\out\\a.mp4"]
    store.delete(first)
    assert store.count() == 1
    store.clear()
    assert store.count() == 0
    store.close()


def test_history_command_jobs_mask_secrets(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "h.sqlite")
    plain = command_builder.parse_manual("-x URL")
    secret = command_builder.parse_manual("--password hunter2 URL")
    a = store.get(store.add_job(job("plain", argv=plain)))
    b = store.get(store.add_job(job("secret", argv=secret)))
    assert a.args == ["-x", "URL"] and a.rerunnable
    assert b.args == ["--password", command_builder.MASK, "URL"] and not b.rerunnable
    raw = (tmp_path / "h.sqlite").read_bytes()
    assert b"hunter2" not in raw
    assert json.loads(json.dumps(a.args)) == ["-x", "URL"]
    store.close()
