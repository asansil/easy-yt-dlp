"""SQLite record of finished downloads.

Stores URLs, titles, output paths and options (no cookies or credentials: options only
name the browser, and command-mode arguments with secrets are stored masked and cannot
be re-run).
"""

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from easy_ytdlp.core import command_builder, paths
from easy_ytdlp.core.queue import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT '',
    output_dir TEXT NOT NULL DEFAULT '',
    files TEXT NOT NULL DEFAULT '[]',
    options TEXT,
    args TEXT,
    rerunnable INTEGER NOT NULL DEFAULT 1,
    finished_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS downloads_finished ON downloads (finished_at DESC);
"""


@dataclass
class HistoryEntry:
    id: int
    title: str
    url: str
    state: str
    error: str
    output_dir: str
    files: list[str] = field(default_factory=list)
    # Serialized DownloadOptions, or None for command-mode jobs.
    options: dict[str, Any] | None = None
    # User arguments of a command-mode job (masked when they contained secrets).
    args: list[str] | None = None
    rerunnable: bool = True
    finished_at: float = 0.0


class HistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or paths.history_file()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._db:
            self._db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def add_job(self, job: Job) -> int:
        args: list[str] | None = None
        rerunnable = True
        if job.options is None:
            user = command_builder.user_args(job.argv)
            masked = command_builder.mask_secrets(user)
            args = masked
            rerunnable = masked == user
        with self._lock, self._db:
            cursor = self._db.execute(
                "INSERT INTO downloads (title, url, state, error, output_dir, files, options,"
                " args, rerunnable, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job.title,
                    job.url,
                    job.state.value,
                    job.error,
                    job.output_dir,
                    json.dumps(job.files, ensure_ascii=False),
                    json.dumps(job.options, ensure_ascii=False) if job.options else None,
                    json.dumps(args, ensure_ascii=False) if args is not None else None,
                    int(rerunnable),
                    job.finished_at or time.time(),
                ),
            )
            return int(cursor.lastrowid or 0)

    @staticmethod
    def _entry(row: sqlite3.Row) -> HistoryEntry:
        def load(text: str | None, fallback: Any) -> Any:
            try:
                return json.loads(text) if text else fallback
            except ValueError:
                return fallback

        return HistoryEntry(
            id=row["id"],
            title=row["title"],
            url=row["url"],
            state=row["state"],
            error=row["error"],
            output_dir=row["output_dir"],
            files=load(row["files"], []),
            options=load(row["options"], None),
            args=load(row["args"], None),
            rerunnable=bool(row["rerunnable"]),
            finished_at=row["finished_at"],
        )

    def search(self, text: str = "", *, state: str = "", limit: int = 500) -> list[HistoryEntry]:
        """Newest first; ``text`` matches title or URL, ``state`` filters by job state."""
        query = "SELECT * FROM downloads WHERE 1 = 1"
        params: list[Any] = []
        if text.strip():
            pattern = (
                "%"
                + text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                + "%"
            )
            query += " AND (title LIKE ? ESCAPE '\\' OR url LIKE ? ESCAPE '\\')"
            params += [pattern, pattern]
        if state:
            query += " AND state = ?"
            params.append(state)
        query += " ORDER BY finished_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._db.execute(query, params).fetchall()
        return [self._entry(row) for row in rows]

    def get(self, entry_id: int) -> HistoryEntry | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM downloads WHERE id = ?", (entry_id,)).fetchone()
        return self._entry(row) if row else None

    def delete(self, entry_id: int) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM downloads WHERE id = ?", (entry_id,))

    def clear(self) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM downloads")

    def count(self) -> int:
        with self._lock:
            return int(self._db.execute("SELECT COUNT(*) FROM downloads").fetchone()[0])
