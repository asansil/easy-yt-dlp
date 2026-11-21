import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from easy_ytdlp.core import command_builder as cb
from easy_ytdlp.core import progress
from easy_ytdlp.core.options import DownloadOptions, Mode, Organize, SponsorBlock

YTDLP = Path("C:/tools/yt-dlp.exe")
URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def build(options: DownloadOptions, **kwargs) -> list[str]:
    options.output.folder = "D:\\Videos"
    return cb.build(options, [URL], ytdlp=YTDLP, **kwargs)


def args_of(options: DownloadOptions, **kwargs) -> list[str]:
    return cb.user_args(build(options, **kwargs))


def has_seq(args: list[str], *seq: str) -> bool:
    n = len(seq)
    return any(args[i : i + n] == list(seq) for i in range(len(args) - n + 1))


def test_default_video_command() -> None:
    argv = build(DownloadOptions())
    assert argv[0] == str(YTDLP)
    assert argv[1 : 1 + len(progress.MACHINE_FLAGS)] == progress.MACHINE_FLAGS
    assert cb.user_args(argv) == [
        "-f",
        "bv*+ba/b",
        "-S",
        "res,ext:mp4:m4a",
        "--merge-output-format",
        "mp4",
        "-P",
        "D:\\Videos",
        "-o",
        "%(title)s [%(id)s].%(ext)s",
        "--embed-metadata",
        "--embed-chapters",
        "--",
        URL,
    ]


@pytest.mark.parametrize(
    ("quality", "container", "expected"),
    [
        ("1080", "mkv", ["-f", "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b"]),
        ("720", "webm", ["-S", "res,ext:webm:webm", "--merge-output-format", "webm"]),
    ],
)
def test_video_quality_and_container(quality: str, container: str, expected: list[str]) -> None:
    options = DownloadOptions()
    options.format.quality = quality
    options.format.container = container
    args = args_of(options)
    assert has_seq(args, *expected)
    if container == "mkv":
        assert "-S" not in args


@pytest.mark.parametrize(
    ("fmt", "bitrate", "expected", "absent"),
    [
        ("mp3", "192", ["-x", "--audio-format", "mp3", "--audio-quality", "192K"], []),
        ("opus", "best", ["--audio-format", "opus", "--audio-quality", "0"], []),
        ("flac", "320", ["--audio-format", "flac"], ["--audio-quality"]),
        ("best", "128", ["-f", "ba/b", "-x"], ["--audio-format", "--audio-quality"]),
    ],
)
def test_audio(fmt: str, bitrate: str, expected: list[str], absent: list[str]) -> None:
    options = DownloadOptions(mode=Mode.AUDIO)
    options.audio.format = fmt
    options.audio.bitrate = bitrate
    args = args_of(options)
    assert has_seq(args, *expected)
    for flag in absent:
        assert flag not in args
    assert "--embed-chapters" not in args
    assert "--merge-output-format" not in args


def test_subtitles_mode() -> None:
    options = DownloadOptions(mode=Mode.SUBTITLES)
    options.subtitles.languages = ["es", "en"]
    options.subtitles.auto_generated = True
    options.advanced.embed_metadata = True
    args = args_of(options)
    assert args[:1] == ["--skip-download"]
    assert has_seq(args, "--write-subs", "--write-auto-subs", "--sub-langs", "es,en")
    assert has_seq(args, "--convert-subs", "srt")
    assert "--embed-metadata" not in args
    assert "-f" not in args


def test_embedded_subtitles_in_video() -> None:
    options = DownloadOptions()
    options.subtitles.enabled = True
    options.subtitles.embed = True
    args = args_of(options)
    assert has_seq(args, "--embed-subs", "--sub-langs", "en")
    assert "--write-subs" not in args
    assert "--convert-subs" not in args


def test_audio_subtitles_are_separate_files() -> None:
    options = DownloadOptions(mode=Mode.AUDIO)
    options.subtitles.enabled = True
    options.subtitles.embed = True
    options.subtitles.format = "vtt"
    args = args_of(options)
    assert "--embed-subs" not in args
    assert has_seq(args, "--convert-subs", "vtt")


