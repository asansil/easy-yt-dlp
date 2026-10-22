"""yt-dlp: the download engine, from its official GitHub releases (stable or nightly)."""

import threading

from easy_ytdlp.core.paths import YTDLP_EXE
from easy_ytdlp.tools.base import GITHUB_API, GITHUB_DOWNLOAD, Tool, run_version
from easy_ytdlp.tools.download import (
    DownloadError,
    ProgressCallback,
    download_file,
    fetch_json,
    fetch_text,
    parse_checksum,
)

CHANNELS = {
    "stable": "yt-dlp/yt-dlp",
    "nightly": "yt-dlp/yt-dlp-nightly-builds",
}


def latest_tag(repo: str) -> str:
    data = fetch_json(f"{GITHUB_API}/{repo}/releases/latest")
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not isinstance(tag, str) or not tag:
        raise DownloadError(f"No release found for {repo}")
    return tag


class YtDlp(Tool):
    name = "yt-dlp"
    executables = (YTDLP_EXE,)

    def installed_version(self) -> str | None:
        return run_version([str(self.path()), "--version"])

    def latest_version(self, channel: str = "stable") -> str:
        return latest_tag(CHANNELS.get(channel, CHANNELS["stable"]))

    def install(
        self,
        channel: str = "stable",
        *,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> str:
        repo = CHANNELS.get(channel, CHANNELS["stable"])
        tag = latest_tag(repo)
        base = f"{GITHUB_DOWNLOAD}/{repo}/releases/download/{tag}"
        expected = parse_checksum(fetch_text(f"{base}/SHA2-256SUMS"), YTDLP_EXE)
        download_file(
            f"{base}/{YTDLP_EXE}",
            self.path(),
            expected_sha256=expected,
            progress=progress,
            cancel=cancel,
        )
        return tag
