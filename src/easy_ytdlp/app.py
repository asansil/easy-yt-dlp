"""Application bootstrap: command-line flags, logging, the Qt application and the window."""

import argparse
import logging
import os
import sys
from collections.abc import Sequence

from easy_ytdlp import __version__
from easy_ytdlp.core import logs, paths

APP_NAME = "Easy yt-dlp"
ORG_NAME = "EasyYtDlp"

log = logging.getLogger(__name__)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="EasyYtDlp", add_help=True)
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    # Hidden: used by the installer smoke test and CI.
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(list(argv))


def _write(text: str) -> None:
    # Windowed (frozen) builds have no stdout.
    if sys.stdout is not None:
        print(text)


def self_test() -> int:
    """Start Qt offscreen, build the main window, check the folders; exit code 0 on success."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        from easy_ytdlp.core import command_builder, options, probe, queue, settings  # noqa: F401

        paths.ensure_dirs()
        probe_file = paths.data_dir() / ".self-test"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink()

        app = create_application()
        from easy_ytdlp.gui.context import AppContext
        from easy_ytdlp.gui.main_window import MainWindow

        ctx = AppContext(persist=False)
        ctx.theme.apply()
        window = MainWindow(ctx)
        window.show()
        app.processEvents()
        window.ctx.queue.shutdown()
        window.hide()
        app.processEvents()
    except Exception:
        log.exception("Self-test failed")
        _write("self-test: FAILED")
        return 1
    log.info("Self-test passed (version %s, install dir %s)", __version__, paths.install_dir())
    _write(f"self-test: OK ({__version__})")
    return 0


def create_application():
    """The QApplication with the app identity and the bundled fonts."""
    from PySide6.QtWidgets import QApplication

    from easy_ytdlp.gui import theme

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    theme.load_fonts()
    return app


def run_gui() -> int:
    app = create_application()
    from easy_ytdlp.gui import i18n
    from easy_ytdlp.gui.context import AppContext
    from easy_ytdlp.gui.main_window import MainWindow

    paths.ensure_dirs()
    from PySide6.QtCore import QTimer

    from easy_ytdlp.gui.dialogs import FirstRunDialog
    from easy_ytdlp.tools import migration

    ctx = AppContext()
    i18n.install(ctx.settings.language)
    ctx.theme.apply()
    window = MainWindow(ctx)
    window.show()
    settings = ctx.settings
    legacy = not settings.legacy_prompt_done and migration.legacy_present()
    if not settings.first_run_done or ctx.tools.missing() or legacy:
        dialog = FirstRunDialog(
            ctx.tools, channel=settings.ytdlp_channel, legacy=legacy, parent=window
        )
        dialog.exec()
        settings.first_run_done = True
        settings.legacy_prompt_done = True
        ctx.save_settings()
        window.banner.refresh()
    # Leave the window responsive first; the checks run in the background anyway.
    QTimer.singleShot(3000, window.startup_checks)
    return app.exec()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        _write(f"{APP_NAME} {__version__}")
        return 0
    logs.setup()
    if args.self_test:
        return self_test()
    log.info("Starting %s %s", APP_NAME, __version__)
    return run_gui()
