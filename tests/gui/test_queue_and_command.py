from PySide6.QtCore import Qt

from easy_ytdlp.core import progress
from easy_ytdlp.core.queue import JobState
from easy_ytdlp.gui.pages.command_page import CommandPage
from easy_ytdlp.gui.pages.queue_page import QueuePage
from easy_ytdlp.gui.pages.settings_page import SettingsPage

from .conftest import FakeRunner


def test_queue_rows_follow_jobs(qtbot, ctx) -> None:
    page = QueuePage(ctx)
    qtbot.addWidget(page)
    assert page.empty.isVisible() is False or not page.rows
    job = ctx.queue.add_command(["yt-dlp", "x"], "First")
    qtbot.waitUntil(lambda: job.id in page.rows)
    row = page.rows[job.id]
    runner = FakeRunner.instances[-1]
    runner.on_line(
        progress.DOWNLOAD_PREFIX
        + '{"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100,'
        ' "speed": 2048, "eta": 5} {"title": "First"}'
    )
    qtbot.waitUntil(lambda: row.progress.value() == 500)
    assert "50 %" in row.status.text()
    assert row.cancel.isVisibleTo(row)

    row.cancel.click()
    qtbot.waitUntil(lambda: ctx.queue.get(job.id).state == JobState.CANCELLED)
    qtbot.waitUntil(lambda: row.retry.isVisibleTo(row))
    row.remove.click()
    assert job.id not in page.rows
    assert ctx.queue.jobs() == []


def test_failed_job_shows_error(qtbot, ctx) -> None:
    page = QueuePage(ctx)
    qtbot.addWidget(page)
    job = ctx.queue.add_command(["yt-dlp", "x"], "Bad")
    runner = FakeRunner.instances[-1]
    runner.on_line("ERROR: Unsupported URL: x")
    runner.on_exit(1)
    qtbot.waitUntil(lambda: page.rows[job.id].error.text() == "Unsupported URL: x")


def test_pause_and_clear(qtbot, ctx) -> None:
    page = QueuePage(ctx)
    qtbot.addWidget(page)
    page.pause_button.click()
    assert ctx.queue.queue.paused
    job = ctx.queue.add_command(["yt-dlp"], "waiting")
    assert ctx.queue.get(job.id).state == JobState.WAITING
    page.pause_button.click()
    assert not ctx.queue.queue.paused
    FakeRunner.instances[-1].on_exit(0)
    qtbot.waitUntil(lambda: ctx.queue.get(job.id).state == JobState.DONE)
    page.clear_button.click()
    assert page.rows == {}


def test_command_page_runs_and_streams_output(qtbot, ctx, fake_ytdlp) -> None:
    page = CommandPage(ctx)
    qtbot.addWidget(page)
    page.args.setText('-x --audio-format mp3 "https://example.com/a b"')
    page.url.setText("")
    page.run()
    [job] = ctx.queue.jobs()
    assert job.argv[-4:] == ["-x", "--audio-format", "mp3", "https://example.com/a b"]
    assert "-P" in job.argv
    FakeRunner.instances[-1].on_line("[download] hello")
    qtbot.waitUntil(lambda: "[download] hello" in page.console.toPlainText())
    assert ctx.settings.command_history[-1].startswith("-x")


def test_command_page_errors(qtbot, ctx, fake_ytdlp) -> None:
    page = CommandPage(ctx)
    qtbot.addWidget(page)
    page.run()
    assert page.error.isVisibleTo(page)
    page.args.setText('-o "unterminated')
    page.run()
    assert "quotes" in page.error.text()
    assert ctx.queue.jobs() == []


def test_command_history_navigation(qtbot, ctx) -> None:
    ctx.settings.command_history = ["-F A", "-x B"]
    page = CommandPage(ctx)
    qtbot.addWidget(page)
    qtbot.keyClick(page.args, Qt.Key.Key_Up)
    assert page.args.text() == "-x B"
    qtbot.keyClick(page.args, Qt.Key.Key_Up)
    assert page.args.text() == "-F A"
    qtbot.keyClick(page.args, Qt.Key.Key_Down)
    qtbot.keyClick(page.args, Qt.Key.Key_Down)
    assert page.args.text() == ""


def test_command_requested_fills_arguments(qtbot, ctx) -> None:
    page = CommandPage(ctx)
    qtbot.addWidget(page)
    ctx.command_requested.emit("yt-dlp -F URL")
    assert page.args.text() == "yt-dlp -F URL"


def test_settings_page_applies_changes(qtbot, ctx) -> None:
    page = SettingsPage(ctx)
    qtbot.addWidget(page)
    page.theme.setCurrentIndex(page.theme.findData("dark"))
    assert ctx.theme.is_dark
    page.concurrency.setCurrentIndex(page.concurrency.findData(4))
    assert ctx.queue.queue.max_concurrent == 4
    page.language.setCurrentIndex(page.language.findData("es"))
    assert ctx.settings.language == "es"
    assert page.language_note.isVisibleTo(page)
    page.folder.set_text("D:\\Videos")
    assert ctx.settings.download_dir == "D:\\Videos"
