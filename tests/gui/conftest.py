import os

# Must be set before the QApplication exists.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Callable
from typing import ClassVar

import pytest

from easy_ytdlp.core import paths
from easy_ytdlp.core.settings import Settings
from easy_ytdlp.gui.context import AppContext
from easy_ytdlp.gui.controllers.queue_controller import QueueController
from easy_ytdlp.gui.widgets import media_card


class FakeRunner:
    """Never starts a process; tests drive output and exit through the callbacks."""

    instances: ClassVar[list["FakeRunner"]] = []

    def __init__(
        self, argv: list[str], on_line: Callable[[str], None], on_exit: Callable[[int], None]
    ) -> None:
        self.argv = argv
        self.on_line = on_line
        self.on_exit = on_exit
        FakeRunner.instances.append(self)

    def start(self) -> None:
        pass

    def cancel(self) -> None:
        self.on_exit(1)


class NoThumbnails:
    def load(self, url, callback, receiver) -> None:
        pass


@pytest.fixture(autouse=True)
def no_network_thumbnails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media_card, "loader", NoThumbnails)


@pytest.fixture
def ctx(qapp, tmp_path) -> AppContext:
    FakeRunner.instances.clear()
    settings = Settings(download_dir=str(tmp_path / "out"))
    context = AppContext(
        settings, persist=False, queue=QueueController(2, runner_factory=FakeRunner)
    )
    context.theme.apply()
    return context


@pytest.fixture
def fake_ytdlp() -> None:
    """Pretend yt-dlp is installed (the pages check that the file exists)."""
    paths.tools_dir().mkdir(parents=True, exist_ok=True)
    paths.ytdlp_exe().write_bytes(b"")
