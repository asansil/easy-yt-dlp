"""Analyze a URL with ``yt-dlp -J --flat-playlist`` before downloading it."""

import json
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from easy_ytdlp.core import paths
from easy_ytdlp.core.runner import CREATE_NO_WINDOW, process_env

PROBE_TIMEOUT = 180


class MediaKind(StrEnum):
    VIDEO = "video"
    PLAYLIST = "playlist"
    CHANNEL = "channel"


@dataclass(frozen=True)
class FormatInfo:
    format_id: str
    ext: str
    height: int | None
    vcodec: str | None
    acodec: str | None
    filesize: int | None

    @property
    def has_video(self) -> bool:
        return bool(self.vcodec) and self.vcodec != "none"

    @property
    def has_audio(self) -> bool:
        return bool(self.acodec) and self.acodec != "none"


@dataclass(frozen=True)
class Entry:
    """One item of a playlist or channel; ``index`` is 1-based, as yt-dlp's ``-I``."""

    index: int
    id: str
    title: str
    url: str
    duration: float | None
    uploader: str | None


@dataclass
class MediaInfo:
    kind: MediaKind
    id: str
    title: str
    url: str
    uploader: str | None = None
    duration: float | None = None
    thumbnail: str | None = None
    extractor: str = ""
    formats: list[FormatInfo] = field(default_factory=list)
    entries: list[Entry] = field(default_factory=list)
    subtitles: list[str] = field(default_factory=list)
    auto_captions: list[str] = field(default_factory=list)
    count: int | None = None

    @property
    def heights(self) -> list[int]:
        """Available video heights, highest first."""
        found = {f.height for f in self.formats if f.has_video and f.height}
        return sorted(found, reverse=True)

    @property
    def is_collection(self) -> bool:
        return self.kind != MediaKind.VIDEO


class ProbeError(Exception):
    """yt-dlp could not analyze the URL. ``details`` holds its raw output."""

    def __init__(self, message: str, details: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.details = details


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _thumbnail(data: dict[str, Any]) -> str | None:
    if isinstance(data.get("thumbnail"), str):
        return data["thumbnail"]
    thumbs = [t for t in data.get("thumbnails") or [] if isinstance(t, dict) and t.get("url")]
    if not thumbs:
        return None
    best = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
    return best["url"]


def _kind(data: dict[str, Any]) -> MediaKind:
    if data.get("_type") not in {"playlist", "multi_video"}:
        return MediaKind.VIDEO
    channel_id = data.get("channel_id")
    if channel_id and data.get("id") == channel_id:
        return MediaKind.CHANNEL
    return MediaKind.PLAYLIST


def _formats(data: dict[str, Any]) -> list[FormatInfo]:
    result = []
    for f in data.get("formats") or []:
        if not isinstance(f, dict) or f.get("format_id") is None:
            continue
        height = f.get("height")
        size = f.get("filesize") or f.get("filesize_approx")
        result.append(
            FormatInfo(
                format_id=str(f["format_id"]),
                ext=str(f.get("ext") or ""),
                height=int(height) if isinstance(height, int | float) else None,
                vcodec=f.get("vcodec"),
                acodec=f.get("acodec"),
                filesize=int(size) if isinstance(size, int | float) else None,
            )
        )
    return result


def _entries(data: dict[str, Any]) -> list[Entry]:
    entries = []
    for position, item in enumerate(data.get("entries") or [], start=1):
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("webpage_url") or item.get("id") or ""
        entries.append(
            Entry(
                index=position,
                id=str(item.get("id") or ""),
                title=str(item.get("title") or item.get("id") or ""),
                url=str(url),
                duration=_float(item.get("duration")),
                uploader=item.get("uploader") or item.get("channel"),
            )
        )
    return entries


def parse_info(data: dict[str, Any], url: str = "") -> MediaInfo:
    """Build a ``MediaInfo`` from the JSON printed by ``yt-dlp -J --flat-playlist``."""
    kind = _kind(data)
    entries = _entries(data) if kind != MediaKind.VIDEO else []
    count = data.get("playlist_count")
    return MediaInfo(
        kind=kind,
        id=str(data.get("id") or ""),
        title=str(data.get("title") or data.get("id") or url),
        url=str(data.get("webpage_url") or data.get("original_url") or url),
        uploader=data.get("uploader") or data.get("channel"),
        duration=_float(data.get("duration")),
        thumbnail=_thumbnail(data),
        extractor=str(data.get("extractor_key") or data.get("extractor") or ""),
        formats=_formats(data),
        entries=entries,
        subtitles=sorted(data.get("subtitles") or {}),
        auto_captions=sorted(data.get("automatic_captions") or {}),
        count=int(count) if isinstance(count, int) else (len(entries) if entries else None),
    )


def error_message(output: str) -> str:
    """The most useful line of a failed yt-dlp run."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("ERROR:"):
            return line[len("ERROR:") :].strip()
    return lines[-1] if lines else "yt-dlp failed without output"


def probe_argv(url: str, ytdlp: Path | None = None, extra: list[str] | None = None) -> list[str]:
    return [
        str(ytdlp or paths.ytdlp_exe()),
        "-J",
        "--flat-playlist",
        "--no-warnings",
        *(extra or []),
        "--",
        url,
    ]


def analyze(
    url: str,
    *,
    ytdlp: Path | None = None,
    extra: list[str] | None = None,
    run=subprocess.run,
    timeout: float = PROBE_TIMEOUT,
) -> MediaInfo:
    """Run yt-dlp on ``url`` and parse the result. Raises ``ProbeError`` on failure."""
    argv = probe_argv(url, ytdlp, extra)
    try:
        result = run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=process_env(),
            creationflags=CREATE_NO_WINDOW,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ProbeError("yt-dlp is not installed", str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("yt-dlp did not answer in time", str(exc)) from exc
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    if result.returncode != 0 or not stdout.strip():
        raise ProbeError(error_message(stderr or stdout), stderr)
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError("yt-dlp returned invalid data", stdout[:2000]) from exc
    if not isinstance(data, dict):
        raise ProbeError("yt-dlp returned invalid data", stdout[:2000])
    return parse_info(data, url)
