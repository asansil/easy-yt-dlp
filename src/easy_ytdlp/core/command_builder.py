"""Pure functions that turn download options into a yt-dlp argv, and back into text.

The GUI, "Show command" and command mode all go through this module, so what the user
sees is always what runs.
"""

import shlex
import subprocess
from collections.abc import Sequence
from pathlib import Path

from easy_ytdlp.core import paths, progress
from easy_ytdlp.core.options import (
    LOSSLESS_AUDIO_FORMATS,
    DownloadOptions,
    Mode,
    Organize,
    SponsorBlock,
    parse_time,
)

DISPLAY_EXE = "yt-dlp"
MASK = "********"

# Options whose value must never be shown or stored in clear text.
SECRET_OPTIONS = {
    "--cookies",
    "-p",
    "--password",
    "-u",
    "--username",
    "--video-password",
    "--ap-password",
    "--ap-username",
    "--client-certificate-password",
}
SECRET_HEADERS = ("cookie:", "authorization:")

# yt-dlp sanitizes "/" inside field values, so folders are literal "/" between fields.
# A missing playlist title falls back to "." (the folder itself): an empty first
# segment would turn the path into an absolute one.
_ORGANIZE_PREFIX = {
    Organize.NONE: "",
    Organize.UPLOADER: "%(uploader,channel|Unknown)s/",
    Organize.PLAYLIST: "%(playlist_title|.)s/",
    Organize.UPLOADER_PLAYLIST: "%(uploader,channel|Unknown)s/%(playlist_title|.)s/",
}


class ManualCommandError(ValueError):
    """The manual argument string cannot be split into arguments."""


def output_template(options: DownloadOptions) -> str:
    """Template passed to ``-o``, including the folder-organization prefix."""
    template = options.output.template.strip() or "%(title)s [%(id)s].%(ext)s"
    return _ORGANIZE_PREFIX[options.output.organize] + template


def _format_args(options: DownloadOptions) -> list[str]:
    if options.mode == Mode.SUBTITLES:
        return ["--skip-download"]

    if options.mode == Mode.AUDIO:
        audio = options.audio
        args = ["-f", "ba/b", "-x"]
        if audio.format != "best":
            args += ["--audio-format", audio.format]
            if audio.format not in LOSSLESS_AUDIO_FORMATS:
                quality = "0" if audio.bitrate == "best" else f"{audio.bitrate}K"
                args += ["--audio-quality", quality]
        return args

    fmt = options.format
    if fmt.quality == "best":
        selector = "bv*+ba/b"
    else:
        selector = f"bv*[height<={fmt.quality}]+ba/b[height<={fmt.quality}]/bv*+ba/b"
    args = ["-f", selector]
    if fmt.container == "mp4":
        args += ["-S", "res,ext:mp4:m4a"]
    elif fmt.container == "webm":
        args += ["-S", "res,ext:webm:webm"]
    args += ["--merge-output-format", fmt.container]
    return args


def _subtitle_args(options: DownloadOptions) -> list[str]:
    subs = options.subtitles
    if options.mode != Mode.SUBTITLES and not subs.enabled:
        return []
    languages = ",".join(lang.strip() for lang in subs.languages if lang.strip())
    embed = options.mode == Mode.VIDEO and subs.embed
    # --embed-subs implies writing them; an explicit --write-subs would keep the files.
    args = ["--embed-subs"] if embed else ["--write-subs"]
    if subs.auto_generated:
        args.append("--write-auto-subs")
    args += ["--sub-langs", languages or "en"]
    if not embed:
        args += ["--convert-subs", subs.format]
    return args


def _clip_args(options: DownloadOptions) -> list[str]:
    clip = options.clip
    if not clip.enabled or options.mode == Mode.SUBTITLES:
        return []
    start = parse_time(clip.start) if clip.start.strip() else 0.0
    end = parse_time(clip.end) if clip.end.strip() else None
    if start is None or (clip.end.strip() and end is None):
        return []
    section = f"*{_seconds(start)}-{_seconds(end) if end is not None else 'inf'}"
    args = ["--download-sections", section]
    if clip.force_keyframes:
        args.append("--force-keyframes-at-cuts")
    return args


def _seconds(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:g}"


