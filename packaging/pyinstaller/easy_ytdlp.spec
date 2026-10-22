# PyInstaller spec for Easy yt-dlp (onedir, windowed). Build with:
#   uv run pyinstaller packaging/pyinstaller/easy_ytdlp.spec --noconfirm
import re
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH).resolve().parents[1]  # noqa: F821 (defined by PyInstaller)
SRC = ROOT / "src" / "easy_ytdlp"

VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
    "version"
]
# Windows needs four integers: "2.0.0.dev0" -> (2, 0, 0, 0).
_numbers = [int(n) for n in re.findall(r"\d+", VERSION.split(".dev")[0].split("b")[0])][:3]
NUMERIC = tuple(_numbers + [0] * (4 - len(_numbers)))

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMERIC, prodvers=NUMERIC),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "Easy yt-dlp"),
                        StringStruct("FileDescription", "Easy yt-dlp"),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("InternalName", "EasyYtDlp"),
                        StringStruct("LegalCopyright", "MIT License"),
                        StringStruct("OriginalFilename", "EasyYtDlp.exe"),
                        StringStruct("ProductName", "Easy yt-dlp"),
                        StringStruct("ProductVersion", VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

datas = copy_metadata("easy-ytdlp")
datas.append((str(SRC / "resources"), "easy_ytdlp/resources"))
# Only the compiled translations; packaging/build.ps1 builds them from the .ts sources.
datas += [(str(qm), "easy_ytdlp/i18n") for qm in (SRC / "i18n").glob("*.qm")]

a = Analysis(  # noqa: F821
    [str(Path(SPECPATH) / "launcher.py")],  # noqa: F821
    pathex=[str(ROOT / "src")],
    datas=datas,
    excludes=["tkinter", "unittest", "pydoc", "pytest"],
    noarchive=False,
)
# Qt pieces a Qt Widgets app does not use (about 40 MB): software OpenGL, Qt Quick/QML
# (pulled in by the virtual keyboard plugin) and PDF image support.
_UNUSED = re.compile(
    r"opengl32sw\.dll|Qt6(Quick|Qml|VirtualKeyboard|Pdf|OpenGL)\w*\.dll"
    r"|qtvirtualkeyboardplugin\.dll|qpdf\.dll",
    re.IGNORECASE,
)
# Keep only the Qt translations for the languages the app offers.
_TRANSLATION = re.compile(r"translations[\\/](?!qtbase_(en|es)\.qm$)", re.IGNORECASE)


def _keep(entry) -> bool:
    name = entry[0]
    return not _UNUSED.search(Path(name).name) and not _TRANSLATION.search(name)


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EasyYtDlp",
    console=False,
    icon=str(ROOT / "assets" / "yt_dlp_interface.ico"),
    version=version_info,
    upx=False,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="EasyYtDlp",
    upx=False,
)
