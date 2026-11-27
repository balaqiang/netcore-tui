"""Ports implemented by infrastructure (DEC-005)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from netcore.domain.enums import Direction, DropReason, EventCategory, Severity
from netcore.domain.events import NetworkEvent, TrafficEvent
from netcore.domain.ids import DeviceId, LinkId
from netcore.domain.simulation.result import SimulationResult
from netcore.domain.topology import NetworkTopology


class Clock(Protocol):
    """Source of the current UTC time."""

    def now(self) -> datetime:
        """Current time (timezone-aware UTC)."""
        ...


@dataclass(frozen=True, slots=True)
class EventFilter:
    """Event query criteria."""

    severities: frozenset[Severity] | None = None
    category: EventCategory | None = None
    device_id: DeviceId | None = None
    text: str = ""
    since: datetime | None = None
    limit: int = 1000


@dataclass(slots=True)
class CounterRow:
    """Accumulated simulated counters for one device/link direction."""

    packets: int = 0
    bytes: int = 0
    dropped: int = 0
    drop_reasons: dict[DropReason, int] = field(default_factory=dict)


CounterKey = tuple[DeviceId | None, LinkId | None, Direction]


class TopologyRepository(Protocol):
    """Loads/saves the whole topology aggregate (DEC-008)."""

    def load(self) -> NetworkTopology:
        """Load the current lab."""
        ...

    def save(self, topology: NetworkTopology) -> None:
        """Persist the lab."""
        ...

    def clear(self) -> None:
        """Delete the whole lab (devices, links, subnets, tables)."""
        ...


class EventRepository(Protocol):
    """Audit trail storage."""

    def add(self, event: NetworkEvent) -> int:
        """Store an event; returns its id."""
        ...

    def query(self, flt: EventFilter) -> list[NetworkEvent]:
        """Events matching ``flt``, newest first."""
        ...

    def prune(self, keep: int) -> int:
        """Delete all but the ``keep`` most recent events."""
        ...

    def clear(self) -> None:
        """Delete all events."""
        ...


class SimulationRepository(Protocol):
    """Simulation run history."""

    def add(self, result: SimulationResult) -> int:
        """Store a run with its hops; returns run id."""
        ...

    def recent(self, limit: int) -> list[SimulationResult]:
        """Most recent runs (hops included)."""
        ...

    def clear(self) -> None:
        """Delete all runs."""
        ...


class TrafficRepository(Protocol):
    """Simulated traffic counters."""

    def apply(self, events: Iterable[TrafficEvent]) -> None:
        """Add counter deltas."""
        ...

    def counters(self) -> dict[CounterKey, CounterRow]:
        """All counters."""
        ...

    def reset(self) -> None:
        """Zero all counters."""
        ...


class SettingsRepository(Protocol):
    """Key/value settings."""

    def get_all(self) -> dict[str, str]:
        """All stored settings."""
        ...

    def set_many(self, values: Mapping[str, str]) -> None:
        """Upsert settings."""
        ...


class UnitOfWork(Protocol):
    """Transaction boundary exposing repositories."""

    @property
    def topology(self) -> TopologyRepository:
        """Topology repository."""
        ...

    @property
    def events(self) -> EventRepository:
        """Event repository."""
        ...

    @property
    def simulations(self) -> SimulationRepository:
        """Simulation repository."""
        ...

    @property
    def traffic(self) -> TrafficRepository:
        """Traffic counter repository."""
        ...

    @property
    def settings(self) -> SettingsRepository:
        """Settings repository."""
        ...

    def __enter__(self) -> Self:
        """Begin a transaction."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Commit on success, roll back on exception."""
        ...

    def commit(self) -> None:
        """Commit now."""
        ...

    def rollback(self) -> None:
        """Roll back now."""
        ...


UnitOfWorkFactory = Callable[[], UnitOfWork]


class EventExporter(Protocol):
    """Writes exported events to a file (infrastructure)."""

    def exists(self, path: str) -> bool:
        """True if ``path`` already exists."""
        ...

    def write(self, path: str, rows: list[dict[str, object]], fmt: str) -> None:
        """Write ``rows`` as ``csv`` or ``json``."""
        ...
