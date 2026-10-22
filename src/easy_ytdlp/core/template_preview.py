"""Approximate preview of yt-dlp output templates, for the live file-name preview.

It understands the common forms: ``%(field)s``, alternatives ``%(a,b)s``, defaults
``%(field|default)s``, replacements ``%(field&text|default)s``, and ``%(field).Ns``
truncation. Anything else is shown as-is; yt-dlp has the final word.
"""

import contextlib
import re
from datetime import datetime
from pathlib import PureWindowsPath
from typing import Any

from easy_ytdlp.core.options import DownloadOptions, Mode

_FIELD_RE = re.compile(r"%\((?P<body>[^)]*)\)(?P<format>[-#0 +]*\d*(?:\.\d+)?[a-zA-Z])")
# Characters Windows does not allow in file names; yt-dlp swaps them for lookalikes.
_INVALID = str.maketrans({c: "_" for c in '<>:"/\\|?*'})

SAMPLE_FIELDS: dict[str, Any] = {
    "title": "Video title",
    "id": "dQw4w9WgXcQ",
    "uploader": "Uploader",
    "channel": "Channel",
    "upload_date": "20240131",
    "playlist_title": None,
    "playlist_index": None,
    "playlist": None,
}


def output_ext(options: DownloadOptions) -> str:
    if options.mode == Mode.AUDIO:
        return options.audio.format if options.audio.format != "best" else "m4a"
    if options.mode == Mode.SUBTITLES:
        return f"en.{options.subtitles.format}"
    return options.format.container


def _value(body: str, fields: dict[str, Any]) -> str:
    default: str | None = None
    if "|" in body:
        body, default = body.split("|", 1)
    replacement: str | None = None
    if "&" in body:
        body, replacement = body.split("&", 1)
    date_format: str | None = None
    if ">" in body:
        body, date_format = body.split(">", 1)
    value = None
    for name in body.split(","):
        candidate = fields.get(name.strip())
        if candidate not in (None, ""):
            value = candidate
            break
    if value is None:
        return default if default is not None else "NA"
    if date_format is not None:
        with contextlib.suppress(ValueError):
            value = datetime.strptime(str(value), "%Y%m%d").strftime(date_format)
    if replacement is not None:
        return replacement.replace("{}", str(value))
    return str(value)


def render(template: str, fields: dict[str, Any]) -> str:
    def substitute(match: re.Match[str]) -> str:
        text = _value(match.group("body"), fields)
        fmt = match.group("format")
        precision = re.search(r"\.(\d+)", fmt)
        if precision:
            text = text[: int(precision.group(1))]
        if fmt.endswith("d") and text.isdigit():
            width = re.match(r"0?(\d+)", fmt)
            if width and fmt.startswith("0"):
                text = text.zfill(int(width.group(1)))
        # Field values become file-name text: no folder separators inside them.
        return text.translate(_INVALID)

    return _FIELD_RE.sub(substitute, template)


def preview(
    options: DownloadOptions,
    output_template: str,
    fields: dict[str, Any] | None = None,
) -> str:
    """The path a download would get, relative to the destination folder."""
    values = {**SAMPLE_FIELDS, **(fields or {}), "ext": output_ext(options)}
    rendered = render(output_template, values).replace("/", "\\")
    parts = [p for p in PureWindowsPath(rendered).parts if p not in ("", ".")]
    return "\\".join(parts)
