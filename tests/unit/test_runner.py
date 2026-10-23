import sys
import threading
import time
from pathlib import Path

import pytest

from easy_ytdlp.core.runner import ProcessRunner, child_pids


def run(code: str) -> tuple[list[str], int | None]:
    lines: list[str] = []
    runner = ProcessRunner([sys.executable, "-c", code], lines.append)
    runner.start()
    return lines, runner.wait(30)


def test_streams_lines_and_exit_code() -> None:
    lines, code = run(
        "import sys; print('one', flush=True); print('two', file=sys.stderr); sys.exit(3)"
    )
    assert lines == ["one", "two"]
    assert code == 3


def test_carriage_returns_split_lines() -> None:
    lines, code = run(r"import sys; sys.stdout.write('a\rb\r\nc\n\nd')")
    assert lines == ["a", "b", "c", "d"]
    assert code == 0


def test_utf8_output() -> None:
    lines, _ = run("print('Canción ñ 日本')")
    assert lines == ["Canción ñ 日本"]


def test_on_exit_callback() -> None:
    done = threading.Event()
    codes: list[int] = []

    def on_exit(code: int) -> None:
        codes.append(code)
        done.set()

    runner = ProcessRunner([sys.executable, "-c", "pass"], lambda _: None, on_exit)
    runner.start()
    assert done.wait(30)
    assert codes == [0]
    assert not runner.running


def start_and_wait_for(runner: ProcessRunner, lines: list[str], marker: str) -> float:
    started = time.monotonic()
    runner.start()
    while marker not in lines and time.monotonic() - started < 20:
        time.sleep(0.05)
    return started


def test_cancel_kills_process_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    # The parent starts a child that would outlive a plain kill of the parent, and
    # never exits by itself, so the kill after the grace time is needed.
    monkeypatch.setattr(ProcessRunner, "grace_seconds", 1.0)
    code = (
        "import subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "print('started', flush=True); time.sleep(60)"
    )
    lines: list[str] = []
    runner = ProcessRunner([sys.executable, "-c", code], lines.append)
    started = start_and_wait_for(runner, lines, "started")
    runner.cancel()
    # wait() returns only when the pipe closes, i.e. when the child is dead too.
    assert runner.wait(20) is not None
    assert runner.cancelled
    assert time.monotonic() - started < 30


def test_cancel_lets_parent_clean_up(tmp_path: Path) -> None:
    # Like the PyInstaller bootloader of yt-dlp.exe: the parent waits for its child,
    # then cleans up. Cancelling must kill the child only, so the clean-up still runs.
    marker = tmp_path / "cleaned"
    code = (
        "import pathlib, subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "print('started', flush=True); child.wait(); "
        f"pathlib.Path({str(marker)!r}).write_text('ok')"
    )
    # The base interpreter: a venv python.exe may be a launcher with its own child.
    python = getattr(sys, "_base_executable", sys.executable)
    lines: list[str] = []
    runner = ProcessRunner([python, "-c", code], lines.append)
    started = start_and_wait_for(runner, lines, "started")
    runner.cancel()
    assert runner.wait(20) is not None
    assert marker.read_text() == "ok"
    assert time.monotonic() - started < ProcessRunner.grace_seconds + 20


def test_child_pids_lists_direct_children() -> None:
    code = (
        "import subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "print(child.pid, flush=True); time.sleep(60)"
    )
    python = getattr(sys, "_base_executable", sys.executable)
    lines: list[str] = []
    runner = ProcessRunner([python, "-c", code], lines.append)
    started = time.monotonic()
    runner.start()
    while not lines and time.monotonic() - started < 20:
        time.sleep(0.05)
    try:
        assert runner._process is not None
        assert child_pids(runner._process.pid) == [int(lines[0])]
    finally:
        runner.cancel()
        runner.wait(20)


def test_missing_executable_raises() -> None:
    runner = ProcessRunner(["Z:/definitely/missing.exe"], lambda _: None)
    with pytest.raises(OSError):
        runner.start()


def test_cancel_before_start_is_harmless() -> None:
    runner = ProcessRunner([sys.executable, "-c", "pass"], lambda _: None)
    runner.cancel()
    assert runner.cancelled
