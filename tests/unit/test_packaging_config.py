"""Keep the installer, the smoke test and the app in agreement."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETUP = (ROOT / "packaging" / "inno" / "setup.iss").read_text(encoding="utf-8-sig")
SMOKE = (ROOT / "tests" / "packaging" / "install_smoke.ps1").read_text(encoding="utf-8")


def test_app_id_matches_smoke_test() -> None:
    app_id = re.search(r"^AppId=\{(\{[0-9A-F-]{36}\})", SETUP, re.MULTILINE)
    assert app_id
    assert f'"{app_id.group(1)}_is1"' in SMOKE


def test_tools_dir_matches_paths(monkeypatch) -> None:
    from easy_ytdlp.core import paths

    monkeypatch.delenv("EASYYTDLP_TOOLS_DIR")
    monkeypatch.setenv("LOCALAPPDATA", "L")
    assert '#define ToolsDir "{localappdata}\\EasyYtDlp\\bin"' in SETUP
    assert paths.tools_dir() == Path("L") / "EasyYtDlp" / "bin"


def test_install_dir_matches_paths(monkeypatch) -> None:
    from easy_ytdlp.core import paths

    monkeypatch.setenv("LOCALAPPDATA", "L")
    assert "DefaultDirName={localappdata}\\Programs\\{#AppName}" in SETUP
    assert '#define AppName "Easy yt-dlp"' in SETUP
    assert paths.install_dir() == Path("L") / "Programs" / "Easy yt-dlp"


def test_setup_name_matches_updater_pattern() -> None:
    assert "OutputBaseFilename=EasyYtDlp-Setup-{#AppVersion}" in SETUP
