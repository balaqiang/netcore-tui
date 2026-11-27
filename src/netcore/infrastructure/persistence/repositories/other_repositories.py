"""Event, simulation, traffic and settings repositories (parameterised SQL)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from ipaddress import IPv4Address

from netcore.application.ports import CounterKey, CounterRow, EventFilter
from netcore.domain.enums import (
    Direction,
    DropReason,
    Protocol,
    SimulationStatus,
)
from netcore.domain.events import NetworkEvent, TrafficEvent
from netcore.domain.ids import DeviceId, LinkId
from netcore.domain.simulation.result import PacketRequest, SimulationResult
from netcore.infrastructure.persistence.mappers import (
    drop_reasons_from_json,
    drop_reasons_to_json,
    event_from_row,
    hop_from_row,
    require_ts,
    ts,
)


class SqliteEventRepository:
    """Audit events."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, event: NetworkEvent) -> int:
        """Insert an event."""
        cur = self._conn.execute(
            "INSERT INTO events(timestamp, severity, category, device_id, message, "
            "payload_json) VALUES (?, ?, ?, "
            "(SELECT id FROM devices WHERE id = ?), ?, ?)",
            (
                ts(event.timestamp),
                event.severity.value,
                event.category.value,
                event.device_id,
                event.message,
                json.dumps(dict(event.payload), default=str, sort_keys=True),
            ),
        )
        return int(cur.lastrowid or 0)

    def query(self, flt: EventFilter) -> list[NetworkEvent]:
        """Filter newest-first."""
        clauses: list[str] = []
        params: list[object] = []
        if flt.severities:
            marks = ",".join("?" for _ in flt.severities)
            clauses.append(f"severity IN ({marks})")
            params.extend(sorted(s.value for s in flt.severities))
        if flt.category is not None:
            clauses.append("category = ?")
            params.append(flt.category.value)
        if flt.device_id is not None:
            clauses.append("device_id = ?")
            params.append(flt.device_id)
        if flt.text:
            clauses.append("message LIKE ? ESCAPE '\\'")
            escaped = flt.text.replace("\\", "\\\\").replace("%", "\\%")
            params.append(f"%{escaped.replace('_', chr(92) + '_')}%")
        if flt.since is not None:
            clauses.append("timestamp >= ?")
            params.append(ts(flt.since))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(flt.limit)
        rows = self._conn.execute(
            f"SELECT * FROM events {where} ORDER BY timestamp DESC, id DESC LIMIT ?",
            params,
        ).fetchall()
        return [event_from_row(r) for r in rows]

    def prune(self, keep: int) -> int:
        """Keep the ``keep`` most recent events."""
        cur = self._conn.execute(
            "DELETE FROM events WHERE id NOT IN "
            "(SELECT id FROM events ORDER BY timestamp DESC, id DESC LIMIT ?)",
            (keep,),
        )
        return cur.rowcount

    def clear(self) -> None:
        """Delete all events."""
        self._conn.execute("DELETE FROM events")


