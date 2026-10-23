"""Start, supervise and cancel one external process, streaming its output line by line."""

import contextlib
import ctypes
import os
import re
import subprocess
import threading
from collections.abc import Callable, Sequence
from ctypes import wintypes
from pathlib import Path
from typing import ClassVar

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

    # How long a cancelled process may take to exit by itself before it is killed.
    grace_seconds = 10.0

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
        """Stop the process and all its children (e.g. FFmpeg started by yt-dlp).

        yt-dlp.exe is a PyInstaller one-file program: the process we start only unpacks
        Python into ``%TEMP%\\_MEI*``, runs it as a child and deletes the folder when the
        child ends. So the children are killed first and the process is left to clean up
        and exit by itself; it is killed only if it is still running after a grace time.
        """
        self._cancelled.set()
        process = self._process
        if process is None or process.poll() is not None:
            return
        children = child_pids(process.pid)
        if not children:
            _kill(process)
            return
        for pid in children:
            _taskkill_tree(pid)
        threading.Thread(
            target=self._kill_after_grace, args=(process,), name="process-cancel", daemon=True
        ).start()

    def _kill_after_grace(self, process: subprocess.Popen) -> None:
        try:
            process.wait(self.grace_seconds)
        except subprocess.TimeoutExpired:
            _kill(process)


def _taskkill_tree(pid: int) -> None:
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            check=False,
            timeout=15,
        )


def _kill(process: subprocess.Popen) -> None:
    """Kill ``process`` and its whole tree at once."""
    _taskkill_tree(process.pid)
    if process.poll() is None:
        with contextlib.suppress(OSError):
            process.kill()


_TH32CS_SNAPPROCESS = 0x00000002
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _ProcessEntry(ctypes.Structure):
    _fields_: ClassVar = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def _kernel32() -> ctypes.WinDLL:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    entry_ptr = ctypes.POINTER(_ProcessEntry)
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, entry_ptr]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, entry_ptr]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, *[ctypes.POINTER(wintypes.FILETIME)] * 4]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    return kernel32


def _creation_time(kernel32: ctypes.WinDLL, pid: int) -> int | None:
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    finally:
        kernel32.CloseHandle(handle)


def child_pids(pid: int) -> list[int]:
    """Direct children of ``pid`` except its console host; empty when they cannot be listed."""
    if os.name != "nt":
        return []
    kernel32 = _kernel32()
    snapshot = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == _INVALID_HANDLE_VALUE:
        return []
    candidates: list[int] = []
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(_ProcessEntry)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            # conhost.exe is the hidden console Windows attaches, not a real child.
            if (
                entry.th32ParentProcessID == pid
                and entry.th32ProcessID != pid
                and entry.szExeFile.lower() != "conhost.exe"
            ):
                candidates.append(entry.th32ProcessID)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    # A parent PID can be stale: skip processes older than ``pid`` (their real parent
    # died and Windows reused its PID).
    started = _creation_time(kernel32, pid)
    if started is None:
        return []
    return [
        child
        for child in candidates
        if (created := _creation_time(kernel32, child)) is not None and created >= started
    ]
