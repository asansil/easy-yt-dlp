from pathlib import Path

import pytest

from easy_ytdlp.core import paths


def test_overrides_from_environment(isolated_dirs: Path) -> None:
    assert paths.data_dir() == isolated_dirs / "data"
    assert paths.tools_dir() == isolated_dirs / "tools" / "bin"
    assert paths.ytdlp_exe() == isolated_dirs / "tools" / "bin" / "yt-dlp.exe"
    assert paths.settings_file().parent == paths.data_dir()


def test_defaults_follow_windows_folders(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("EASYYTDLP_DATA_DIR")
    monkeypatch.delenv("EASYYTDLP_TOOLS_DIR")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert paths.data_dir() == tmp_path / "Roaming" / "EasyYtDlp"
    assert paths.tools_dir() == tmp_path / "Local" / "EasyYtDlp" / "bin"
    assert paths.tools_root() == tmp_path / "Local" / "EasyYtDlp"
    assert paths.install_dir() == tmp_path / "Local" / "Programs" / "Easy yt-dlp"


def test_legacy_dir_is_v1_location() -> None:
    assert paths.legacy_env_dir() == Path.home() / ".ytdlp_env"


def test_ensure_dirs_creates_folders() -> None:
    paths.ensure_dirs()
    assert paths.data_dir().is_dir()
    assert paths.logs_dir().is_dir()
    assert paths.tools_dir().is_dir()
