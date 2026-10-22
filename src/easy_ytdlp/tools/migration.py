"""Clean-up of the v1 installation (``~/.ytdlp_env`` and its PATH entry)."""

from pathlib import Path

from easy_ytdlp.core import paths
from easy_ytdlp.tools import path_env

# The only files v1 ever wrote to its folder.
LEGACY_FILES = ("yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe")


def legacy_present(env_dir: Path | None = None) -> bool:
    env_dir = env_dir or paths.legacy_env_dir()
    try:
        in_path = path_env.is_in_user_path(env_dir)
    except OSError:
        in_path = False
    return env_dir.is_dir() or in_path


def remove_legacy(env_dir: Path | None = None) -> list[str]:
    """Remove the v1 PATH entry and the v1 files. Returns what could not be removed.

    Unknown files are left untouched, and the folder is removed only when it ends up empty.
    """
    env_dir = env_dir or paths.legacy_env_dir()
    problems: list[str] = []
    try:
        path_env.remove_from_user_path(env_dir)
    except (OSError, RuntimeError):
        problems.append("PATH")
    for name in LEGACY_FILES:
        try:
            (env_dir / name).unlink(missing_ok=True)
        except OSError:
            problems.append(name)
    try:
        if env_dir.is_dir() and not any(env_dir.iterdir()):
            env_dir.rmdir()
    except OSError:
        problems.append(str(env_dir))
    return problems
