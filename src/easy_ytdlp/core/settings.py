"""User settings stored as JSON in the data folder, with a schema version and migrations."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from easy_ytdlp.core import paths

SCHEMA_VERSION = 1


@dataclass
class Settings:
    schema_version: int = SCHEMA_VERSION
    # "system", "en" or "es".
    language: str = "system"
    # "system", "light" or "dark".
    theme: str = "system"
    download_dir: str = ""
    max_concurrent: int = 2
    default_preset: str = ""
    # yt-dlp release channel: "stable" or "nightly".
    ytdlp_channel: str = "stable"
    auto_update_tools: bool = True
    last_tools_check: float = 0.0
    check_app_updates: bool = True
    beta_updates: bool = False
    last_app_check: float = 0.0
    skipped_app_version: str = ""
    first_run_done: bool = False
    legacy_prompt_done: bool = False
    # Last used download options, restored on startup.
    last_options: dict[str, Any] = field(default_factory=dict)
    command_history: list[str] = field(default_factory=list)
    window_geometry: str = ""
    last_page: int = 0

    def effective_download_dir(self) -> Path:
        return Path(self.download_dir) if self.download_dir else paths.default_download_dir()


# Each function upgrades a settings dict from version N to N + 1.
MIGRATIONS: dict[int, Any] = {}


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("schema_version")
    if not isinstance(version, int) or version < 1:
        version = 1
    while version < SCHEMA_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
    data["schema_version"] = SCHEMA_VERSION
    return data


def from_dict(data: dict[str, Any]) -> Settings:
    settings = Settings()
    for f in fields(Settings):
        if f.name not in data:
            continue
        value = data[f.name]
        default = getattr(settings, f.name)
        # bool is an int subclass, so check it first.
        if isinstance(default, bool):
            ok = isinstance(value, bool)
        elif isinstance(default, float):
            ok = isinstance(value, int | float) and not isinstance(value, bool)
            value = float(value) if ok else value
        elif isinstance(default, int):
            ok = isinstance(value, int) and not isinstance(value, bool)
        else:
            ok = isinstance(value, type(default))
        if ok:
            setattr(settings, f.name, value)
    settings.max_concurrent = min(max(settings.max_concurrent, 1), 8)
    return settings


def load(path: Path | None = None) -> Settings:
    """Load settings; a missing or corrupt file yields the defaults."""
    path = path or paths.settings_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    return from_dict(migrate(data))


def write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON to a temp file in the same folder, then replace the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def save(settings: Settings, path: Path | None = None) -> None:
    write_json_atomic(path or paths.settings_file(), asdict(settings))
