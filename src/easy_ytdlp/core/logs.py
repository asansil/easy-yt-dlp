"""Application logging to a rotating file in the data folder."""

import logging
import logging.handlers
import sys

from easy_ytdlp.core import paths

LOG_FILE_NAME = "easy-ytdlp.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_configured = False


def setup(level: int = logging.INFO) -> None:
    """Log to ``logs/easy-ytdlp.log`` (rotated) and to stderr when there is one."""
    global _configured
    if _configured:
        return
    _configured = True
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(FORMAT)
    try:
        paths.logs_dir().mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            paths.logs_dir() / LOG_FILE_NAME,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
    except OSError:
        pass
    # Windowed (frozen) builds have no console: sys.stderr is None.
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)
