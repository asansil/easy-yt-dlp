"""deno: the JavaScript runtime yt-dlp needs to solve YouTube's challenges.

yt-dlp finds ``deno.exe`` automatically when it sits next to ``yt-dlp.exe``.
"""

import re
import threading
from pathlib import Path

from easy_ytdlp.core.paths import DENO_EXE
from easy_ytdlp.tools.base import GITHUB_DOWNLOAD, Tool, run_version
from easy_ytdlp.tools.download import (
    ProgressCallback,
    download_file,
    extract_member,
    fetch_text,
    parse_checksum,
)
from easy_ytdlp.tools.ytdlp import latest_tag

REPO = "denoland/deno"
ASSET = "deno-x86_64-pc-windows-msvc.zip"

_VERSION_RE = re.compile(r"deno (\d+(?:\.\d+)*)")


def parse_version(output: str | None) -> str | None:
    match = _VERSION_RE.search(output or "")
    return match.group(1) if match else None


class Deno(Tool):
    name = "deno"
    executables = (DENO_EXE,)

    def installed_version(self) -> str | None:
        return parse_version(run_version([str(self.path()), "--version"]))

    def latest_version(self, channel: str = "stable") -> str:
        return latest_tag(REPO).lstrip("v")

    def install(
        self,
        channel: str = "stable",
        *,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> str:
        tag = latest_tag(REPO)
        base = f"{GITHUB_DOWNLOAD}/{REPO}/releases/download/{tag}"
        # The published file is PowerShell Get-FileHash output; parse_checksum handles it.
        expected = parse_checksum(fetch_text(f"{base}/{ASSET}.sha256sum"))
        with self.temp_dir() as tmp:
            archive = download_file(
                f"{base}/{ASSET}",
                Path(tmp) / ASSET,
                expected_sha256=expected,
                progress=progress,
                cancel=cancel,
            )
            extract_member(archive, re.escape(DENO_EXE), self.path())
        return tag.lstrip("v")