def _advanced_args(options: DownloadOptions, archive_file: Path | None) -> list[str]:
    adv = options.advanced
    args: list[str] = []
    if adv.cookies_browser:
        args += ["--cookies-from-browser", adv.cookies_browser]
    if options.mode != Mode.SUBTITLES:
        if adv.embed_metadata:
            args.append("--embed-metadata")
        if adv.embed_thumbnail:
            args.append("--embed-thumbnail")
        if adv.embed_chapters and options.mode == Mode.VIDEO:
            args.append("--embed-chapters")
        if adv.sponsorblock != SponsorBlock.OFF and adv.sponsorblock_categories:
            flag = (
                "--sponsorblock-remove"
                if adv.sponsorblock == SponsorBlock.REMOVE
                else "--sponsorblock-mark"
            )
            args += [flag, ",".join(adv.sponsorblock_categories)]
    if adv.rate_limit.strip():
        args += ["-r", adv.rate_limit.strip()]
    if adv.use_archive and archive_file is not None:
        args += ["--download-archive", str(archive_file)]
    return args


def build(
    options: DownloadOptions,
    urls: Sequence[str],
    *,
    ytdlp: Path | None = None,
    playlist_items: str = "",
    archive_file: Path | None = None,
) -> list[str]:
    """Build the full argv for a download. URLs always go after ``--``."""
    argv = [str(ytdlp or paths.ytdlp_exe()), *progress.MACHINE_FLAGS]
    argv += _format_args(options)
    argv += _subtitle_args(options)
    argv += _clip_args(options)
    folder = options.output.folder.strip() or str(paths.default_download_dir())
    argv += ["-P", folder, "-o", output_template(options)]
    if playlist_items.strip():
        argv += ["-I", playlist_items.strip()]
    argv += _advanced_args(options, archive_file)
    if options.advanced.extra_args.strip():
        argv += split_arguments(options.advanced.extra_args)
    argv += ["--", *urls]
    return argv


def user_args(argv: Sequence[str]) -> list[str]:
    """Strip the executable and the machine flags, leaving what the user would type."""
    args = list(argv[1:])
    flags = progress.MACHINE_FLAGS
    if args[: len(flags)] == flags:
        args = args[len(flags) :]
    return args


def mask_secrets(args: Sequence[str]) -> list[str]:
    masked: list[str] = []
    hide_next = False
    for arg in args:
        if hide_next:
            masked.append(MASK)
            hide_next = False
            continue
        name, eq, _value = arg.partition("=")
        if name in SECRET_OPTIONS and arg.startswith("--") and eq:
            masked.append(f"{name}={MASK}")
        elif arg in SECRET_OPTIONS:
            masked.append(arg)
            hide_next = True
        elif masked and masked[-1] == "--add-header" and arg.lower().startswith(SECRET_HEADERS):
            masked.append(arg.split(":", 1)[0] + ":" + MASK)
        else:
            masked.append(arg)
    return masked


def to_display(argv: Sequence[str], *, include_machine_flags: bool = False) -> str:
    """Render an argv as a copyable command line with secrets masked."""
    args = list(argv[1:]) if include_machine_flags else user_args(argv)
    return subprocess.list2cmdline([DISPLAY_EXE, *mask_secrets(args)])


def split_arguments(text: str) -> list[str]:
    """Split a command line typed by the user. Backslashes are literal (Windows paths)."""
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split = True
    lexer.escape = ""
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError as exc:
        raise ManualCommandError(str(exc)) from exc


def parse_manual(text: str, *, ytdlp: Path | None = None) -> list[str]:
    """Turn a manual command into a runnable argv with the progress flags the app needs."""
    args = split_arguments(text)
    if args and Path(args[0]).name.lower() in {"yt-dlp", "yt-dlp.exe"}:
        args = args[1:]
    if not args:
        raise ManualCommandError("no arguments")
    return [str(ytdlp or paths.ytdlp_exe()), *progress.MACHINE_FLAGS, *args]


def manual_argv(
    text: str, *, url: str = "", folder: str = "", ytdlp: Path | None = None
) -> list[str]:
    """Command-mode argv: the folder goes before the user's arguments (so their own ``-P``
    wins) and the optional URL goes last, after ``--``."""
    argv = parse_manual(text, ytdlp=ytdlp)
    head, user = argv[: 1 + len(progress.MACHINE_FLAGS)], argv[1 + len(progress.MACHINE_FLAGS) :]
    if folder.strip():
        head += ["-P", folder.strip()]
    tail = ["--", url.strip()] if url.strip() else []
    return [*head, *user, *tail]
