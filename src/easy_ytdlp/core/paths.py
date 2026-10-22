"""Well-known locations used by Easy yt-dlp.

Every path the app reads or writes is defined here, so tests and the packaging smoke
scripts can redirect them with environment variables.
"""

import os
import sys
from pathlib import Path

APP_DIR_NAME = "EasyYtDlp"
INSTALL_DIR_NAME = "Easy yt-dlp"

DATA_DIR_ENV = "EASYYTDLP_DATA_DIR"
TOOLS_DIR_ENV = "EASYYTDLP_TOOLS_DIR"

YTDLP_EXE = "yt-dlp.exe"
FFMPEG_EXE = "ffmpeg.exe"
FFPROBE_EXE = "ffprobe.exe"
DENO_EXE = "deno.exe"


def _env_dir(name: str, fallback_env: str, fallback: Path) -> Path:
    override = os.environ.get(name)
    if override:
        return Path(override)
    base = os.environ.get(fallback_env)
    return Path(base) / fallback if base else Path.home() / fallback


def local_app_data() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) if base else Path.home() / "AppData" / "Local"


def install_dir() -> Path:
    """Folder that holds the installed application (or the frozen executable's folder)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return local_app_data() / "Programs" / INSTALL_DIR_NAME


def tools_dir() -> Path:
    """Folder with yt-dlp, FFmpeg and deno; the PATH entry points here."""
    override = os.environ.get(TOOLS_DIR_ENV)
    if override:
        return Path(override)
    return local_app_data() / APP_DIR_NAME / "bin"


def tools_root() -> Path:
    """Parent of the tools folder; removed by the uninstaller on request."""
    return tools_dir().parent


def data_dir() -> Path:
    """Folder with settings, presets, history and logs."""
    return _env_dir(DATA_DIR_ENV, "APPDATA", Path(APP_DIR_NAME))


def logs_dir() -> Path:
    return data_dir() / "logs"


def settings_file() -> Path:
    return data_dir() / "settings.json"


def presets_file() -> Path:
    return data_dir() / "presets.json"


def history_file() -> Path:
    return data_dir() / "history.sqlite"


def ytdlp_exe() -> Path:
    return tools_dir() / YTDLP_EXE


def ffmpeg_exe() -> Path:
    return tools_dir() / FFMPEG_EXE


def ffprobe_exe() -> Path:
    return tools_dir() / FFPROBE_EXE


def deno_exe() -> Path:
    return tools_dir() / DENO_EXE


def legacy_env_dir() -> Path:
    """Tools folder used by v1, which v2 offers to remove."""
    return Path.home() / ".ytdlp_env"


def default_download_dir() -> Path:
    return Path.home() / "Downloads"


def ensure_dirs() -> None:
    """Create the data, logs and tools folders if they are missing."""
    for path in (data_dir(), logs_dir(), tools_dir()):
        path.mkdir(parents=True, exist_ok=True)
