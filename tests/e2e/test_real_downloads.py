"""Real downloads with the latest tools. Network-dependent: run with ``pytest -m e2e``.

The tools are installed once per session into a temporary folder through the same code
the app uses, so these tests also cover the tool installers end to end.
"""

import os
from pathlib import Path

import pytest

from easy_ytdlp.core import command_builder, probe
from easy_ytdlp.core.options import DownloadOptions, Mode
from easy_ytdlp.core.probe import MediaKind
from easy_ytdlp.core.queue import DownloadQueue, JobState
from easy_ytdlp.tools import manager

pytestmark = pytest.mark.e2e

# "Big Buck Bunny" (Blender Foundation, CC BY 3.0); clips keep the downloads tiny.
YOUTUBE_URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
ARCHIVE_URL = "https://archive.org/details/BigBuckBunny_124"
# YouTube often asks CI runners to sign in; that is an environment problem, not a bug.
BOT_CHECK = "Sign in to confirm"


@pytest.fixture(scope="session")
def tools_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("tools") / "bin"
    os.environ["EASYYTDLP_TOOLS_DIR"] = str(folder)
    for tool in manager.all_tools(folder):
        tool.install()
        assert tool.installed_version(), tool.name
    return folder


@pytest.fixture
def ytdlp(tools_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # The autouse fixture in tests/conftest.py points the tools folder elsewhere.
    monkeypatch.setenv("EASYYTDLP_TOOLS_DIR", str(tools_dir))
    return tools_dir / "yt-dlp.exe"


def run(options: DownloadOptions, url: str, ytdlp: Path) -> list[str]:
    queue = DownloadQueue(1)
    job = queue.add(command_builder.build(options, [url], ytdlp=ytdlp), url)
    assert queue.wait_idle(600)
    result = queue.get(job.id)
    if result.state != JobState.DONE and BOT_CHECK in "\n".join(result.log):
        pytest.skip("YouTube asked this runner to sign in")
    assert result.state == JobState.DONE, "\n".join(list(result.log)[-30:])
    return result.files


def clip(options: DownloadOptions, out: Path) -> DownloadOptions:
    options.output.folder = str(out)
    options.clip.enabled = True
    options.clip.end = "0:04"
    return options


def test_probe_youtube(ytdlp: Path) -> None:
    try:
        info = probe.analyze(YOUTUBE_URL, ytdlp=ytdlp)
    except probe.ProbeError as exc:
        if BOT_CHECK in exc.details:
            pytest.skip("YouTube asked this runner to sign in")
        raise
    assert info.kind == MediaKind.VIDEO
    assert info.heights


@pytest.mark.parametrize("url", [YOUTUBE_URL, ARCHIVE_URL])
def test_video_clip(ytdlp: Path, tmp_path: Path, url: str) -> None:
    options = clip(DownloadOptions(), tmp_path)
    options.format.quality = "360"
    files = run(options, url, ytdlp)
    assert files and Path(files[-1]).suffix == ".mp4"
    assert Path(files[-1]).stat().st_size > 10_000


def test_audio_clip(ytdlp: Path, tmp_path: Path) -> None:
    options = clip(DownloadOptions(mode=Mode.AUDIO), tmp_path)
    files = run(options, ARCHIVE_URL, ytdlp)
    assert Path(files[-1]).suffix == ".mp3"
