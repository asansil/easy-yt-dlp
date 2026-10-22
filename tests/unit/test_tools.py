import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from easy_ytdlp.core import paths
from easy_ytdlp.tools import base, deno, ffmpeg, manager, ytdlp
from easy_ytdlp.tools.base import ToolStatus
from easy_ytdlp.tools.download import ChecksumError

GH = "https://github.com"
API = "https://api.github.com/repos"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buffer.getvalue()


@pytest.mark.parametrize("channel", ["stable", "nightly"])
def test_ytdlp_install(web, channel: str) -> None:
    repo = ytdlp.CHANNELS[channel]
    exe = b"MZ yt-dlp"
    web.add(f"{API}/{repo}/releases/latest", '{"tag_name": "2026.10.21"}')
    base_url = f"{GH}/{repo}/releases/download/2026.10.21"
    web.add(f"{base_url}/SHA2-256SUMS", f"{'0' * 64}  yt-dlp\n{sha(exe)}  yt-dlp.exe\n")
    web.add(f"{base_url}/yt-dlp.exe", exe)
    tool = ytdlp.YtDlp()
    assert tool.latest_version(channel) == "2026.10.21"
    assert tool.install(channel) == "2026.10.21"
    assert paths.ytdlp_exe().read_bytes() == exe
    assert tool.is_installed()


def test_ytdlp_tampered_binary_is_rejected(web) -> None:
    repo = ytdlp.CHANNELS["stable"]
    web.add(f"{API}/{repo}/releases/latest", '{"tag_name": "1"}')
    web.add(f"{GH}/{repo}/releases/download/1/SHA2-256SUMS", f"{'0' * 64}  yt-dlp.exe\n")
    web.add(f"{GH}/{repo}/releases/download/1/yt-dlp.exe", b"evil")
    with pytest.raises(ChecksumError):
        ytdlp.YtDlp().install()
    assert not paths.ytdlp_exe().exists()


def test_ffmpeg_install(web) -> None:
    archive = zip_bytes(
        {
            "ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe": b"ffmpeg",
            "ffmpeg-9.0.2-essentials_build/bin/ffprobe.exe": b"ffprobe",
            "ffmpeg-9.0.2-essentials_build/bin/ffplay.exe": b"ffplay",
        }
    )
    web.add(ffmpeg.VERSION_URL, "9.0.2\n")
    web.add(ffmpeg.SHA_URL, sha(archive))
    web.add(ffmpeg.ZIP_URL, archive)
    tool = ffmpeg.Ffmpeg()
    assert tool.install() == "9.0.2"
    assert paths.ffmpeg_exe().read_bytes() == b"ffmpeg"
    assert paths.ffprobe_exe().read_bytes() == b"ffprobe"
    assert sorted(p.name for p in paths.tools_dir().iterdir()) == ["ffmpeg.exe", "ffprobe.exe"]
    # The temp download folder is cleaned up.
    assert [p.name for p in paths.tools_root().iterdir()] == ["bin"]


def test_deno_install(web) -> None:
    archive = zip_bytes({"deno.exe": b"deno"})
    web.add(f"{API}/denoland/deno/releases/latest", '{"tag_name": "v2.9.8"}')
    base_url = f"{GH}/denoland/deno/releases/download/v2.9.8"
    web.add(
        f"{base_url}/{deno.ASSET}.sha256sum",
        f"Algorithm : SHA256\r\nHash      : {sha(archive).upper()}\r\nPath      : C:\\a\\x.zip\r\n",
    )
    web.add(f"{base_url}/{deno.ASSET}", archive)
    tool = deno.Deno()
    assert tool.latest_version() == "2.9.8"
    assert tool.install() == "2.9.8"
    assert paths.deno_exe().read_bytes() == b"deno"


def test_version_parsers() -> None:
    assert (
        ffmpeg.parse_version("ffmpeg version 9.0.2-essentials_build-www.gyan.dev Copyright")
        == "9.0.2"
    )
    assert ffmpeg.parse_version(None) is None
    assert deno.parse_version("deno 2.9.8 (stable, release, x86_64-pc-windows-msvc)") == "2.9.8"
    assert base.version_key("2026.10.21.232929") > base.version_key("2026.10.21")


def test_installed_version_of_missing_tool() -> None:
    tool = ytdlp.YtDlp()
    assert tool.installed_version() is None
    assert tool.status(check_latest=False) == ToolStatus("yt-dlp", None, None)


def test_status_flags() -> None:
    assert ToolStatus("x", None, "1").missing
    assert ToolStatus("x", "1", "2").update_available
    assert not ToolStatus("x", "2", "2").update_available
    assert not ToolStatus("x", "2", None).update_available


def test_run_version_uses_real_process(tmp_path: Path) -> None:
    import sys

    assert base.run_version([sys.executable, "-c", "print('1.2.3')"]) == "1.2.3"
    assert base.run_version([sys.executable, "-c", "import sys; sys.exit(1)"]) is None
    assert base.run_version([str(tmp_path / "missing.exe")]) is None


def test_manager_lists_missing_tools() -> None:
    assert [t.name for t in manager.all_tools()] == ["yt-dlp", "FFmpeg", "deno"]
    paths.tools_dir().mkdir(parents=True)
    paths.ytdlp_exe().write_bytes(b"x")
    paths.ffmpeg_exe().write_bytes(b"x")
    # FFmpeg needs ffprobe too.
    assert [t.name for t in manager.missing_tools()] == ["FFmpeg", "deno"]
