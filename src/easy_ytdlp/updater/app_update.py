"""Self-update: find a newer release on GitHub, download and verify its Setup, run it.

Never downgrades. The Setup must be named ``EasyYtDlp-Setup-<version>.exe`` and come with
a ``.sha256`` file; the download is refused when the hash does not match.
"""

import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from easy_ytdlp.core.runner import CREATE_NO_WINDOW
from easy_ytdlp.tools.download import (
    DownloadError,
    ProgressCallback,
    download_file,
    fetch_json,
    fetch_text,
    parse_checksum,
)
from easy_ytdlp.updater.versions import Version, parse

REPO = "asansil/easy-yt-dlp"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases"
UPDATE_URL_ENV = "EASYYTDLP_UPDATE_URL"
CHECK_INTERVAL = 24 * 3600
SETUP_PREFIX = "EasyYtDlp-Setup-"
INSTALLER_ARGS = [
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/CLOSEAPPLICATIONS",
    "/NORESTART",
    "/RELAUNCH=1",
]
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0)


@dataclass(frozen=True)
class Release:
    version: Version
    tag: str
    name: str
    notes: str
    url: str
    setup_name: str
    setup_url: str
    checksum_url: str

    @property
    def prerelease(self) -> bool:
        return self.version.is_prerelease


def releases_url() -> str:
    return os.environ.get(UPDATE_URL_ENV) or RELEASES_URL


def _assets(data: dict[str, Any]) -> dict[str, str]:
    result = {}
    for asset in data.get("assets") or []:
        if isinstance(asset, dict) and asset.get("name") and asset.get("browser_download_url"):
            result[str(asset["name"])] = str(asset["browser_download_url"])
    return result


def parse_release(data: dict[str, Any]) -> Release | None:
    """A release usable for updating, or None (drafts, odd tags, missing assets)."""
    if not isinstance(data, dict) or data.get("draft"):
        return None
    tag = str(data.get("tag_name") or "")
    version = parse(tag)
    if version is None:
        return None
    assets = _assets(data)
    # Accept the PEP 440 spelling (what the build produces) or the tag spelling.
    for candidate in (version.pep440(), tag.lstrip("v")):
        setup = f"{SETUP_PREFIX}{candidate}.exe"
        if setup in assets and f"{setup}.sha256" in assets:
            return Release(
                version=version,
                tag=tag,
                name=str(data.get("name") or tag),
                notes=str(data.get("body") or ""),
                url=str(data.get("html_url") or ""),
                setup_name=setup,
                setup_url=assets[setup],
                checksum_url=assets[f"{setup}.sha256"],
            )
    return None


def find_update(
    current: str,
    *,
    include_prereleases: bool = False,
    skipped: str = "",
    url: str | None = None,
) -> Release | None:
    """The newest usable release newer than ``current``, or None."""
    data = fetch_json(url or releases_url())
    if not isinstance(data, list):
        raise DownloadError("Unexpected answer from GitHub")
    current_version = parse(current)
    if current_version is None:
        raise ValueError(f"Bad current version {current!r}")
    candidates = []
    for item in data:
        release = parse_release(item)
        if release is None:
            continue
        if release.prerelease and not include_prereleases:
            continue
        candidates.append(release)
    if not candidates:
        return None
    best = max(candidates, key=lambda r: r.version)
    if best.version <= current_version:
        return None
    if skipped and parse(skipped) == best.version:
        return None
    return best


def check_due(last_check: float, now: float | None = None) -> bool:
    return (now or time.time()) - last_check >= CHECK_INTERVAL


def download_setup(
    release: Release,
    folder: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> Path:
    """Download the Setup into ``folder`` and verify its SHA-256."""
    expected = parse_checksum(fetch_text(release.checksum_url), release.setup_name)
    return download_file(
        release.setup_url,
        folder / release.setup_name,
        expected_sha256=expected,
        progress=progress,
        cancel=cancel,
    )


def launch_installer(setup: Path, popen=subprocess.Popen) -> None:
    """Start the Setup silently, detached; the caller must quit right after."""
    popen(
        [str(setup), *INSTALLER_ARGS],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
        close_fds=True,
    )
