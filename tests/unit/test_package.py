import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import easy_ytdlp

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


def test_main_module_runs() -> None:
    main = importlib.import_module("easy_ytdlp.__main__").main
    assert main() == 0
