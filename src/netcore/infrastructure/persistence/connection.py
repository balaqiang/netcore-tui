"""SQLite connection factory (WAL, foreign keys, busy timeout)."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

MEMORY = ":memory:"


class ConnectionFactory:
    """Opens configured connections; one per unit of work / thread.

    ``:memory:`` is mapped to a uniquely named shared-cache in-memory
    database kept alive by an anchor connection, so every unit of work
    sees the same data.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._anchor: sqlite3.Connection | None = None
        if self._path == MEMORY:
            self._uri = f"file:netcore-{uuid.uuid4().hex}?mode=memory&cache=shared"
            self._anchor = self._open()
        else:
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            self._uri = Path(self._path).resolve().as_uri()

    @property
    def path(self) -> str:
        """Configured database path (``:memory:`` for tests)."""
        return self._path

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._uri, uri=True, isolation_level=None, check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        if self._path != MEMORY:
            conn.execute("PRAGMA journal_mode = WAL")
        else:
            # Shared-cache readers must not block on table locks.
            conn.execute("PRAGMA read_uncommitted = 1")
        return conn

    def connect(self) -> sqlite3.Connection:
        """A new configured connection."""
        return self._open()

    def close(self) -> None:
        """Release the in-memory anchor (if any)."""
        if self._anchor is not None:
            self._anchor.close()
            self._anchor = None
