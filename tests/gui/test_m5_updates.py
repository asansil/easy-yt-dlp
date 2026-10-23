import threading
import time
from pathlib import Path

import pytest

from easy_ytdlp.core.settings import Settings
from easy_ytdlp.gui.controllers.tools_controller import ToolsController
from easy_ytdlp.gui.controllers.update_controller import ToolAutoUpdater, UpdateController
from easy_ytdlp.gui.dialogs import FirstRunDialog, UpdateDialog
from easy_ytdlp.gui.pages.settings_page import SettingsPage
from easy_ytdlp.tools import migration, path_env
from easy_ytdlp.tools.base import Tool
from easy_ytdlp.tools.download import DownloadError
from easy_ytdlp.updater.app_update import Release
from easy_ytdlp.updater.versions import Version


class FakeTool(Tool):
    """A tool whose 'binary' is a text file holding its version."""

    latest = "2.0"
    fail = False

    def __init__(self, name: str, folder: Path) -> None:
        super().__init__(folder)
        self.name = name
        self.executables = (f"{name}.exe",)

    def installed_version(self) -> str | None:
        path = self.path()
        return path.read_text() if path.exists() else None

    def latest_version(self, channel: str = "stable") -> str:
        return self.latest

    def install(self, channel="stable", *, progress=None, cancel: threading.Event | None = None):
        if self.fail:
            raise DownloadError("network is down")
        if progress:
            progress(50, 100)
            progress(100, 100)
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.path().write_text(self.latest)
        return self.latest


@pytest.fixture
def fake_tools(tmp_path: Path):
    tools = [FakeTool(name, tmp_path / "bin") for name in ("yt-dlp", "FFmpeg", "deno")]
    return tools, ToolsController(lambda: tools)


def test_first_run_installs_everything(qtbot, fake_tools, monkeypatch) -> None:
    tools, controller = fake_tools
    removed = []
    monkeypatch.setattr(migration, "remove_legacy", lambda: removed.append(True) or [])
    dialog = FirstRunDialog(controller, legacy=True)
    qtbot.addWidget(dialog)
    assert dialog.names == ["yt-dlp", "FFmpeg", "deno"]
    assert dialog.legacy.isVisibleTo(dialog)
    with qtbot.waitSignal(controller.finished, timeout=10000):
        dialog.install()
    assert all(tool.is_installed() for tool in tools)
    assert removed == [True]
    assert dialog.close_button.isVisibleTo(dialog)
    assert dialog.rows["deno"][0].value() == 1000


def test_first_run_offline_offers_retry(qtbot, fake_tools) -> None:
    tools, controller = fake_tools
    tools[1].fail = True
    dialog = FirstRunDialog(controller, legacy=False)
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(controller.finished, timeout=10000):
        dialog.install()
    assert dialog.error.isVisibleTo(dialog)
    assert "network is down" in dialog.error.text()
    assert dialog.install_button.isEnabled()
    assert tools[0].is_installed() and not tools[1].is_installed()

    tools[1].fail = False
    with qtbot.waitSignal(controller.finished, timeout=10000):
        dialog.install()
    assert dialog.close_button.isVisibleTo(dialog)


def test_first_run_with_everything_installed(qtbot, fake_tools) -> None:
    tools, controller = fake_tools
    for tool in tools:
        tool.install()
    dialog = FirstRunDialog(controller, legacy=False)
    qtbot.addWidget(dialog)
    assert dialog.close_button.isVisibleTo(dialog)
    assert not dialog.install_button.isVisibleTo(dialog)


def make_release(tag: str = "v2.1.0") -> Release:
    version = Version(tag)
    return Release(
        version=version,
        tag=tag,
        name=tag,
        notes="<b>Notes</b> stay plain",
        url="",
        setup_name=f"EasyYtDlp-Setup-{version.pep440()}.exe",
        setup_url="https://x/setup.exe",
        checksum_url="https://x/setup.exe.sha256",
    )


def test_update_controller_respects_settings(qtbot) -> None:
    settings = Settings()
    calls = []

    def find(current, include_prereleases, skipped):
        calls.append((current, include_prereleases, skipped))
        return make_release()

    updates = UpdateController(settings, find=find, current="2.0.0")
    settings.check_app_updates = False
    assert not updates.check()
    settings.check_app_updates = True
    settings.beta_updates = True
    settings.skipped_app_version = "2.1.0"
    with qtbot.waitSignal(updates.available):
        assert updates.check()
    assert calls == [("2.0.0", True, "2.1.0")]
    assert settings.last_app_check > time.time() - 60
    # Ran less than a day ago: automatic checks wait; manual ones ignore "skipped".
    assert not updates.check()
    with qtbot.waitSignal(updates.available):
        updates.check(manual=True)
    assert calls[-1][2] == ""


def test_manual_check_reports_up_to_date_and_errors(qtbot) -> None:
    updates = UpdateController(Settings(), find=lambda *a, **k: None)
    with qtbot.waitSignal(updates.up_to_date):
        updates.check(manual=True)

    def broken(*args, **kwargs):
        raise DownloadError("offline")

    failing = UpdateController(Settings(), find=broken)
    with qtbot.waitSignal(failing.failed) as blocker:
        failing.check(manual=True)
    assert blocker.args == ["offline"]


