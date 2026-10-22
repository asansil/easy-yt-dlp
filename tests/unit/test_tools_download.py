import hashlib
import io
import threading
import zipfile
from pathlib import Path

import pytest

from easy_ytdlp.tools import download
from easy_ytdlp.tools.download import ChecksumError, DownloadCancelled, DownloadError

URL = "https://example.com/file.bin"
DATA = b"x" * 200_000
DATA_SHA = hashlib.sha256(DATA).hexdigest()


def test_download_verifies_and_moves(web, tmp_path: Path) -> None:
    web.add(URL, DATA)
    seen: list[tuple[int, int | None]] = []
    target = tmp_path / "out" / "file.bin"
    download.download_file(
        URL, target, expected_sha256=DATA_SHA.upper(), progress=lambda d, t: seen.append((d, t))
    )
    assert target.read_bytes() == DATA
    assert seen[-1] == (len(DATA), len(DATA))
    assert not (tmp_path / "out" / "file.bin.part").exists()


def test_checksum_mismatch_keeps_previous_file(web, tmp_path: Path) -> None:
    web.add(URL, DATA)
    target = tmp_path / "file.bin"
    target.write_bytes(b"old")
    with pytest.raises(ChecksumError):
        download.download_file(URL, target, expected_sha256="0" * 64)
    assert target.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [target]


def test_cancel(web, tmp_path: Path) -> None:
    web.add(URL, DATA)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(DownloadCancelled):
        download.download_file(URL, tmp_path / "f", expected_sha256=DATA_SHA, cancel=cancel)
    assert list(tmp_path.iterdir()) == []


def test_http_only_is_refused(web, tmp_path: Path) -> None:
    with pytest.raises(DownloadError, match="non-HTTPS"):
        download.download_file("http://example.com/x", tmp_path / "f", expected_sha256=None)
    with pytest.raises(DownloadError):
        download.fetch_text("http://example.com/x")
    assert web.requests == []


def test_network_error_becomes_download_error(web, tmp_path: Path) -> None:
    with pytest.raises(DownloadError):
        download.download_file(URL, tmp_path / "f", expected_sha256=None)
    with pytest.raises(DownloadError):
        download.fetch_json(URL)


def test_fetch_json(web) -> None:
    web.add(URL, '{"tag_name": "v1"}')
    assert download.fetch_json(URL) == {"tag_name": "v1"}
    web.add(URL, "nope")
    with pytest.raises(DownloadError):
        download.fetch_json(URL)


SUMS = f"""\
{"a" * 64}  yt-dlp
{DATA_SHA}  yt-dlp.exe
{"b" * 64}  yt-dlp_x86.exe
"""


@pytest.mark.parametrize(
    ("text", "filename", "expected"),
    [
        (SUMS, "yt-dlp.exe", DATA_SHA),
        (SUMS, "yt-dlp", "a" * 64),
        (f"{DATA_SHA} *ffmpeg.zip\n", "ffmpeg.zip", DATA_SHA),
        (f"{DATA_SHA}\n", None, DATA_SHA),
        (
            f"Algorithm : SHA256\nHash      : {DATA_SHA.upper()}\nPath      : C:\\a\\deno.zip\n",
            None,
            DATA_SHA,
        ),
    ],
)
def test_parse_checksum(text: str, filename: str | None, expected: str) -> None:
    assert download.parse_checksum(text, filename) == expected


def test_parse_checksum_missing() -> None:
    with pytest.raises(ChecksumError):
        download.parse_checksum(SUMS, "other.exe")
    with pytest.raises(ChecksumError):
        download.parse_checksum("nothing here")


def make_zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def test_extract_member_by_exact_name(tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    archive.write_bytes(
        make_zip(
            {"ff-9/bin/ffmpeg.exe": b"ffmpeg", "ff-9/bin/ffplay.exe": b"no", "../evil.exe": b"x"}
        )
    )
    target = tmp_path / "bin" / "ffmpeg.exe"
    target.parent.mkdir()
    download.extract_member(archive, r"[^/]+/bin/ffmpeg\.exe", target)
    assert target.read_bytes() == b"ffmpeg"
    assert sorted(p.name for p in target.parent.iterdir()) == ["ffmpeg.exe"]
    assert not (tmp_path / "evil.exe").exists()


def test_extract_member_requires_exactly_one(tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    archive.write_bytes(make_zip({"a/bin/ffmpeg.exe": b"1", "b/bin/ffmpeg.exe": b"2"}))
    with pytest.raises(DownloadError):
        download.extract_member(archive, r"[^/]+/bin/ffmpeg\.exe", tmp_path / "ffmpeg.exe")
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(DownloadError):
        download.extract_member(bad, "x", tmp_path / "x")


def test_sha256_file(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(DATA)
    assert download.sha256_file(path) == DATA_SHA