class SqliteSimulationRepository:
    """Simulation run history with hop records."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, result: SimulationResult) -> int:
        """Insert run + hops."""
        req = result.request
        cur = self._conn.execute(
            "INSERT INTO simulation_runs(started_at, src_device_id, dst_ip, protocol, "
            "ttl, size_bytes, status, drop_reason, total_latency_ms, seed, path_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ts(result.started_at),
                req.src_device_id if req else None,
                str(req.dst_ip) if req else "",
                req.protocol.value if req else Protocol.ICMP.value,
                req.ttl if req else 0,
                req.size_bytes if req else 0,
                result.status.value,
                result.drop_reason.value if result.drop_reason else None,
                result.total_latency_ms,
                result.seed,
                json.dumps(list(result.path)),
            ),
        )
        run_id = int(cur.lastrowid or 0)
        self._conn.executemany(
            "INSERT INTO hop_records(run_id, hop_index, device_id, device_name, "
            "device_type, kind, ingress, egress, ttl_in, ttl_out, matched_route, "
            "reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    run_id,
                    h.index,
                    h.device_id,
                    h.device_name,
                    h.device_type.value,
                    h.kind.value,
                    h.ingress,
                    h.egress,
                    h.ttl_in,
                    h.ttl_out,
                    h.matched_route,
                    h.reason,
                )
                for h in result.hops
            ],
        )
        return run_id

    def recent(self, limit: int) -> list[SimulationResult]:
        """Newest runs first."""
        runs = self._conn.execute(
            "SELECT * FROM simulation_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        results: list[SimulationResult] = []
        for run in runs:
            hops = self._conn.execute(
                "SELECT * FROM hop_records WHERE run_id = ? ORDER BY hop_index",
                (run["id"],),
            ).fetchall()
            request = None
            if run["src_device_id"] is not None and run["dst_ip"]:
                request = PacketRequest(
                    DeviceId(run["src_device_id"]),
                    IPv4Address(run["dst_ip"]),
                    Protocol(run["protocol"]),
                    run["ttl"],
                    run["size_bytes"],
                )
            results.append(
                SimulationResult(
                    run_id=run["id"],
                    status=SimulationStatus(run["status"]),
                    drop_reason=DropReason(run["drop_reason"])
                    if run["drop_reason"]
                    else None,
                    hops=tuple(hop_from_row(h) for h in hops),
                    path=tuple(DeviceId(d) for d in json.loads(run["path_json"])),
                    total_latency_ms=run["total_latency_ms"],
                    started_at=require_ts(run["started_at"]),
                    seed=run["seed"],
                    request=request,
                )
            )
        return results

    def clear(self) -> None:
        """Delete all runs."""
        self._conn.execute("DELETE FROM simulation_runs")


class SqliteTrafficRepository:
    """Simulated counters keyed by (device, link, direction)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def apply(self, events: Iterable[TrafficEvent]) -> None:
        """Accumulate deltas."""
        for ev in events:
            row = self._conn.execute(
                "SELECT id, drop_reasons_json FROM traffic_counters "
                "WHERE device_id IS ? AND link_id IS ? AND direction = ?",
                (ev.device_id, ev.link_id, ev.direction.value),
            ).fetchone()
            reasons = drop_reasons_from_json(row["drop_reasons_json"]) if row else {}
            if ev.dropped and ev.drop_reason is not None:
                reasons[ev.drop_reason] = reasons.get(ev.drop_reason, 0) + ev.dropped
            if row is None:
                self._conn.execute(
                    "INSERT INTO traffic_counters(device_id, link_id, direction, "
                    "packets, bytes, dropped, drop_reasons_json) "
                    "SELECT ?, ?, ?, ?, ?, ?, ? WHERE "
                    "(? IS NULL OR EXISTS (SELECT 1 FROM devices WHERE id = ?)) AND "
                    "(? IS NULL OR EXISTS (SELECT 1 FROM links WHERE id = ?))",
                    (
                        ev.device_id,
                        ev.link_id,
                        ev.direction.value,
                        ev.packets,
                        ev.bytes,
                        ev.dropped,
                        drop_reasons_to_json(reasons),
                        ev.device_id,
                        ev.device_id,
                        ev.link_id,
                        ev.link_id,
                    ),
                )
            else:
                self._conn.execute(
                    "UPDATE traffic_counters SET packets = packets + ?, "
                    "bytes = bytes + ?, dropped = dropped + ?, drop_reasons_json = ? "
                    "WHERE id = ?",
                    (
                        ev.packets,
                        ev.bytes,
                        ev.dropped,
                        drop_reasons_to_json(reasons),
                        row["id"],
                    ),
                )

    def counters(self) -> dict[CounterKey, CounterRow]:
        """All counters."""
        result: dict[CounterKey, CounterRow] = {}
        for r in self._conn.execute("SELECT * FROM traffic_counters"):
            key: CounterKey = (
                DeviceId(r["device_id"]) if r["device_id"] is not None else None,
                LinkId(r["link_id"]) if r["link_id"] is not None else None,
                Direction(r["direction"]),
            )
            result[key] = CounterRow(
                r["packets"],
                r["bytes"],
                r["dropped"],
                drop_reasons_from_json(r["drop_reasons_json"]),
            )
        return result

    def reset(self) -> None:
        """Delete all counters."""
        self._conn.execute("DELETE FROM traffic_counters")


class SqliteSettingsRepository:
    """Key/value settings table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_all(self) -> dict[str, str]:
        """All settings."""
        return {
            r["key"]: r["value"]
            for r in self._conn.execute("SELECT key, value FROM settings")
        }

    def set_many(self, values: Mapping[str, str]) -> None:
        """Upsert settings."""
        self._conn.executemany(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            list(values.items()),
        )
