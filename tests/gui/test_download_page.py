from easy_ytdlp.core import probe
from easy_ytdlp.core.options import Mode
from easy_ytdlp.core.probe import ProbeError
from easy_ytdlp.core.queue import JobState
from easy_ytdlp.gui.controllers.probe_controller import ProbeController
from easy_ytdlp.gui.pages.download_page import DownloadPage, looks_like_url

URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def make_page(qtbot, ctx, analyze=None) -> DownloadPage:
    controller = ProbeController(analyze) if analyze else None
    page = DownloadPage(ctx, controller)
    qtbot.addWidget(page)
    page.show()
    return page


def test_looks_like_url() -> None:
    assert looks_like_url(" https://x.y/z ")
    assert not looks_like_url("hello world")
    assert not looks_like_url("ftp://x")


def test_controls_update_options_and_command(qtbot, ctx) -> None:
    page = make_page(qtbot, ctx)
    page.url.setText(URL)
    page.mode.button("audio").click()
    page.audio_format.setCurrentIndex(page.audio_format.findData("opus"))
    page.bitrate.setCurrentIndex(page.bitrate.findData("128"))
    assert page.options.mode == Mode.AUDIO
    assert page.options.audio.format == "opus"
    text = page.command_view.toPlainText()
    assert text.startswith("yt-dlp -f ba/b -x --audio-format opus --audio-quality 128K")
    assert text.endswith(f"-- {URL}")
    assert page.mode_stack.currentIndex() == 1

    page.audio_format.setCurrentIndex(page.audio_format.findData("flac"))
    assert not page.bitrate.isEnabled()


def test_enqueue_requires_url_and_tools(qtbot, ctx) -> None:
    page = make_page(qtbot, ctx)
    assert not page.enqueue(navigate=False)
    assert page.error.text() == "Paste a URL first."
    page.url.setText("not a url")
    assert not page.enqueue(navigate=False)
    page.url.setText(URL)
    assert not page.enqueue(navigate=False)
    assert "not installed" in page.error.text()
    assert ctx.queue.jobs() == []


def test_enqueue_adds_job_and_navigates(qtbot, ctx, fake_ytdlp) -> None:
    page = make_page(qtbot, ctx)
    page.url.setText(URL)
    with qtbot.waitSignal(ctx.page_requested) as blocker:
        page.download()
    assert blocker.args == ["queue"]
    [job] = ctx.queue.jobs()
    assert job.title == URL
    assert job.state == JobState.DOWNLOADING
    assert job.argv[-2:] == ["--", URL]
    assert ctx.settings.last_options["mode"] == "video"


def test_validation_error_blocks_enqueue(qtbot, ctx, fake_ytdlp) -> None:
    page = make_page(qtbot, ctx)
    page.url.setText(URL)
    page.options.clip.enabled = True
    page.options.clip.start = "nope"
    assert not page.enqueue(navigate=False)
    assert "clip start" in page.error.text()


def test_analysis_fills_card_and_qualities(qtbot, ctx, fake_ytdlp, fixture_json) -> None:
    info = probe.parse_info(fixture_json("probe_video.json"))
    page = make_page(qtbot, ctx, analyze=lambda url: info)
    page.url.setText(URL)
    with qtbot.waitSignal(page.probe.finished):
        page.analyze()
    assert page.info is info
    assert page.card.title.text() == "Me at the zoo"
    values = [page.quality.itemData(i) for i in range(page.quality.count())]
    assert values == ["best", "240", "144"]
    page.enqueue(navigate=False)
    assert ctx.queue.jobs()[0].title == "Me at the zoo"


def test_analysis_error_is_shown(qtbot, ctx, fake_ytdlp) -> None:
    def fail(url):
        raise ProbeError("Video unavailable", "ERROR: [youtube] x: Video unavailable")

    page = make_page(qtbot, ctx, analyze=fail)
    page.url.setText(URL)
    with qtbot.waitSignal(page.probe.failed):
        page.analyze()
    assert page.card.meta.text() == "Video unavailable"
    assert page.card.details.toPlainText().startswith("ERROR:")


def test_pasting_a_url_analyzes_automatically(qtbot, ctx, fake_ytdlp, fixture_json) -> None:
    info = probe.parse_info(fixture_json("probe_video.json"))
    page = make_page(qtbot, ctx, analyze=lambda url: info)
    with qtbot.waitSignal(page.probe.finished, timeout=5000):
        page.url.setText(URL)


def test_edit_in_command_mode(qtbot, ctx) -> None:
    page = make_page(qtbot, ctx)
    page.url.setText(URL)
    with qtbot.waitSignal(ctx.command_requested) as blocker:
        page.edit_button.click()
    assert blocker.args[0] == page.command_text()
