import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import easy_ytdlp
from easy_ytdlp.core import paths

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
QT_FREE_PACKAGES = ["easy_ytdlp.core", "easy_ytdlp.tools", "easy_ytdlp.updater"]


def test_version_matches_pyproject() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    assert easy_ytdlp.__version__ == project["version"]


@pytest.mark.parametrize("package", QT_FREE_PACKAGES)
def test_package_does_not_import_pyside6(package: str) -> None:
    # Run in a fresh interpreter so modules loaded by other tests do not leak in.
    code = f"import sys, {package}; sys.exit('PySide6' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], check=False)
    assert result.returncode == 0, f"{package} imports PySide6"


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    main = importlib.import_module("easy_ytdlp.app").main
    assert main(["--version"]) == 0
    assert easy_ytdlp.__version__ in capsys.readouterr().out


def test_self_test_flag() -> None:
    # A fresh interpreter, like the frozen app, with the data folder from conftest.
    result = subprocess.run(
        [sys.executable, "-m", "easy_ytdlp", "--self-test"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "self-test: OK" in result.stdout
    assert paths.logs_dir().is_dir()
