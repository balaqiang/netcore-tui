"""MonitoringService — US-TRF-1..4, dashboard summary."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from netcore.application.dto import (
    DashboardDTO,
    DeviceStatsDTO,
    DeviceStatus,
    FlowDTO,
    LinkStatsDTO,
    StartFlowRequest,
)
from netcore.application.errors import ApplicationError, translate_errors
from netcore.application.ports import CounterKey, CounterRow, EventFilter
from netcore.application.services._common import (
    BaseService,
    ServiceContext,
    event_dto,
    link_dto,
    seeded_rng,
    sim_settings,
)
from netcore.domain.addressing import parse_ipv4_address
from netcore.domain.enums import Direction, EventCategory, Severity
from netcore.domain.ids import DeviceId
from netcore.domain.simulation.engine import ForwardingEngine
from netcore.domain.simulation.traffic import (
    FlowReport,
    TrafficFlow,
    TrafficGenerator,
    utilization_pct,
)


@dataclass(frozen=True, slots=True)
class _ActiveFlow:
    flow_id: int
    report: FlowReport
    started_at: datetime
    src_name: str


class MonitoringService(BaseService):
    """Counters, utilization and simulated flows (all values simulated)."""

    def __init__(self, ctx: ServiceContext) -> None:
        super().__init__(ctx)
        self._lock = threading.Lock()
        self._flows: dict[int, _ActiveFlow] = {}
        self._next_flow = 1
        self._generator = TrafficGenerator()

    # ---------------------------------------------------------------- flows
    def _active(self) -> list[_ActiveFlow]:
        now = self._now()
        with self._lock:
            expired = [
                fid
                for fid, f in self._flows.items()
                if now >= f.started_at + timedelta(seconds=f.report.flow.duration_s)
            ]
            for fid in expired:
                del self._flows[fid]
            return list(self._flows.values())

    def _flow_dto(self, flow: _ActiveFlow) -> FlowDTO:
        elapsed = (self._now() - flow.started_at).total_seconds()
        f = flow.report.flow
        return FlowDTO(
            flow_id=flow.flow_id,
            src_name=flow.src_name,
            dst_ip=str(f.dst_ip),
            protocol=f.protocol,
            packet_size=f.packet_size,
            packets_per_second=f.packets_per_second,
            duration_s=f.duration_s,
            remaining_s=max(0, int(f.duration_s - elapsed)),
            load_mbps=round(f.load_mbps, 3),
            delivered=flow.report.probe.delivered,
            drop_reason=flow.report.probe.drop_reason,
            congestion_drops=flow.report.congestion_drops,
        )

    def flows(self) -> list[FlowDTO]:
        """Active flows with remaining duration."""
        return [self._flow_dto(f) for f in self._active()]

    def start_flow(self, req: StartFlowRequest) -> FlowDTO:
        """Start a simulated flow (US-TRF-3)."""
        active = self._active()
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            settings = self._settings(uow)
            src = topo.get_device(DeviceId(req.src_device_id))
            flow = TrafficFlow(
                src.id,
                parse_ipv4_address(req.dst_ip.strip()),
                req.protocol,
                req.packet_size,
                req.packets_per_second,
                req.duration_s,
                settings.seed,
            )
            engine = ForwardingEngine(
                topo,
                sim_settings(settings),
                seeded_rng(settings.seed, 1),
                self._now(),
                settings.seed,
            )
            existing = self._generator.load_by_direction(a.report for a in active)
            report = self._generator.run(flow, topo, engine, self._now(), existing)
            uow.topology.save(topo)
            uow.traffic.apply(report.events)
            evs = [
                self._event(
                    Severity.INFO,
                    EventCategory.TRAFFIC,
                    f"flow {src.hostname} → {flow.dst_ip} started: "
                    f"{flow.packets_per_second} pps x {flow.packet_size} B for "
                    f"{flow.duration_s} s ({flow.load_mbps:.2f} Mbps, simulated)",
                    src.id,
                )
            ]
            if not report.probe.delivered:
                reason = report.probe.drop_reason
                evs.append(
                    self._event(
                        Severity.WARNING,
                        EventCategory.TRAFFIC,
                        f"flow {src.hostname} → {flow.dst_ip} undeliverable: "
                        f"{reason.value if reason else 'DROPPED'}",
                        src.id,
                    )
                )
            if report.congestion_drops:
                evs.append(
                    self._event(
                        Severity.WARNING,
                        EventCategory.TRAFFIC,
                        f"congestion on path of flow {src.hostname} → {flow.dst_ip}: "
                        f"{report.congestion_drops} packets dropped (simulated)",
                        src.id,
                    )
                )
            events = self._store(uow, evs)
        with self._lock:
            flow_id = self._next_flow
            self._next_flow += 1
            record = _ActiveFlow(flow_id, report, self._now(), src.hostname)
            if report.probe.delivered:
                self._flows[flow_id] = record
        self._publish(events)
        return self._flow_dto(record)

    def stop_flow(self, flow_id: int) -> None:
        """Stop an active flow."""
        with self._lock:
            flow = self._flows.pop(flow_id, None)
        if flow is None:
            raise ApplicationError(
                "APP005", f"Flow {flow_id} is not active.", "not_found"
            )
        event = self._event(
            Severity.INFO,
            EventCategory.TRAFFIC,
            f"flow {flow.src_name} → {flow.report.flow.dst_ip} stopped",
        )
        with self._ctx.uow_factory() as uow:
            events = self._store(uow, [event])
        self._publish(events)

    def reset_counters(self) -> None:
        """Zero all simulated counters."""
        with self._ctx.uow_factory() as uow:
            uow.traffic.reset()
            events = self._store(
                uow,
                [self._event(Severity.INFO, EventCategory.TRAFFIC, "counters reset")],
            )
        self._publish(events)

    # ---------------------------------------------------------------- stats
    def link_stats(self) -> list[LinkStatsDTO]:
        """Per-link capacity, simulated load/utilization and counters."""
        active = [a.report for a in self._active()]
        loads = self._generator.load_by_direction(active)
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            counters = uow.traffic.counters()
        result = []
        for link in topo.links():
            ab = counters.get((None, link.id, Direction.A_TO_B), CounterRow())
            ba = counters.get((None, link.id, Direction.B_TO_A), CounterRow())
            load = max(
                loads.get((link.id, Direction.A_TO_B), 0.0),
                loads.get((link.id, Direction.B_TO_A), 0.0),
            )
            result.append(
                LinkStatsDTO(
                    link_id=link.id,
                    label=link_dto(topo, link).label,
                    capacity_mbps=link.capacity_mbps,
                    load_mbps=round(load, 3),
                    utilization_pct=utilization_pct(load, link.capacity_mbps),
                    tx_packets=ab.packets,
                    rx_packets=ba.packets,
                    dropped=ab.dropped + ba.dropped,
                    admin_up=link.admin_up,
                )
            )
        return result

    def device_stats(self) -> list[DeviceStatsDTO]:
        """Per-device simulated counters (top talkers first)."""
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            counters = uow.traffic.counters()
        result = []
        for device in topo.devices():
            tx = counters.get((device.id, None, Direction.TX), CounterRow())
            rx = counters.get((device.id, None, Direction.RX), CounterRow())
            reasons: dict = {}
            for row in (tx, rx):
                for reason, count in row.drop_reasons.items():
                    reasons[reason] = reasons.get(reason, 0) + count
            top = max(reasons, key=lambda r: reasons[r]).value if reasons else None
            result.append(
                DeviceStatsDTO(
                    device_id=device.id,
                    hostname=device.hostname,
                    tx_packets=tx.packets,
                    rx_packets=rx.packets,
                    tx_bytes=tx.bytes,
                    rx_bytes=rx.bytes,
                    dropped=tx.dropped + rx.dropped,
                    top_drop_reason=top,
                )
            )
        result.sort(key=lambda d: (-(d.tx_packets + d.rx_packets), d.hostname))
        return result

    def dashboard_summary(self) -> DashboardDTO:
        """Health overview (UI_SPEC §5.1)."""
        links = self.link_stats()
        since = self._now() - timedelta(hours=1)
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            settings = self._settings(uow)
            recent = uow.events.query(
                EventFilter(
                    severities=frozenset(
                        {
                            Severity.INFO,
                            Severity.WARNING,
                            Severity.ERROR,
                            Severity.CRITICAL,
                        }
                    ),
                    limit=10,
                )
            )
            hour = uow.events.query(
                EventFilter(
                    severities=frozenset(
                        {Severity.WARNING, Severity.ERROR, Severity.CRITICAL}
                    ),
                    since=since,
                    limit=100_000,
                )
            )
        statuses = [d.status for d in topo.devices()]
        total_hosts = used_hosts = 0
        for subnet in topo.subnets():
            total_hosts += subnet.usable_hosts()
            used_hosts += len(topo.addresses_in(subnet))
        up = sum(
            1
            for lk in topo.links()
            if topo.is_operational(lk.endpoint_a) and topo.is_operational(lk.endpoint_b)
        )
        top = tuple(sorted(links, key=lambda s: -s.utilization_pct)[:5])
        return DashboardDTO(
            lab_name=settings.lab_name,
            device_total=len(statuses),
            online=statuses.count(DeviceStatus.ONLINE),
            offline=statuses.count(DeviceStatus.OFFLINE),
            maintenance=statuses.count(DeviceStatus.MAINTENANCE),
            link_total=len(links),
            links_up=up,
            links_down=len(links) - up,
            subnet_count=len(topo.subnets()),
            subnet_util_pct=round(used_hosts / total_hosts * 100, 1)
            if total_hosts
            else 0.0,
            warnings_1h=sum(1 for e in hour if e.severity is Severity.WARNING),
            errors_1h=sum(1 for e in hour if e.severity is not Severity.WARNING),
            top_links=top,
            recent_events=tuple(event_dto(topo, e) for e in recent),
        )

    def counters_snapshot(self) -> dict[CounterKey, CounterRow]:
        """Raw counters (diagnostics/tests)."""
        with self._ctx.uow_factory() as uow:
            return uow.traffic.counters()
