from pathlib import Path

import pytest

from easy_ytdlp.tools import migration, path_env

ENTRY = r"C:\Users\me\AppData\Local\EasyYtDlp\bin"


class FakeRegistry:
    def __init__(self, value: str, kind: int = path_env.REG_EXPAND_SZ) -> None:
        self.value = value
        self.kind = kind
        self.writes = 0
        self.broadcasts = 0

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(path_env, "read_user_path", lambda: (self.value, self.kind))
        monkeypatch.setattr(path_env, "write_user_path", self.write)
        monkeypatch.setattr(path_env, "refresh_environment", self.refresh)

    def write(self, value: str, kind: int = path_env.REG_EXPAND_SZ) -> None:
        self.value, self.kind = value, kind
        self.writes += 1

    def refresh(self) -> None:
        self.broadcasts += 1


def test_with_entry_appends_once() -> None:
    assert (
        path_env.with_entry(r"%USERPROFILE%\bin;C:\x", ENTRY) == rf"%USERPROFILE%\bin;C:\x;{ENTRY}"
    )
    assert path_env.with_entry(f"C:\\x;{ENTRY.upper()}\\", ENTRY) is None
    assert path_env.with_entry("", ENTRY) == ENTRY


def test_without_entry_keeps_others() -> None:
    value = rf"C:\a;{ENTRY};;%SystemRoot%\b;"
    assert path_env.without_entry(value, ENTRY.lower()) == r"C:\a;%SystemRoot%\b"
    assert path_env.without_entry(r"C:\a", ENTRY) is None


def test_contains_expands_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\me\AppData\Local")
    assert path_env.contains(r"%LOCALAPPDATA%\EasyYtDlp\bin", ENTRY)
    assert path_env.contains(rf'"{ENTRY}"', ENTRY)


def test_add_and_remove_preserve_type(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = FakeRegistry(r"%SystemRoot%\x", path_env.REG_SZ)
    registry.install(monkeypatch)
    assert path_env.add_to_user_path(ENTRY)
    assert registry.value == rf"%SystemRoot%\x;{ENTRY}"
    assert registry.kind == path_env.REG_SZ
    assert not path_env.add_to_user_path(ENTRY)
    assert path_env.is_in_user_path(ENTRY)
    assert path_env.remove_from_user_path(ENTRY)
    assert registry.value == r"%SystemRoot%\x"
    assert not path_env.remove_from_user_path(ENTRY)
    assert (registry.writes, registry.broadcasts) == (2, 2)


def test_real_registry_read_is_a_string() -> None:
    value, kind = path_env.read_user_path()
    assert isinstance(value, str)
    assert kind in (path_env.REG_SZ, path_env.REG_EXPAND_SZ)


def test_legacy_detection_and_removal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    legacy = tmp_path / ".ytdlp_env"
    registry = FakeRegistry(rf"C:\a;{legacy}")
    registry.install(monkeypatch)
    assert migration.legacy_present(legacy)

    legacy.mkdir()
    for name in migration.LEGACY_FILES:
        (legacy / name).write_bytes(b"x")
    assert migration.remove_legacy(legacy) == []
    assert registry.value == r"C:\a"
    assert not legacy.exists()
    assert not migration.legacy_present(legacy)


def test_legacy_removal_keeps_unknown_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    FakeRegistry("").install(monkeypatch)
    legacy = tmp_path / ".ytdlp_env"
    legacy.mkdir()
    (legacy / "yt-dlp.exe").write_bytes(b"x")
    (legacy / "notes.txt").write_text("mine")
    assert migration.remove_legacy(legacy) == []
    assert sorted(p.name for p in legacy.iterdir()) == ["notes.txt"]