def test_update_dialog_install_and_skip(qtbot, tmp_path: Path) -> None:
    settings = Settings()
    setup = tmp_path / "EasyYtDlp-Setup-2.1.0.exe"

    def download(release, folder, progress=None, cancel=None):
        progress(10, 10)
        return setup

    updates = UpdateController(settings, download=download, current="2.0.0")
    release = make_release()
    dialog = UpdateDialog(updates, release)
    qtbot.addWidget(dialog)
    assert dialog.notes.toPlainText() == "<b>Notes</b> stay plain"
    launched = []
    dialog.launch = launched.append
    with qtbot.waitSignal(updates.ready):
        dialog.install_button.click()
    assert launched == [setup]

    other = UpdateDialog(updates, release)
    qtbot.addWidget(other)
    other.skip_button.click()
    assert settings.skipped_app_version == "2.1.0"


def test_update_dialog_shows_verification_errors(qtbot) -> None:
    def download(release, folder, progress=None, cancel=None):
        raise DownloadError("Checksum mismatch")

    updates = UpdateController(Settings(), download=download)
    dialog = UpdateDialog(updates, make_release())
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(updates.download_failed):
        dialog.install_button.click()
    assert "Checksum mismatch" in dialog.error.text()
    assert dialog.install_button.isEnabled()


def test_tool_auto_updater(qtbot, fake_tools) -> None:
    tools, controller = fake_tools
    for tool in tools:
        tool.install()
    tools[0].latest = "3.0"
    settings = Settings()
    idle = {"value": True}
    updater = ToolAutoUpdater(settings, controller, is_idle=lambda: idle["value"])
    with qtbot.waitSignal(updater.started) as blocker:
        assert updater.run()
    assert blocker.args == [["yt-dlp"]]
    qtbot.waitUntil(lambda: tools[0].installed_version() == "3.0")
    qtbot.waitUntil(lambda: not controller.busy)
    # Checked recently: nothing until tomorrow.
    assert not updater.run()
    settings.last_tools_check = 0
    settings.auto_update_tools = False
    assert not updater.run()


def test_tool_auto_updater_waits_for_idle_queue(qtbot, fake_tools) -> None:
    tools, controller = fake_tools
    for tool in tools:
        tool.install()
    tools[2].latest = "9"
    updater = ToolAutoUpdater(Settings(), controller, is_idle=lambda: False)
    with qtbot.waitSignal(controller.statuses):
        updater.run()
    qtbot.wait(50)
    assert tools[2].installed_version() == "2.0"


def test_settings_tools_section(qtbot, ctx, fake_tools, monkeypatch) -> None:
    tools, controller = fake_tools
    tools[0].install()
    ctx.tools = controller
    state = {"in_path": False}
    monkeypatch.setattr(path_env, "is_in_user_path", lambda entry: state["in_path"])
    monkeypatch.setattr(path_env, "add_to_user_path", lambda entry: state.update(in_path=True))
    monkeypatch.setattr(
        path_env, "remove_from_user_path", lambda entry: state.update(in_path=False)
    )
    page = SettingsPage(ctx)
    qtbot.addWidget(page)
    qtbot.waitUntil(lambda: page.tool_rows["yt-dlp"][0].text() == "2.0")
    assert page.tool_rows["FFmpeg"][0].text() == "Not installed"

    with qtbot.waitSignal(controller.statuses):
        page.check_tools(latest=True)
    assert page.update_tools_button.isEnabled()
    assert "FFmpeg" in page.tools_status.text()
    with qtbot.waitSignal(controller.finished, timeout=10000):
        page.update_tools()
    assert all(tool.is_installed() for tool in tools)

    assert page.path_button.text() == "Add to PATH"
    page.toggle_path()
    assert state["in_path"] and page.path_button.text() == "Remove from PATH"

    page.channel.setCurrentIndex(page.channel.findData("nightly"))
    assert ctx.settings.ytdlp_channel == "nightly"
    page.beta.setChecked(True)
    assert ctx.settings.beta_updates


def test_settings_clear_history(qtbot, ctx) -> None:
    from easy_ytdlp.core.queue import Job, JobState

    ctx.history.add_job(Job(id=1, argv=["y"], title="t", state=JobState.DONE, finished_at=1))
    page = SettingsPage(ctx)
    qtbot.addWidget(page)
    page.confirm_clear_history = lambda: True
    page.clear_history()
    assert ctx.history.count() == 0


def test_main_window_update_badge(qtbot, ctx) -> None:
    from easy_ytdlp.gui.main_window import MainWindow

    window = MainWindow(ctx)
    window.confirm_quit = lambda pending: True
    qtbot.addWidget(window)
    assert not window.update_button.isVisibleTo(window)
    ctx.updates.release = make_release("v2.0.0-beta.2")
    ctx.updates.available.emit(ctx.updates.release)
    assert window.update_button.isVisibleTo(window)
    assert "v2.0.0-beta.2" in window.update_button.text()
