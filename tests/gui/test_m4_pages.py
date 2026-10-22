from PySide6.QtCore import Qt

from easy_ytdlp.core import command_builder, probe
from easy_ytdlp.core.options import DownloadOptions, Mode
from easy_ytdlp.core.queue import Job, JobState
from easy_ytdlp.gui.controllers.probe_controller import ProbeController
from easy_ytdlp.gui.pages.download_page import DownloadPage
from easy_ytdlp.gui.pages.history_page import HistoryPage
from easy_ytdlp.gui.pages.presets_page import PresetsPage

PLAYLIST = "https://www.youtube.com/playlist?list=PLwclSMR0kf72WS2ZAAAdhpY2lFu4NIcPS"
VIDEO = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def page_with(qtbot, ctx, info=None) -> DownloadPage:
    page = DownloadPage(ctx, ProbeController(lambda url: info) if info else None)
    qtbot.addWidget(page)
    page.show()
    return page


def analyzed(qtbot, ctx, fixture_json, name: str, url: str) -> DownloadPage:
    info = probe.parse_info(fixture_json(name))
    page = page_with(qtbot, ctx, info)
    page.url.setText(url)
    with qtbot.waitSignal(page.probe.finished):
        page.analyze()
    return page


def test_playlist_selection(qtbot, ctx, fake_ytdlp, fixture_json) -> None:
    page = analyzed(qtbot, ctx, fixture_json, "probe_playlist.json", PLAYLIST)
    picker = page.picker
    assert picker.isVisibleTo(page)
    assert picker.list.count() == 5
    assert page.playlist_items() == ""
    assert picker.note.isVisibleTo(picker)  # 5 of 37 listed

    picker.ranges.setText("1-2, 5")
    picker.apply_ranges.click()
    assert page.playlist_items() == "1-2,5"
    assert "-I 1-2,5" in page.command_view.toPlainText()

    picker.ranges.setText("x")
    picker.apply_ranges.click()
    assert picker.range_error.isVisibleTo(picker)

    picker.search.setText("bedtime")
    assert sum(not picker.list.item(i).isHidden() for i in range(5)) == 1
    picker.none_button.click()  # only the visible item is unchecked
    assert page.playlist_items() == "2,5"
    picker.search.clear()
    picker.none_button.click()
    assert not page.enqueue(navigate=False)
    assert "at least one item" in page.error.text()
    picker.all_button.click()
    assert page.enqueue(navigate=False)
    assert "-I" not in ctx.queue.jobs()[0].argv


def test_subtitles_mode_and_sections(qtbot, ctx, fake_ytdlp, fixture_json) -> None:
    page = analyzed(qtbot, ctx, fixture_json, "probe_video.json", VIDEO)
    assert "de, en" in page.subtitles.available.text()
    page.mode.button("subtitles").click()
    assert page.options.mode == Mode.SUBTITLES
    assert page.subtitles_box.is_expanded()
    assert not page.subtitles.enabled.isVisibleTo(page.subtitles)
    page.subtitles.languages.setText("es, en")
    page.subtitles.auto.setChecked(True)
    text = page.command_view.toPlainText()
    assert "--skip-download" in text
    assert "--write-auto-subs --sub-langs es,en" in text
    assert not page.clip_box.isEnabled()


def test_clip_output_and_advanced(qtbot, ctx, fake_ytdlp, fixture_json) -> None:
    page = analyzed(qtbot, ctx, fixture_json, "probe_video.json", VIDEO)
    page.clip.enabled.setChecked(True)
    page.clip.start.setText("0:05")
    page.clip.end.setText("0:10")
    page.clip.keyframes.setChecked(True)
    page.output.organize.setCurrentIndex(page.output.organize.findData("uploader"))
    page.output.template.setText("%(title)s.%(ext)s")
    adv = page.advanced
    adv.cookies.setCurrentIndex(adv.cookies.findData("firefox"))
    adv.sponsorblock.setCurrentIndex(adv.sponsorblock.findData("remove"))
    adv.categories["intro"].setChecked(True)
    adv.rate.setText("2M")
    adv.archive.setChecked(True)
    adv.extra.setText("--no-mtime")
    text = page.command_view.toPlainText()
    for part in (
        "--download-sections *5-10 --force-keyframes-at-cuts",
        "-o %(uploader,channel|Unknown)s/%(title)s.%(ext)s",
        "--cookies-from-browser firefox",
        "--sponsorblock-remove sponsor,intro",
        "-r 2M",
        "--download-archive",
        "--no-mtime --",
    ):
        assert part in text, part
    assert page.output.preview.text().endswith("jawed\\Me at the zoo.mp4")

    page.clip.end.setText("0:01")
    assert not page.enqueue(navigate=False)
    assert "after its start" in page.error.text()

    page.output.template.setText("../%(title)s")
    assert page.output.warning.isVisibleTo(page.output)


def test_options_round_trip_through_controls(qtbot, ctx) -> None:
    options = DownloadOptions(mode=Mode.AUDIO)
    options.audio.format = "opus"
    options.subtitles.enabled = True
    options.subtitles.languages = ["fr"]
    options.clip.enabled = True
    options.clip.end = "30"
    options.advanced.embed_thumbnail = True
    options.output.folder = "D:\\Music"
    page = page_with(qtbot, ctx)
    page.set_options(options)
    page._read_controls()
    assert page.options == options


