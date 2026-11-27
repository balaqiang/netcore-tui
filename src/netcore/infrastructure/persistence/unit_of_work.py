"""SqliteUnitOfWork — BEGIN on enter, COMMIT on success, ROLLBACK on error."""

from __future__ import annotations

import sqlite3
from types import TracebackType
from typing import Self

from netcore.infrastructure.persistence.connection import ConnectionFactory
from netcore.infrastructure.persistence.repositories.other_repositories import (
    SqliteEventRepository,
    SqliteSettingsRepository,
    SqliteSimulationRepository,
    SqliteTrafficRepository,
)
from netcore.infrastructure.persistence.repositories.topology_repository import (
    SqliteTopologyRepository,
)


class SqliteUnitOfWork:
    """One connection + one transaction per ``with`` block."""

    def __init__(self, factory: ConnectionFactory) -> None:
        self._factory = factory
        self._conn: sqlite3.Connection | None = None

    def _require(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Unit of work used outside its 'with' block.")
        return self._conn

    @property
    def topology(self) -> SqliteTopologyRepository:
        """Topology repository."""
        return SqliteTopologyRepository(self._require())

    @property
    def events(self) -> SqliteEventRepository:
        """Event repository."""
        return SqliteEventRepository(self._require())

    @property
    def simulations(self) -> SqliteSimulationRepository:
        """Simulation repository."""
        return SqliteSimulationRepository(self._require())

    @property
    def traffic(self) -> SqliteTrafficRepository:
        """Traffic counter repository."""
        return SqliteTrafficRepository(self._require())

    @property
    def settings(self) -> SqliteSettingsRepository:
        """Settings repository."""
        return SqliteSettingsRepository(self._require())

    def __enter__(self) -> Self:
        conn = self._factory.connect()
        conn.execute("BEGIN")
        self._conn = conn
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def commit(self) -> None:
        """Commit the transaction (and start a new one if still open)."""
        if self._conn is not None and self._conn.in_transaction:
            self._conn.execute("COMMIT")

    def rollback(self) -> None:
        """Roll back the transaction."""
        if self._conn is not None and self._conn.in_transaction:
            self._conn.execute("ROLLBACK")


class SqliteUnitOfWorkFactory:
    """Callable producing units of work bound to one database."""

    def __init__(self, factory: ConnectionFactory) -> None:
        self._factory = factory

    def __call__(self) -> SqliteUnitOfWork:
        return SqliteUnitOfWork(self._factory)

    @property
    def db_path(self) -> str:
        """Database location."""
        return self._factory.path
