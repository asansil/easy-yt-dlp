"""Entry point for ``python -m easy_ytdlp`` and the frozen executable."""

import sys

from easy_ytdlp.app import main

if __name__ == "__main__":
    sys.exit(main())
