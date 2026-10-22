"""The one helper every download goes through: HTTPS only, a timeout, a temp file and a
SHA-256 check before anything is moved into place."""

import hashlib
import json
import os
import re
import threading
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

TIMEOUT = 30
CHUNK_SIZE = 64 * 1024
USER_AGENT = "EasyYtDlp (+https://github.com/asansil/easy-yt-dlp)"

type ProgressCallback = Callable[[int, int | None], None]

_HASH_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")


class DownloadError(Exception):
    """A download failed: network error, bad status, wrong scheme or cancellation."""


class ChecksumError(DownloadError):
    """The downloaded file does not match its published SHA-256."""


class DownloadCancelled(DownloadError):
    pass


def _require_https(url: str) -> None:
    if not url.lower().startswith("https://"):
        raise DownloadError(f"Refusing non-HTTPS URL: {url}")


def _request(url: str, headers: dict[str, str] | None = None) -> urllib.request.Request:
    _require_https(url)
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})


def fetch_bytes(
    url: str, *, timeout: float = TIMEOUT, headers: dict[str, str] | None = None, opener=None
) -> bytes:
    opener = opener or urllib.request.urlopen
    try:
        with opener(_request(url, headers), timeout=timeout) as response:
            return response.read()
    except OSError as exc:
        raise DownloadError(f"Could not fetch {url}: {exc}") from exc


def fetch_text(url: str, **kwargs: Any) -> str:
    return fetch_bytes(url, **kwargs).decode("utf-8", errors="replace")


def fetch_json(url: str, **kwargs: Any) -> Any:
    kwargs.setdefault("headers", {"Accept": "application/vnd.github+json"})
    try:
        return json.loads(fetch_bytes(url, **kwargs))
    except ValueError as exc:
        raise DownloadError(f"Invalid JSON from {url}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksum(text: str, filename: str | None = None) -> str:
    """Extract a SHA-256 from a checksum file.

    Handles ``SHA2-256SUMS`` lists ("hash  name" or "hash *name"), single-hash files and
    PowerShell ``Get-FileHash`` output. With ``filename``, pick the line for that file.
    """
    if filename:
        for line in text.splitlines():
            parts = line.strip().split(maxsplit=1)
            if (
                len(parts) == 2
                and parts[1].lstrip("*").strip() == filename
                and _HASH_RE.fullmatch(parts[0])
            ):
                return parts[0].lower()
    hashes = _HASH_RE.findall(text)
    if filename is None and hashes:
        return hashes[0].lower()
    if filename is not None and len(hashes) == 1:
        return hashes[0].lower()
    raise ChecksumError(f"No SHA-256 found for {filename or 'file'}")


def download_file(
    url: str,
    destination: Path,
    *,
    expected_sha256: str | None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    timeout: float = TIMEOUT,
    opener=None,
) -> Path:
    """Download ``url`` to ``destination`` atomically.

    The data goes to ``<destination>.part``; it replaces ``destination`` only after the
    SHA-256 matches. Passing ``expected_sha256=None`` is allowed only for data that is
    verified some other way (e.g. a checksum file itself).
    """
    opener = opener or urllib.request.urlopen
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    digest = hashlib.sha256()
    try:
        with opener(_request(url), timeout=timeout) as response, part.open("wb") as fh:
            length = response.headers.get("Content-Length")
            total = int(length) if length and length.isdigit() else None
            done = 0
            while True:
                if cancel is not None and cancel.is_set():
                    raise DownloadCancelled("Download cancelled")
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)
        if expected_sha256 is not None and digest.hexdigest() != expected_sha256.lower():
            raise ChecksumError(f"Checksum mismatch for {url}")
        replace_file(part, destination)
    except DownloadError:
        part.unlink(missing_ok=True)
        raise
    except OSError as exc:
        part.unlink(missing_ok=True)
        raise DownloadError(f"Could not download {url}: {exc}") from exc
    return destination


def extract_member(archive: Path, pattern: str, destination: Path) -> Path:
    """Extract exactly one ZIP member whose name matches ``pattern`` to ``destination``.

    Members are selected by name and written to a path we choose, so a hostile archive
    cannot write anywhere else (no ``extractall``).
    """
    regex = re.compile(pattern, re.IGNORECASE)
    try:
        with zipfile.ZipFile(archive) as zf:
            matches = [name for name in zf.namelist() if regex.fullmatch(name)]
            if len(matches) != 1:
                raise DownloadError(f"Expected one {pattern!r} in {archive.name}")
            part = destination.with_name(destination.name + ".part")
            with zf.open(matches[0]) as src, part.open("wb") as dst:
                for chunk in iter(lambda: src.read(CHUNK_SIZE), b""):
                    dst.write(chunk)
    except zipfile.BadZipFile as exc:
        raise DownloadError(f"{archive.name} is not a valid ZIP file") from exc
    replace_file(part, destination)
    return destination


def replace_file(source: Path, destination: Path) -> None:
    """Move ``source`` over ``destination``; a locked target (exe in use) raises DownloadError."""
    try:
        os.replace(source, destination)
    except PermissionError as exc:
        source.unlink(missing_ok=True)
        raise DownloadError(f"{destination.name} is in use; close it and try again") from exc