@pytest.mark.parametrize(
    ("start", "end", "section"),
    [
        ("1:00", "2:30", "*00:01:00-00:02:30"),
        ("", "10", "*00:00:00-00:00:10"),
        ("0:05", "", "*00:00:05-inf"),
        ("1:02:03", "100:00:00", "*01:02:03-100:00:00"),
        # Fractions from 2.0.0 presets round outwards so the clip keeps the whole range.
        ("4.7", "2:30.2", "*00:00:04-00:02:31"),
    ],
)
def test_clip(start: str, end: str, section: str) -> None:
    options = DownloadOptions()
    options.clip.enabled = True
    options.clip.start = start
    options.clip.end = end
    options.clip.force_keyframes = True
    assert has_seq(args_of(options), "--download-sections", section, "--force-keyframes-at-cuts")


def test_invalid_clip_is_ignored() -> None:
    options = DownloadOptions()
    options.clip.enabled = True
    options.clip.start = "bad"
    assert "--download-sections" not in args_of(options)


@pytest.mark.parametrize(
    ("organize", "prefix"),
    [
        (Organize.UPLOADER, "%(uploader,channel|Unknown)s/"),
        (Organize.PLAYLIST, "%(playlist_title|.)s/"),
        (Organize.UPLOADER_PLAYLIST, "%(uploader,channel|Unknown)s/%(playlist_title|.)s/"),
    ],
)
def test_organize_prefix(organize: Organize, prefix: str) -> None:
    options = DownloadOptions()
    options.output.organize = organize
    assert has_seq(args_of(options), "-o", prefix + "%(title)s [%(id)s].%(ext)s")


def test_advanced_options() -> None:
    options = DownloadOptions()
    adv = options.advanced
    adv.cookies_browser = "firefox"
    adv.embed_metadata = False
    adv.embed_thumbnail = True
    adv.embed_chapters = False
    adv.sponsorblock = SponsorBlock.REMOVE
    adv.sponsorblock_categories = ["sponsor", "intro"]
    adv.rate_limit = "2M"
    adv.use_archive = True
    adv.extra_args = '--limit-rate 1M --exec "echo {}"'
    args = args_of(options, archive_file=Path("C:/data/archive.txt"), playlist_items="1-3,7")
    assert has_seq(args, "--cookies-from-browser", "firefox")
    assert "--embed-metadata" not in args
    assert "--embed-thumbnail" in args
    assert "--embed-chapters" not in args
    assert has_seq(args, "--sponsorblock-remove", "sponsor,intro")
    assert has_seq(args, "-r", "2M")
    assert has_seq(args, "--download-archive", str(Path("C:/data/archive.txt")))
    assert has_seq(args, "-I", "1-3,7")
    assert has_seq(args, "--limit-rate", "1M", "--exec", "echo {}", "--", URL)


def test_sponsorblock_mark_and_archive_without_file() -> None:
    options = DownloadOptions()
    options.advanced.sponsorblock = SponsorBlock.MARK
    options.advanced.use_archive = True
    args = args_of(options)
    assert has_seq(args, "--sponsorblock-mark", "sponsor")
    assert "--download-archive" not in args


def test_urls_go_after_separator() -> None:
    argv = cb.build(DownloadOptions(), ["-not-an-option", URL], ytdlp=YTDLP)
    assert argv[-3:] == ["--", "-not-an-option", URL]


def test_default_folder_is_downloads() -> None:
    argv = cb.build(DownloadOptions(), [URL], ytdlp=YTDLP)
    assert has_seq(argv, "-P", str(Path.home() / "Downloads"))


def test_to_display_hides_machine_flags_and_quotes() -> None:
    text = cb.to_display(build(DownloadOptions()))
    assert text.startswith('yt-dlp -f "bv*+ba/b" -S "res,ext:mp4:m4a"')
    assert '"%(title)s [%(id)s].%(ext)s"' in text
    assert "--progress-template" not in text
    assert "--progress-template" in cb.to_display(
        build(DownloadOptions()), include_machine_flags=True
    )


@pytest.mark.parametrize(
    ("arg", "shown"),
    [
        ("--download-sections", "--download-sections"),
        (r"D:\Videos", r"D:\Videos"),
        ("https://example.com/v/1", "https://example.com/v/1"),
        ("refe_intro.%(ext)s", '"refe_intro.%(ext)s"'),
        ("res,ext:mp4:m4a", '"res,ext:mp4:m4a"'),
        ("bv*[height<=720]+ba/b", '"bv*[height<=720]+ba/b"'),
        ("%(uploader,channel|Unknown)s/", '"%(uploader,channel|Unknown)s/"'),
        ("https://x.com/watch?v=a&t=5", '"https://x.com/watch?v=a&t=5"'),
        (r"C:\My Videos", r'"C:\My Videos"'),
        ("@file", '"@file"'),
        ("", '""'),
        ('say "hi"', r'"say \"hi\""'),
        ("C:\\My Videos\\", '"C:\\My Videos\\\\"'),
    ],
)
def test_shell_quote(arg: str, shown: str) -> None:
    assert cb.shell_quote(arg) == shown


