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
        from PySide6.QtWidgets import QApplication

        from easy_ytdlp.core import command_builder, options, probe, queue, settings  # noqa: F401
        from easy_ytdlp.gui.main_window import MainWindow

        paths.ensure_dirs()
        probe_file = paths.data_dir() / ".self-test"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink()

        app = QApplication.instance() or QApplication([sys.argv[0]])
        window = MainWindow()
        window.close()
        app.processEvents()
    except Exception:
        log.exception("Self-test failed")
        _write("self-test: FAILED")
        return 1
    log.info("Self-test passed (version %s, install dir %s)", __version__, paths.install_dir())
    _write(f"self-test: OK ({__version__})")
    return 0


def run_gui() -> int:
    from PySide6.QtWidgets import QApplication

    from easy_ytdlp.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    window = MainWindow()
    window.show()
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
