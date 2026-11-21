import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from easy_ytdlp.core import probe
from easy_ytdlp.core.options import DownloadOptions
from easy_ytdlp.gui.widgets.option_sections import ClipSection
from easy_ytdlp.gui.widgets.time_input import MAX_SECONDS, TimeInput


@pytest.fixture
def field(qtbot) -> TimeInput:
    widget = TimeInput("Start")
    qtbot.addWidget(widget)
    widget.show()
    widget.setFocus()
    widget.setCursorPosition(0)
    return widget


def test_starts_at_zero_with_fixed_separators(field) -> None:
    assert field.text() == "00:00:00"
    assert field.value() == 0


@pytest.mark.parametrize(
    ("keys", "text", "cursor"),
    [
        ("01", "01:00:00", 3),  # two hour digits move on to the minutes
        ("0130", "01:30:00", 6),
        ("013045", "01:30:45", 8),
        ("007", "00:07:00", 6),  # 7 cannot start a minute value: read as 07
        ("0059", "00:59:00", 6),
        ("0067", "00:06:07", 8),  # 6 in the minutes, then 7 in the seconds
        ("00309", "00:30:09", 8),
        ("000005", "00:00:05", 8),
        ("1234567", "12:34:56", 8),  # nothing past the seconds
    ],
)
def test_typing_moves_through_the_parts(qtbot, field, keys, text, cursor) -> None:
    qtbot.keyClicks(field, keys)
    assert field.text() == text
    assert field.cursorPosition() == cursor


def test_value_follows_typing(qtbot, field) -> None:
    with qtbot.waitSignal(field.valueChanged) as signal:
        qtbot.keyClicks(field, "0001")
    assert signal.args == [60]
    qtbot.keyClicks(field, "3")
    assert field.value() == 90


def test_separator_jumps_to_next_part(qtbot, field) -> None:
    qtbot.keyClicks(field, "2:3:")
    assert field.cursorPosition() == 6
    assert field.text() == "20:30:00"


def test_letters_are_ignored(qtbot, field) -> None:
    qtbot.keyClicks(field, "a1b")
    assert field.text() == "10:00:00"


def test_backspace_clears_the_previous_digit(qtbot, field) -> None:
    qtbot.keyClicks(field, "0012")
    qtbot.keyClick(field, Qt.Key.Key_Backspace)
    assert field.text() == "00:10:00"
    assert field.cursorPosition() == 4


def test_typing_over_a_full_selection_starts_again(qtbot, field) -> None:
    field.setValue(3723)
    field.selectAll()
    qtbot.keyClicks(field, "0005")
    assert field.text() == "00:05:00"


def test_arrows_step_the_part_under_the_cursor(qtbot, field) -> None:
    field.setValue(59)
    field.setCursorPosition(7)
    qtbot.keyClick(field, Qt.Key.Key_Up)
    assert field.text() == "00:01:00"  # carry-over
    field.setCursorPosition(4)
    qtbot.keyClick(field, Qt.Key.Key_Down)
    qtbot.keyClick(field, Qt.Key.Key_Down)
    assert field.value() == 0  # never below zero


def test_paste_converts_other_formats(qtbot, field) -> None:
    QGuiApplication.clipboard().setText("1:30")
    qtbot.keyClick(field, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert field.text() == "00:01:30"
    QGuiApplication.clipboard().setText("nonsense")
    qtbot.keyClick(field, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert field.text() == "00:01:30"


def test_maximum_clamps(qtbot, field) -> None:
    field.setValue(500)
    field.setMaximum(120)
    assert field.text() == "00:02:00"
    qtbot.keyClicks(field, "0009")
    assert field.value() == 120  # typed 9 min, capped
    qtbot.keyClick(field, Qt.Key.Key_Return)
    assert field.text() == "00:02:00"
    field.setMaximum(None)
    field.setValue(10**9)
    assert field.value() == MAX_SECONDS


def clip_section(qtbot) -> ClipSection:
    section = ClipSection()
    qtbot.addWidget(section)
    section.show()
    section.enabled.setChecked(True)
    return section


def test_to_end_is_the_default_and_disables_the_end(qtbot) -> None:
    section = clip_section(qtbot)
    assert section.to_end.isChecked()
    assert not section.end.isEnabled()
    options = DownloadOptions()
    section.start.setValue(90)
    section.read(options)
    assert (options.clip.start, options.clip.end) == ("00:01:30", "")


def test_duration_limits_and_fills_the_end(qtbot, fixture_json) -> None:
    section = clip_section(qtbot)
    section.set_info(probe.parse_info(fixture_json("probe_video.json")))  # 19 s
    section.start.setValue(100)
    assert section.start.value() == 18
    section.start.setValue(4)
    assert section.length.text() == "Clip length: 0:15 (to the end)"
    section.to_end.setChecked(False)
    assert section.end.value() == 19
    section.end.setValue(10)
    assert section.length.text() == "Clip length: 0:06"
    section.end.setValue(3)
    assert section.end.property("invalid") == "true"
    assert "after the start" in section.length.text()


def test_playlist_has_no_duration_limit(qtbot, fixture_json) -> None:
    section = clip_section(qtbot)
    section.set_info(probe.parse_info(fixture_json("probe_playlist.json")))
    section.start.setValue(5000)
    assert section.start.value() == 5000
    assert not section.length.isVisible()


def test_loads_old_time_formats(qtbot) -> None:
    section = clip_section(qtbot)
    options = DownloadOptions()
    options.clip.enabled = True
    options.clip.start = "1:30.6"
    options.clip.end = "125"
    section.load(options)
    assert section.start.value() == 90
    assert section.end.value() == 125
    assert not section.to_end.isChecked()
    section.read(options)
    assert (options.clip.start, options.clip.end) == ("00:01:30", "00:02:05")