def _tricky_argv() -> list[str]:
    options = DownloadOptions()
    options.format.quality = "1080"
    options.output.template = "refe_intro.%(ext)s"
    options.output.organize = Organize.UPLOADER_PLAYLIST
    options.output.folder = r"C:\Users\me\My Videos"
    options.clip.enabled = True
    options.clip.start = "0:05"
    options.advanced.extra_args = '--exec "echo {}"'
    return cb.build(options, ["https://www.youtube.com/watch?v=abc&t=5"], ytdlp=YTDLP)


def test_displayed_command_splits_back() -> None:
    argv = _tricky_argv()
    assert cb.split_arguments(cb.to_display(argv))[1:] == cb.user_args(argv)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shells")
@pytest.mark.parametrize("shell", ["powershell", "pwsh", "cmd"])
def test_displayed_command_pastes_into_windows_shells(shell: str, tmp_path: Path) -> None:
    """Paste the displayed command into each shell, with an argv-echo stub as yt-dlp."""
    if not shutil.which(shell):
        pytest.skip(f"{shell} is not installed")
    argv = _tricky_argv()
    stub = tmp_path / "echo_args.py"
    stub.write_text("import json, sys\nprint(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
    program = f"{cb.shell_quote(sys.executable)} {cb.shell_quote(str(stub))}"
    line = program + cb.to_display(argv).removeprefix(cb.DISPLAY_EXE)
    if shell == "cmd":
        run = subprocess.run(f'cmd /d /s /c "{line}"', capture_output=True, text=True, check=True)
    else:
        command = [shell, "-NoProfile", "-NonInteractive", "-Command", f"& {line}"]
        run = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(run.stdout) == cb.user_args(argv)


def test_mask_secrets() -> None:
    args = [
        "--cookies",
        "C:/secret/cookies.txt",
        "--password=hunter2",
        "-u",
        "me",
        "--add-header",
        "Cookie: a=b",
        "--add-header",
        "Accept: x",
        "--cookies-from-browser",
        "firefox",
    ]
    assert cb.mask_secrets(args) == [
        "--cookies",
        cb.MASK,
        f"--password={cb.MASK}",
        "-u",
        cb.MASK,
        "--add-header",
        f"Cookie:{cb.MASK}",
        "--add-header",
        "Accept: x",
        "--cookies-from-browser",
        "firefox",
    ]


def test_split_arguments_keeps_backslashes() -> None:
    assert cb.split_arguments(r'-P C:\Users\me\Videos -o "%(title)s.%(ext)s" URL') == [
        "-P",
        r"C:\Users\me\Videos",
        "-o",
        "%(title)s.%(ext)s",
        "URL",
    ]


def test_split_arguments_unbalanced_quote() -> None:
    with pytest.raises(cb.ManualCommandError):
        cb.split_arguments('-o "unterminated')


def test_parse_manual_adds_machine_flags_and_strips_program() -> None:
    argv = cb.parse_manual("yt-dlp.exe -x URL", ytdlp=YTDLP)
    assert argv == [str(YTDLP), *progress.MACHINE_FLAGS, "-x", "URL"]
    assert cb.user_args(argv) == ["-x", "URL"]


def test_parse_manual_empty() -> None:
    with pytest.raises(cb.ManualCommandError):
        cb.parse_manual("  yt-dlp ")


def test_manual_argv_with_folder_and_url() -> None:
    argv = cb.manual_argv("-x --audio-format mp3", url=" U ", folder=r"D:\Music", ytdlp=YTDLP)
    assert cb.user_args(argv) == ["-P", r"D:\Music", "-x", "--audio-format", "mp3", "--", "U"]


def test_manual_argv_without_extras() -> None:
    assert cb.user_args(cb.manual_argv("-F URL", ytdlp=YTDLP)) == ["-F", "URL"]
