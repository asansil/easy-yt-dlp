import hashlib
import json
from pathlib import Path

import pytest

from easy_ytdlp.tools.download import ChecksumError, DownloadError
from easy_ytdlp.updater import app_update
from easy_ytdlp.updater.versions import Version, parse

API = "https://api.example.com/releases"


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("2.0.0.dev0", "2.0.0a1"),
        ("2.0.0a1", "2.0.0b1"),
        ("v2.0.0-beta.1", "v2.0.0-beta.2"),
        ("2.0.0b2", "2.0.0rc1"),
        ("v2.0.0-rc.1", "2.0.0"),
        ("2.0.0", "2.0.1"),
        ("1.0.1", "2.0.0b1"),
        ("2.0", "2.0.1"),
    ],
)
def test_version_order(a: str, b: str) -> None:
    assert Version(a) < Version(b)


def test_version_spellings() -> None:
    assert Version("v2.0.0-beta.1") == Version("2.0.0b1")
    assert Version("v2.0.0-beta.1").pep440() == "2.0.0b1"
    assert Version("2.0.0b1").tag() == "v2.0.0-beta.1"
    assert Version("2.0.0rc2").tag() == "v2.0.0-rc.2"
    assert Version("2.0.0.dev0").pep440() == "2.0.0.dev0"
    assert Version("v2.1").tag() == "v2.1.0"
    assert Version("2.0.0").is_prerelease is False
    assert parse("latest") is None


def release(tag: str, *, prerelease: bool = False, draft: bool = False, assets=None) -> dict:
    parsed = parse(tag)
    version = parsed.pep440() if parsed else tag
    setup = f"EasyYtDlp-Setup-{version}.exe"
    names = assets if assets is not None else [setup, f"{setup}.sha256"]
    return {
        "tag_name": tag,
        "name": f"Easy yt-dlp {tag}",
        "body": "Notes for " + tag,
        "html_url": f"https://github.com/x/releases/tag/{tag}",
        "draft": draft,
        "prerelease": prerelease,
        "assets": [
            {"name": n, "browser_download_url": f"https://github.com/dl/{tag}/{n}"} for n in names
        ],
    }


def serve(web, releases: list[dict]) -> None:
    web.add(API, json.dumps(releases))


def test_finds_newest_stable(web) -> None:
    serve(web, [release("v2.1.0"), release("v2.2.0-beta.1", prerelease=True), release("v2.0.0")])
    update = app_update.find_update("2.0.0", url=API)
    assert update.tag == "v2.1.0"
    assert update.setup_name == "EasyYtDlp-Setup-2.1.0.exe"
    assert update.notes == "Notes for v2.1.0"
    beta = app_update.find_update("2.0.0", include_prereleases=True, url=API)
    assert beta.tag == "v2.2.0-beta.1"
    assert beta.setup_name == "EasyYtDlp-Setup-2.2.0b1.exe"


def test_no_downgrade_or_same_version(web) -> None:
    serve(web, [release("v2.0.0"), release("v1.0.1")])
    assert app_update.find_update("2.0.0", url=API) is None
    assert app_update.find_update("2.1.0b1", url=API) is None


def test_skipped_version_and_unusable_releases(web) -> None:
    serve(
        web,
        [
            release("v3.0.0", draft=True),
            release("v2.5.0", assets=["other.zip"]),
            release("nightly"),
            release("v2.1.0"),
        ],
    )
    assert app_update.find_update("2.0.0", url=API).tag == "v2.1.0"
    assert app_update.find_update("2.0.0", skipped="2.1.0", url=API) is None


def test_tag_spelling_assets_are_accepted() -> None:
    data = release(
        "v2.0.0-beta.1",
        assets=["EasyYtDlp-Setup-2.0.0-beta.1.exe", "EasyYtDlp-Setup-2.0.0-beta.1.exe.sha256"],
    )
    assert app_update.parse_release(data).setup_name == "EasyYtDlp-Setup-2.0.0-beta.1.exe"


def test_update_url_override(web, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(app_update.UPDATE_URL_ENV, API)
    serve(web, [release("v9.0.0")])
    assert app_update.find_update("2.0.0").tag == "v9.0.0"


def test_bad_answers(web) -> None:
    web.add(API, '{"message": "rate limited"}')
    with pytest.raises(DownloadError):
        app_update.find_update("2.0.0", url=API)


def test_check_due() -> None:
    assert app_update.check_due(0, now=100_000)
    assert not app_update.check_due(100_000 - 60, now=100_000)


def test_download_setup_verifies_hash(web, tmp_path: Path) -> None:
    data = release("v2.1.0")
    update = app_update.parse_release(data)
    payload = b"MZ setup"
    web.add(update.setup_url, payload)
    web.add(update.checksum_url, f"{hashlib.sha256(payload).hexdigest()}  {update.setup_name}\n")
    path = app_update.download_setup(update, tmp_path)
    assert path.read_bytes() == payload

    web.add(update.checksum_url, f"{'0' * 64}  {update.setup_name}\n")
    path.unlink()
    with pytest.raises(ChecksumError):
        app_update.download_setup(update, tmp_path)
    assert not path.exists()


def test_launch_installer_arguments(tmp_path: Path) -> None:
    calls = []
    app_update.launch_installer(tmp_path / "setup.exe", popen=lambda argv, **kw: calls.append(argv))
    assert calls[0][1:] == app_update.INSTALLER_ARGS
    assert "/RELAUNCH=1" in calls[0]
