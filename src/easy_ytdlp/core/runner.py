"""Start, supervise and cancel one external process, streaming its output line by line."""

import contextlib
import os
import re
import subprocess
import threading
from collections.abc import Callable, Sequence
from pathlib import Path

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# yt-dlp and FFmpeg redraw progress with "\r"; treat it as a line break too.
_LINE_BREAK = re.compile(rb"\r\n|\r|\n")


def process_env() -> dict[str, str]:
    """Environment for child processes: force UTF-8 output from Python-based tools."""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


class ProcessRunner:
    """Run one command; report each output line and the exit code through callbacks.

    Callbacks are called from a background reader thread.
    """

    def __init__(
        self,
        argv: Sequence[str],
        on_line: Callable[[str], None],
        on_exit: Callable[[int], None] | None = None,
        *,
        cwd: Path | None = None,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    ) -> None:
        self.argv = list(argv)
        self._on_line = on_line
        self._on_exit = on_exit
        self._cwd = cwd
        self._popen = popen
        self._process: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._cancelled = threading.Event()
        self.returncode: int | None = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def running(self) -> bool:
        return self._process is not None and self.returncode is None

    def start(self) -> None:
        """Start the process. Raises OSError when the executable cannot be started."""
        self._process = self._popen(
            self.argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self._cwd,
            env=process_env(),
            creationflags=CREATE_NO_WINDOW,
        )
        self._reader = threading.Thread(target=self._read, name="process-reader", daemon=True)
        self._reader.start()

    def _read(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        stream = self._process.stdout
        buffer = b""
        while True:
            chunk = stream.read1(65536) if hasattr(stream, "read1") else stream.read(65536)
            if not chunk:
                break
            buffer += chunk
            *lines, buffer = _LINE_BREAK.split(buffer)
            for raw in lines:
                self._emit(raw)
        if buffer:
            self._emit(buffer)
        self.returncode = self._process.wait()
        if self._on_exit is not None:
            self._on_exit(self.returncode)

    def _emit(self, raw: bytes) -> None:
        line = raw.decode("utf-8", errors="replace")
        if line.strip():
            self._on_line(line)

    def wait(self, timeout: float | None = None) -> int | None:
        """Wait until the output is consumed and the process has exited."""
        if self._reader is not None:
            self._reader.join(timeout)
        return self.returncode

    def cancel(self) -> None:
        """Kill the process and all its children (e.g. FFmpeg started by yt-dlp)."""
        self._cancelled.set()
        process = self._process
        if process is None or process.poll() is not None:
            return
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                check=False,
                timeout=15,
            )
        if process.poll() is None:
            process.kill()