def test_save_and_apply_preset(qtbot, ctx) -> None:
    page = page_with(qtbot, ctx)
    page.mode.button("audio").click()
    page.audio_format.setCurrentIndex(page.audio_format.findData("flac"))
    page.ask_preset_name = lambda suggestion: "Lossless"
    assert page.save_preset()
    preset = ctx.presets.get("Lossless")
    assert preset.options.audio.format == "flac"
    assert preset.options.output.folder == ""
    assert page.preset.findData("Lossless") >= 0

    page.ask_preset_name = lambda suggestion: "Subtitles only"
    assert not page.save_preset()

    folder = page.options.output.folder
    page._apply_preset(page.preset.findData("Subtitles only"))
    assert page.options.mode == Mode.SUBTITLES
    assert page.options.output.folder == folder
    assert page.preset.currentIndex() == 0


def test_presets_page(qtbot, ctx) -> None:
    page = PresetsPage(ctx)
    qtbot.addWidget(page)
    builtin_count = page.list.count()
    page.list.setCurrentRow(0)
    assert not page.rename_button.isEnabled()
    page.ask_name = lambda title, suggestion: "Mine"
    page.duplicate()
    assert page.list.count() == builtin_count + 1
    page.list.setCurrentRow(builtin_count)
    assert page.rename_button.isEnabled()
    page.toggle_default()
    assert ctx.settings.default_preset == "Mine"
    page.ask_name = lambda title, suggestion: "Ours"
    page.rename()
    assert ctx.settings.default_preset == "Ours"
    with qtbot.waitSignal(ctx.options_requested):
        page.apply()
    page.list.setCurrentRow(builtin_count)
    page.confirm_delete = lambda name: True
    page.delete()
    assert ctx.presets.get("Ours") is None
    assert ctx.settings.default_preset == ""


def test_default_preset_loads_at_start(qtbot, ctx) -> None:
    ctx.settings.default_preset = "Music MP3 320 kbit/s"
    page = page_with(qtbot, ctx)
    assert page.options.mode == Mode.AUDIO
    assert page.options.audio.bitrate == "320"


def finished_job(title: str, state=JobState.DONE, options=None, argv=None) -> Job:
    return Job(
        id=1,
        argv=argv or ["yt-dlp", "--", "u"],
        title=title,
        url=f"https://example.com/{title}",
        options=options,
        state=state,
        finished_at=1.0,
    )


def test_finished_jobs_reach_the_history(qtbot, ctx) -> None:
    page = HistoryPage(ctx)
    qtbot.addWidget(page)
    job = ctx.queue.add_command(["yt-dlp", "-x"], "From queue")
    from .conftest import FakeRunner

    FakeRunner.instances[-1].on_exit(0)
    qtbot.waitUntil(lambda: page.tree.topLevelItemCount() == 1)
    assert page.tree.topLevelItem(0).text(0) == "From queue"
    assert ctx.history.search()[0].state == "done"
    assert job.id


def test_history_page_actions(qtbot, ctx, fake_ytdlp) -> None:
    ctx.history.add_job(finished_job("video", options=DownloadOptions().to_dict()))
    ctx.history.add_job(
        finished_job("secret", argv=command_builder.parse_manual("--password x URL"))
    )
    ctx.history.add_job(finished_job("broken", state=JobState.FAILED))
    page = HistoryPage(ctx)
    qtbot.addWidget(page)
    assert page.tree.topLevelItemCount() == 3

    page.state.setCurrentIndex(page.state.findData("failed"))
    assert page.tree.topLevelItemCount() == 1
    page.state.setCurrentIndex(0)
    page.search.setText("vid")
    page.refresh()
    assert page.tree.topLevelItemCount() == 1
    page.tree.setCurrentItem(page.tree.topLevelItem(0))
    assert page.again_button.isEnabled() and page.load_button.isEnabled()
    page.download_again()
    assert ctx.queue.jobs()[-1].title == "video"
    with qtbot.waitSignal(ctx.options_requested):
        page.load_options()

    page.search.setText("secret")
    page.refresh()
    page.tree.setCurrentItem(page.tree.topLevelItem(0))
    assert not page.again_button.isEnabled()
    assert "********" in page.detail.text()

    page.remove()
    page.search.clear()
    page.refresh()
    assert page.tree.topLevelItemCount() == 2
    page.confirm_clear = lambda: True
    page.clear()
    assert page.tree.topLevelItemCount() == 0


def test_sidebar_has_all_pages(qtbot, ctx) -> None:
    from easy_ytdlp.gui.main_window import MainWindow

    window = MainWindow(ctx)
    window.confirm_quit = lambda pending: True
    qtbot.addWidget(window)
    assert list(window.pages) == ["download", "queue", "history", "presets", "command", "settings"]
    ctx.options_requested.emit(DownloadOptions(mode=Mode.AUDIO))
    assert window.download_page.options.mode == Mode.AUDIO
    assert window.nav_buttons["history"].toolTip().endswith("(Ctrl+3)")
    assert window.download_page.url.focusPolicy() != Qt.FocusPolicy.NoFocus
