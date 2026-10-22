"""Entry point for ``python -m easy_ytdlp``."""

import sys

from easy_ytdlp import __version__


def main() -> int:
    # Placeholder until the main window lands in M2.
    print(f"Easy yt-dlp {__version__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
