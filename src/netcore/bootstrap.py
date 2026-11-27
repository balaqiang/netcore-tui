"""Composition root: wires infrastructure into services (DEC-005)."""

from __future__ import annotations

from dataclasses import dataclass

from netcore.application.event_bus import EventBus
from netcore.application.ports import Clock
from netcore.application.services import ServiceContext, Services
from netcore.infrastructure.clock import SystemClock
from netcore.infrastructure.config import AppConfig
from netcore.infrastructure.exporter import FileEventExporter
from netcore.infrastructure.persistence.connection import ConnectionFactory
from netcore.infrastructure.persistence.migrator import Migrator
from netcore.infrastructure.persistence.unit_of_work import SqliteUnitOfWorkFactory


@dataclass(slots=True)
class Container:
    """Built application graph."""

    config: AppConfig
    services: Services
    connections: ConnectionFactory

    def close(self) -> None:
        """Release database resources."""
        self.connections.close()


def build_container(config: AppConfig, clock: Clock | None = None) -> Container:
    """Open the DB, migrate, construct services, optionally seed a lab."""
    connections = ConnectionFactory(config.db_path)
    conn = connections.connect()
    try:
        Migrator(conn).migrate()
    finally:
        conn.close()
    ctx = ServiceContext(
        uow_factory=SqliteUnitOfWorkFactory(connections),
        bus=EventBus(),
        clock=clock or SystemClock(),
        db_path=config.db_path,
        exporter=FileEventExporter(),
    )
    services = Services.build(ctx)
    if config.seed_lab and services.settings.lab_is_empty():
        services.settings.load_sample_lab(config.seed_lab)
    return Container(config, services, connections)
