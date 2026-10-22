"""Translation helper.

uv run python scripts/i18n.py update    # extract strings into src/easy_ytdlp/i18n/*.ts
uv run python scripts/i18n.py compile   # build the .qm files the app loads
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "easy_ytdlp"
I18N = PACKAGE / "i18n"
LANGUAGES = ["es"]


def _tool(name: str) -> str:
    exe = Path(sys.executable).parent / f"pyside6-{name}.exe"
    return str(exe) if exe.exists() else f"pyside6-{name}"


def update() -> int:
    I18N.mkdir(exist_ok=True)
    sources = sorted(str(p) for p in (PACKAGE / "gui").rglob("*.py"))
    for lang in LANGUAGES:
        ts = I18N / f"easy_ytdlp_{lang}.ts"
        cmd = [_tool("lupdate"), "-no-obsolete", "-locations", "none", *sources, "-ts", str(ts)]
        if subprocess.run(cmd, check=False).returncode != 0:
            return 1
    return 0


def compile_all() -> int:
    for ts in sorted(I18N.glob("*.ts")):
        cmd = [_tool("lrelease"), str(ts), "-qm", str(ts.with_suffix(".qm"))]
        if subprocess.run(cmd, check=False).returncode != 0:
            return 1
    return 0


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "update":
        sys.exit(update())
    if action == "compile":
        sys.exit(compile_all())
    print(__doc__)
    sys.exit(2)
