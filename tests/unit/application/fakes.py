"""In-memory fake UnitOfWork for service unit tests."""

from __future__ import annotations

import copy
from dataclasses import replace

from netcore.application.ports import CounterKey, CounterRow, EventFilter
from netcore.domain.events import NetworkEvent, TrafficEvent
from netcore.domain.simulation.result import SimulationResult
from netcore.domain.topology import NetworkTopology


class FakeStore:
    """Shared state across fake units of work."""

    def __init__(self) -> None:
        self.topology = NetworkTopology()
        self.events: list[NetworkEvent] = []
        self.runs: list[SimulationResult] = []
        self.counters: dict[CounterKey, CounterRow] = {}
        self.settings: dict[str, str] = {}
        self.commits = 0


class _Topo:
    def __init__(self, store: FakeStore) -> None:
        self.s = store

    def load(self) -> NetworkTopology:
        return copy.deepcopy(self.s.topology)

    def save(self, topology: NetworkTopology) -> None:
        self.s.topology = copy.deepcopy(topology)

    def clear(self) -> None:
        self.s.topology = NetworkTopology()


class _Events:
    def __init__(self, store: FakeStore) -> None:
        self.s = store

    def add(self, event: NetworkEvent) -> int:
        new_id = len(self.s.events) + 1
        self.s.events.append(replace(event, id=new_id))
        return new_id

    def query(self, flt: EventFilter) -> list[NetworkEvent]:
        out = []
        for e in reversed(self.s.events):
            if flt.severities and e.severity not in flt.severities:
                continue
            if flt.category and e.category is not flt.category:
                continue
            if flt.device_id is not None and e.device_id != flt.device_id:
                continue
            if flt.text and flt.text not in e.message:
                continue
            if flt.since and e.timestamp < flt.since:
                continue
            out.append(e)
        return out[: flt.limit]

    def prune(self, keep: int) -> int:
        removed = max(0, len(self.s.events) - keep)
        self.s.events = self.s.events[removed:]
        return removed

    def clear(self) -> None:
        self.s.events.clear()


class _Sims:
    def __init__(self, store: FakeStore) -> None:
        self.s = store

    def add(self, result: SimulationResult) -> int:
        run_id = len(self.s.runs) + 1
        self.s.runs.append(replace(result, run_id=run_id))
        return run_id

    def recent(self, limit: int) -> list[SimulationResult]:
        return list(reversed(self.s.runs))[:limit]

    def clear(self) -> None:
        self.s.runs.clear()


class _Traffic:
    def __init__(self, store: FakeStore) -> None:
        self.s = store

    def apply(self, events: list[TrafficEvent]) -> None:
        for e in events:
            row = self.s.counters.setdefault(
                (e.device_id, e.link_id, e.direction), CounterRow()
            )
            row.packets += e.packets
            row.bytes += e.bytes
            row.dropped += e.dropped
            if e.dropped and e.drop_reason:
                row.drop_reasons[e.drop_reason] = (
                    row.drop_reasons.get(e.drop_reason, 0) + e.dropped
                )

    def counters(self) -> dict[CounterKey, CounterRow]:
        return copy.deepcopy(self.s.counters)

    def reset(self) -> None:
        self.s.counters.clear()


class _Settings:
    def __init__(self, store: FakeStore) -> None:
        self.s = store

    def get_all(self) -> dict[str, str]:
        return dict(self.s.settings)

    def set_many(self, values) -> None:
        self.s.settings.update(values)


class FakeUnitOfWork:
    """Snapshot-on-enter, write-back-on-commit fake."""

    def __init__(self, store: FakeStore) -> None:
        self._store = store

    def __enter__(self):
        self._backup = copy.deepcopy(self._store.__dict__)
        self.topology = _Topo(self._store)
        self.events = _Events(self._store)
        self.simulations = _Sims(self._store)
        self.traffic = _Traffic(self._store)
        self.settings = _Settings(self._store)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    def commit(self) -> None:
        self._store.commits += 1
        self._backup = copy.deepcopy(self._store.__dict__)

    def rollback(self) -> None:
        self._store.__dict__.update(copy.deepcopy(self._backup))
