"""The set of external tools the app manages."""

from pathlib import Path

from easy_ytdlp.tools.base import Tool
from easy_ytdlp.tools.deno import Deno
from easy_ytdlp.tools.ffmpeg import Ffmpeg
from easy_ytdlp.tools.ytdlp import YtDlp


def all_tools(tools_dir: Path | None = None) -> list[Tool]:
    """yt-dlp first: it is the only tool the app cannot work without."""
    return [YtDlp(tools_dir), Ffmpeg(tools_dir), Deno(tools_dir)]


def missing_tools(tools_dir: Path | None = None) -> list[Tool]:
    return [tool for tool in all_tools(tools_dir) if not tool.is_installed()]
