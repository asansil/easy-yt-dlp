"""User PATH editing (ported from v1's ``update_user_path`` and ``refresh_environment``).

Only the app's own entry in ``HKCU\\Environment\\Path`` is ever added or removed; the other
entries and the value type (usually ``REG_EXPAND_SZ``) are preserved.
"""

import ctypes
import os
from pathlib import Path

REG_SZ = 1
REG_EXPAND_SZ = 2
_ENV_KEY = "Environment"


def _normalize(entry: str) -> str:
    return os.path.normcase(os.path.expandvars(entry.strip().strip('"'))).rstrip("\\/")


def _split(value: str) -> list[str]:
    return [part for part in value.split(";") if part.strip()]


def contains(path_value: str, entry: Path | str) -> bool:
    target = _normalize(str(entry))
    return any(_normalize(part) == target for part in _split(path_value))


def with_entry(path_value: str, entry: Path | str) -> str | None:
    """PATH value with ``entry`` appended, or None when it is already present."""
    if contains(path_value, entry):
        return None
    return ";".join([*_split(path_value), str(entry)])


def without_entry(path_value: str, entry: Path | str) -> str | None:
    """PATH value without ``entry``, or None when it was not present."""
    target = _normalize(str(entry))
    parts = _split(path_value)
    kept = [part for part in parts if _normalize(part) != target]
    if len(kept) == len(parts):
        return None
    return ";".join(kept)


def read_user_path() -> tuple[str, int]:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _ENV_KEY, 0, winreg.KEY_READ) as key:
        try:
            value, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            return "", REG_EXPAND_SZ
    return str(value), kind if kind in (REG_SZ, REG_EXPAND_SZ) else REG_EXPAND_SZ


def write_user_path(value: str, kind: int = REG_EXPAND_SZ) -> None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _ENV_KEY, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "Path", 0, kind, value)
    except PermissionError as exc:
        raise RuntimeError("Could not modify the user PATH") from exc


def refresh_environment() -> None:
    """Tell running programs (Explorer, new terminals) that the environment changed."""
    hwnd_broadcast = 0xFFFF
    wm_settingchange = 0x001A
    smto_abortifhung = 0x0002
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(  # type: ignore[attr-defined]
        hwnd_broadcast,
        wm_settingchange,
        0,
        "Environment",
        smto_abortifhung,
        5000,
        ctypes.byref(result),
    )


def is_in_user_path(entry: Path | str) -> bool:
    return contains(read_user_path()[0], entry)


def add_to_user_path(entry: Path | str) -> bool:
    """Add ``entry`` to the user PATH. Returns True when the PATH changed."""
    value, kind = read_user_path()
    new_value = with_entry(value, entry)
    if new_value is None:
        return False
    write_user_path(new_value, kind)
    refresh_environment()
    return True


def remove_from_user_path(entry: Path | str) -> bool:
    """Remove ``entry`` from the user PATH. Returns True when the PATH changed."""
    value, kind = read_user_path()
    new_value = without_entry(value, entry)
    if new_value is None:
        return False
    write_user_path(new_value, kind)
    refresh_environment()
    return True
