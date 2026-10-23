import pytest
from PySide6.QtGui import QKeySequence, QShortcut

from easy_ytdlp.gui import i18n
from easy_ytdlp.gui.main_window import MainWindow
from easy_ytdlp.gui.theme import icons
from easy_ytdlp.gui.theme.tokens import DARK, LIGHT, contrast_ratio


def make_window(qtbot, ctx) -> MainWindow:
    window = MainWindow(ctx)
    # Never open the modal "quit?" dialog when pytest-qt closes the window.
    window.confirm_quit = lambda pending: True
    qtbot.addWidget(window)
    return window


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("language", ["en", "es"])
def test_window_renders_in_every_theme_and_language(qtbot, ctx, theme, language) -> None:
    i18n.install(language)
    try:
        ctx.theme.set_mode(theme)
        window = make_window(qtbot, ctx)
        window.show()
        assert ctx.theme.is_dark is (theme == "dark")
        for key in window.pages:
            window.show_page(key)
            assert window.current_page() == key
            assert not window.grab().isNull()
        expected = "Cola" if language == "es" else "Queue"
        assert window.nav_buttons["queue"].text() == expected
    finally:
        i18n.install("en")


def test_shortcuts_switch_pages(qtbot, ctx) -> None:
    window = make_window(qtbot, ctx)
    window.show()
    # Offscreen windows are never active, so trigger the shortcut object directly.
    [shortcut] = [s for s in window.findChildren(QShortcut) if s.key() == QKeySequence("Ctrl+2")]
    shortcut.activated.emit()
    assert window.current_page() == "queue"


def test_state_is_saved_and_restored(qtbot, ctx) -> None:
    window = make_window(qtbot, ctx)
    window.show_page("command")
    window.save_state()
    assert ctx.settings.last_page == list(window.pages).index("command")
    assert ctx.settings.window_geometry

    again = make_window(qtbot, ctx)
    assert again.current_page() == "command"


def test_queue_badge_counts_pending_jobs(qtbot, ctx) -> None:
    window = make_window(qtbot, ctx)
    ctx.queue.add_command(["yt-dlp", "-x"], "job")
    qtbot.waitUntil(lambda: window.nav_buttons["queue"].text() == "Queue (1)")


@pytest.mark.parametrize("tokens", [LIGHT, DARK])
def test_token_contrast(tokens) -> None:
    pairs = [
        (tokens.foreground, tokens.background),
        (tokens.foreground, tokens.surface),
        (tokens.foreground, tokens.surface_muted),
        (tokens.muted_foreground, tokens.background),
        (tokens.muted_foreground, tokens.surface),
        (tokens.on_primary, tokens.primary),
        (tokens.on_accent, tokens.accent),
        (tokens.destructive, tokens.surface),
        (tokens.success, tokens.surface),
        (tokens.warning, tokens.surface),
        (tokens.foreground, tokens.selection),
    ]
    for foreground, background in pairs:
        assert contrast_ratio(foreground, background) >= 4.5, (foreground, background)


def test_every_icon_renders(qapp) -> None:
    names = sorted(p.stem for p in icons.ICONS.glob("*.svg"))
    assert len(names) > 30
    for name in names:
        assert not icons.icon(name).pixmap(18, 18).isNull(), name
