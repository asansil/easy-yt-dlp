"""Shared pieces of the external tools (yt-dlp, FFmpeg, deno)."""

import re
import subprocess
import tempfile
import threading
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from easy_ytdlp.core import paths
from easy_ytdlp.core.runner import CREATE_NO_WINDOW, process_env
from easy_ytdlp.tools.download import ProgressCallback

GITHUB_API = "https://api.github.com/repos"
GITHUB_DOWNLOAD = "https://github.com"


@dataclass(frozen=True)
class ToolStatus:
    name: str
    installed: str | None
    latest: str | None

    @property
    def missing(self) -> bool:
        return self.installed is None

    @property
    def update_available(self) -> bool:
        return self.latest is not None and self.installed != self.latest


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def run_version(argv: Sequence[str], timeout: float = 20) -> str | None:
    """Run ``<tool> --version`` style commands; None when the tool is missing or broken."""
    try:
        result = subprocess.run(
            list(argv),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=process_env(),
            creationflags=CREATE_NO_WINDOW,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip() or None


class Tool(ABC):
    """An external executable the app downloads, verifies and keeps up to date."""

    name: str
    executables: tuple[str, ...]

    def __init__(self, tools_dir: Path | None = None) -> None:
        self.tools_dir = tools_dir or paths.tools_dir()

    def path(self, executable: str | None = None) -> Path:
        return self.tools_dir / (executable or self.executables[0])

    def is_installed(self) -> bool:
        return all(self.path(exe).is_file() for exe in self.executables)

    @abstractmethod
    def installed_version(self) -> str | None: ...

    @abstractmethod
    def latest_version(self, channel: str = "stable") -> str: ...

    @abstractmethod
    def install(
        self,
        channel: str = "stable",
        *,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> str:
        """Download, verify and install the latest version; return it."""

    def status(self, channel: str = "stable", *, check_latest: bool = True) -> ToolStatus:
        installed = self.installed_version() if self.is_installed() else None
        latest = self.latest_version(channel) if check_latest else None
        return ToolStatus(self.name, installed, latest)

    def temp_dir(self) -> tempfile.TemporaryDirectory:
        """A scratch folder next to the tools folder, so the final move stays on one disk."""
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix=".download-", dir=self.tools_dir.parent)
