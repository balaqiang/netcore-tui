"""Forward-only numbered SQL migrations (FR-DB-02)."""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from importlib import resources

_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


class Migrator:
    """Applies ``migrations/NNNN_name.sql`` files not yet recorded."""

    PACKAGE = "netcore.infrastructure.persistence.migrations"

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _available(self) -> list[tuple[int, str, str]]:
        files = resources.files(self.PACKAGE)
        found: list[tuple[int, str, str]] = []
        for entry in files.iterdir():
            match = _NAME.match(entry.name)
            if match:
                found.append((int(match.group(1)), entry.name, entry.read_text()))
        return sorted(found)

    def applied(self) -> set[int]:
        """Versions already applied."""
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        rows = self._conn.execute("SELECT version FROM schema_migrations").fetchall()
        return {int(r[0]) for r in rows}

    def migrate(self) -> list[int]:
        """Apply pending migrations in order; returns versions applied."""
        done = self.applied()
        applied: list[int] = []
        for version, _name, sql in self._available():
            if version in done:
                continue
            self._conn.execute("BEGIN")
            try:
                for statement in _split(sql):
                    self._conn.execute(statement)
                self._conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(UTC).isoformat()),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
            applied.append(version)
        return applied


def _split(sql: str) -> list[str]:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
