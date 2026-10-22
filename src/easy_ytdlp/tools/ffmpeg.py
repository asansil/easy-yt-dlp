"""FFmpeg and FFprobe, from gyan.dev's "release essentials" build (logic ported from v1)."""

import re
import threading
from pathlib import Path

from easy_ytdlp.core.paths import FFMPEG_EXE, FFPROBE_EXE
from easy_ytdlp.tools.base import Tool, run_version
from easy_ytdlp.tools.download import (
    ProgressCallback,
    download_file,
    extract_member,
    fetch_text,
    parse_checksum,
)

BUILDS = "https://www.gyan.dev/ffmpeg/builds"
ZIP_URL = f"{BUILDS}/ffmpeg-release-essentials.zip"
SHA_URL = f"{ZIP_URL}.sha256"
VERSION_URL = f"{BUILDS}/release-version"

_VERSION_RE = re.compile(r"ffmpeg version (\d+(?:\.\d+)*)")


def parse_version(output: str | None) -> str | None:
    match = _VERSION_RE.search(output or "")
    return match.group(1) if match else None


class Ffmpeg(Tool):
    name = "FFmpeg"
    executables = (FFMPEG_EXE, FFPROBE_EXE)

    def installed_version(self) -> str | None:
        return parse_version(run_version([str(self.path()), "-version"]))

    def latest_version(self, channel: str = "stable") -> str:
        return fetch_text(VERSION_URL).strip()

    def install(
        self,
        channel: str = "stable",
        *,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> str:
        version = self.latest_version()
        expected = parse_checksum(fetch_text(SHA_URL))
        with self.temp_dir() as tmp:
            archive = download_file(
                ZIP_URL,
                Path(tmp) / "ffmpeg.zip",
                expected_sha256=expected,
                progress=progress,
                cancel=cancel,
            )
            for exe in self.executables:
                extract_member(archive, rf"[^/]+/bin/{re.escape(exe)}", self.path(exe))
        return version
