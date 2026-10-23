"""Parsing of yt-dlp output into typed events.

The command builder asks yt-dlp to print machine-readable lines with a known prefix:

    [easyytdlp:download] {progress JSON} {info JSON}
    [easyytdlp:postprocess] {progress JSON} {info JSON}
    [easyytdlp:file] "final path as JSON string"

Every other line is passed through as a log line, with errors and warnings recognized.
"""

import json
from dataclasses import dataclass

TAG = "easyytdlp"
DOWNLOAD_PREFIX = f"[{TAG}:download] "
POSTPROCESS_PREFIX = f"[{TAG}:postprocess] "
FILE_PREFIX = f"[{TAG}:file] "

_INFO_FIELDS = "id,title,playlist_index,playlist_autonumber,n_entries"
DOWNLOAD_TEMPLATE = (
    f"download:{DOWNLOAD_PREFIX}"
    "%(progress.{status,downloaded_bytes,total_bytes,total_bytes_estimate,speed,eta,"
    "fragment_index,fragment_count})j "
    f"%(info.{{{_INFO_FIELDS}}})j"
)
POSTPROCESS_TEMPLATE = (
    f"postprocess:{POSTPROCESS_PREFIX}%(progress.{{status,postprocessor}})j "
    f"%(info.{{{_INFO_FIELDS}}})j"
)
FILE_PRINT = f"after_move:{FILE_PREFIX}%(filepath)j"

# Flags the app needs to follow a download; added to every generated or manual command.
MACHINE_FLAGS = [
    "--newline",
    "--no-quiet",
    "--progress",
    "--progress-template",
    DOWNLOAD_TEMPLATE,
    "--progress-template",
    POSTPROCESS_TEMPLATE,
    "--print",
    FILE_PRINT,
]


@dataclass(frozen=True)
class ItemInfo:
    """The playlist item (or single video) an event belongs to."""

    id: str = ""
    title: str = ""
    index: int | None = None
    count: int | None = None


@dataclass(frozen=True)
class DownloadProgress:
    status: str
    downloaded_bytes: int
    total_bytes: int | None
    speed: float | None
    eta: int | None
    item: ItemInfo

    @property
    def fraction(self) -> float | None:
        """Progress of the current file, from 0 to 1, or None when the size is unknown."""
        if self.status == "finished":
            return 1.0
        if not self.total_bytes:
            return None
        return min(self.downloaded_bytes / self.total_bytes, 1.0)


@dataclass(frozen=True)
class PostProcess:
    status: str
    postprocessor: str
    item: ItemInfo


@dataclass(frozen=True)
class FileFinished:
    path: str


@dataclass(frozen=True)
class ErrorLine:
    message: str


@dataclass(frozen=True)
class WarningLine:
    message: str


@dataclass(frozen=True)
class LogLine:
    text: str


type Event = DownloadProgress | PostProcess | FileFinished | ErrorLine | WarningLine | LogLine


def _split_json_pair(text: str) -> tuple[dict, dict]:
    decoder = json.JSONDecoder()
    first, end = decoder.raw_decode(text)
    rest = text[end:].lstrip()
    second = decoder.raw_decode(rest)[0] if rest else {}
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise ValueError("expected two JSON objects")
    return first, second


def _int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return int(value)


def _float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _item(info: dict) -> ItemInfo:
    index = _int(info.get("playlist_autonumber")) or _int(info.get("playlist_index"))
    return ItemInfo(
        id=str(info.get("id") or ""),
        title=str(info.get("title") or ""),
        index=index,
        count=_int(info.get("n_entries")),
    )


def parse_line(line: str) -> Event:
    """Turn one output line into an event. Never raises."""
    text = line.rstrip("\r\n")
    try:
        if text.startswith(DOWNLOAD_PREFIX):
            progress, info = _split_json_pair(text[len(DOWNLOAD_PREFIX) :])
            return DownloadProgress(
                status=str(progress.get("status") or ""),
                downloaded_bytes=_int(progress.get("downloaded_bytes")) or 0,
                total_bytes=_int(progress.get("total_bytes"))
                or _int(progress.get("total_bytes_estimate")),
                speed=_float(progress.get("speed")),
                eta=_int(progress.get("eta")),
                item=_item(info),
            )
        if text.startswith(POSTPROCESS_PREFIX):
            progress, info = _split_json_pair(text[len(POSTPROCESS_PREFIX) :])
            return PostProcess(
                status=str(progress.get("status") or ""),
                postprocessor=str(progress.get("postprocessor") or ""),
                item=_item(info),
            )
        if text.startswith(FILE_PREFIX):
            path = json.loads(text[len(FILE_PREFIX) :])
            if isinstance(path, str):
                return FileFinished(path)
    except (ValueError, TypeError):
        pass
    if text.startswith("ERROR:"):
        return ErrorLine(text[len("ERROR:") :].strip())
    if text.startswith("WARNING:"):
        return WarningLine(text[len("WARNING:") :].strip())
    return LogLine(text)
