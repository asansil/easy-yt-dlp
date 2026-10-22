"""Playlist item selections and their yt-dlp ``-I`` (``--playlist-items``) form."""

import re
from collections.abc import Iterable

_PART_RE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$")


class SelectionError(ValueError):
    """The range text cannot be understood."""


def parse_ranges(text: str, maximum: int) -> set[int]:
    """Parse "1-5, 8, 10-" style text into 1-based indices no greater than ``maximum``.

    An open range ("10-") runs to ``maximum``. Raises ``SelectionError`` on bad syntax.
    """
    result: set[int] = set()
    for part in text.split(","):
        if not part.strip():
            continue
        open_end = part.strip().endswith("-")
        match = _PART_RE.match(part.rstrip().rstrip("-") if open_end else part)
        if not match:
            raise SelectionError(part.strip())
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if open_end:
            end = maximum
        if start < 1 or end < start:
            raise SelectionError(part.strip())
        result.update(range(start, min(end, maximum) + 1))
    return result


def format_ranges(indices: Iterable[int]) -> str:
    """Compress indices into the shortest yt-dlp ``-I`` text, e.g. ``1-3,7,9-10``."""
    ordered = sorted(set(indices))
    parts: list[str] = []
    i = 0
    while i < len(ordered):
        start = end = ordered[i]
        while i + 1 < len(ordered) and ordered[i + 1] == end + 1:
            i += 1
            end = ordered[i]
        parts.append(str(start) if start == end else f"{start}-{end}")
        i += 1
    return ",".join(parts)
