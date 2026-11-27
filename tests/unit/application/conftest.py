"""Service fixtures over fake and SQLite backends."""

from __future__ import annotations

import pytest

from netcore.application.event_bus import EventBus
from netcore.application.services import ServiceContext, Services
from netcore.infrastructure.clock import FixedClock
from netcore.infrastructure.exporter import FileEventExporter
from netcore.infrastructure.persistence.connection import ConnectionFactory
from netcore.infrastructure.persistence.migrator import Migrator
from netcore.infrastructure.persistence.unit_of_work import SqliteUnitOfWorkFactory
from tests.conftest import FIXED_NOW
from tests.unit.application.fakes import FakeStore, FakeUnitOfWork


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(FIXED_NOW)


@pytest.fixture(params=["fake", "sqlite"])
def services(request, clock) -> Services:
    if request.param == "fake":
        store = FakeStore()
        factory = lambda: FakeUnitOfWork(store)  # noqa: E731
        db_path = ":memory:"
    else:
        conns = ConnectionFactory(":memory:")
        Migrator(conns.connect()).migrate()
        factory = SqliteUnitOfWorkFactory(conns)
        request.addfinalizer(conns.close)
        db_path = ":memory:"
    ctx = ServiceContext(factory, EventBus(), clock, db_path, FileEventExporter())
    return Services.build(ctx)


@pytest.fixture
def lab(services) -> Services:
    services.settings.load_sample_lab("two-router")
    return services


def dev_id(services: Services, name: str) -> int:
    return next(d.id for d in services.devices.list_devices() if d.hostname == name)
