"""Named download presets stored as JSON, plus read-only built-in presets."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from easy_ytdlp.core import paths
from easy_ytdlp.core.options import DownloadOptions, Mode
from easy_ytdlp.core.settings import write_json_atomic

SCHEMA_VERSION = 1


@dataclass
class Preset:
    name: str
    options: DownloadOptions = field(default_factory=DownloadOptions)
    builtin: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "options": self.options.to_dict()}


def _builtin(name: str, **changes: Any) -> Preset:
    options = DownloadOptions()
    for path, value in changes.items():
        target: Any = options
        *parents, leaf = path.split("__")
        for parent in parents:
            target = getattr(target, parent)
        setattr(target, leaf, value)
    return Preset(name, options, builtin=True)


# Names are stable identifiers; the GUI translates them for display.
BUILTIN_PRESETS = [
    _builtin("Best video (MP4)"),
    _builtin("Video 1080p (MP4)", format__quality="1080"),
    _builtin(
        "Video 720p + subtitles",
        format__quality="720",
        subtitles__enabled=True,
        subtitles__embed=True,
    ),
    _builtin(
        "Music MP3 320 kbit/s",
        mode=Mode.AUDIO,
        audio__format="mp3",
        audio__bitrate="320",
        advanced__embed_thumbnail=True,
    ),
    _builtin("Audio, original format", mode=Mode.AUDIO, audio__format="best"),
    _builtin("Subtitles only", mode=Mode.SUBTITLES),
]


class PresetError(ValueError):
    """Invalid preset operation (e.g. duplicate name or a built-in preset)."""


class PresetStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or paths.presets_file()
        self._user: list[Preset] = self._load()

    def _load(self) -> list[Preset]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        items = data.get("presets") if isinstance(data, dict) else None
        result: list[Preset] = []
        for item in items or []:
            if (
                isinstance(item, dict)
                and isinstance(item.get("name"), str)
                and item["name"].strip()
            ):
                options = item.get("options") if isinstance(item.get("options"), dict) else {}
                result.append(Preset(item["name"].strip(), DownloadOptions.from_dict(options)))
        return result

    def _save(self) -> None:
        write_json_atomic(
            self.path,
            {"schema_version": SCHEMA_VERSION, "presets": [p.to_dict() for p in self._user]},
        )

    def all(self) -> list[Preset]:
        return [*BUILTIN_PRESETS, *self._user]

    def user_presets(self) -> list[Preset]:
        return list(self._user)

    def get(self, name: str) -> Preset | None:
        return next((p for p in self.all() if p.name == name), None)

    def _check_new_name(self, name: str) -> str:
        name = name.strip()
        if not name:
            raise PresetError("empty name")
        if self.get(name) is not None:
            raise PresetError("name exists")
        return name

    def save(self, name: str, options: DownloadOptions, *, overwrite: bool = False) -> Preset:
        """Create a user preset, or replace an existing user preset with ``overwrite``."""
        existing = self.get(name.strip())
        if existing is not None and overwrite and not existing.builtin:
            existing.options = options.copy()
            self._save()
            return existing
        preset = Preset(self._check_new_name(name), options.copy())
        self._user.append(preset)
        self._save()
        return preset

    def rename(self, name: str, new_name: str) -> Preset:
        preset = self._user_preset(name)
        if new_name.strip() != name:
            preset.name = self._check_new_name(new_name)
            self._save()
        return preset

    def duplicate(self, name: str, new_name: str) -> Preset:
        source = self.get(name)
        if source is None:
            raise PresetError("unknown preset")
        return self.save(new_name, source.options)

    def delete(self, name: str) -> None:
        preset = self._user_preset(name)
        self._user.remove(preset)
        self._save()

    def unique_name(self, base: str) -> str:
        """``base``, or ``base (2)``, ``base (3)``... whichever is free."""
        if self.get(base) is None:
            return base
        number = 2
        while self.get(f"{base} ({number})") is not None:
            number += 1
        return f"{base} ({number})"

    def _user_preset(self, name: str) -> Preset:
        preset = self.get(name)
        if preset is None:
            raise PresetError("unknown preset")
        if preset.builtin:
            raise PresetError("built-in presets are read-only")
        return preset
