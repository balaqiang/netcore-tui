"""SimulationService — US-SIM-1..5."""

from __future__ import annotations

from netcore.application.dto import (
    SendPacketRequest,
    SimulationResultDTO,
    SimulationSummaryDTO,
    TracerouteDTO,
    TracerouteHopDTO,
)
from netcore.application.errors import translate_errors
from netcore.application.ports import UnitOfWork
from netcore.application.services._common import (
    BaseService,
    hop_event_category,
    result_dto,
    seeded_rng,
    sim_settings,
)
from netcore.domain.addressing import parse_ipv4_address
from netcore.domain.enums import EventCategory, HopKind, Severity
from netcore.domain.events import NetworkEvent
from netcore.domain.ids import DeviceId
from netcore.domain.simulation.engine import ForwardingEngine
from netcore.domain.simulation.result import PacketRequest, SimulationResult
from netcore.domain.simulation.traffic import counter_events
from netcore.domain.topology import NetworkTopology

_FORWARD_KINDS = (HopKind.ROUTE, HopKind.SWITCH, HopKind.FLOOD, HopKind.ARP)


class SimulationService(BaseService):
    """Runs the forwarding engine and records results."""

    def _engine(self, uow: UnitOfWork, topo: NetworkTopology) -> ForwardingEngine:
        settings = self._settings(uow)
        return ForwardingEngine(
            topo,
            sim_settings(settings),
            seeded_rng(settings.seed, 0),
            self._now(),
            settings.seed,
        )

    def _request(self, uow: UnitOfWork, req: SendPacketRequest) -> PacketRequest:
        ttl = req.ttl if req.ttl is not None else self._settings(uow).default_ttl
        return PacketRequest(
            DeviceId(req.src_device_id),
            parse_ipv4_address(req.dst_ip.strip()),
            req.protocol,
            ttl,
            req.size_bytes,
            req.payload,
        )

    def _record(
        self, uow: UnitOfWork, topo: NetworkTopology, result: SimulationResult
    ) -> tuple[SimulationResult, list[NetworkEvent]]:
        uow.topology.save(topo)  # persist learned ARP / MAC state
        run_id = uow.simulations.add(result)
        size = result.request.size_bytes if result.request else 64
        uow.traffic.apply(counter_events(result, 1, size, self._now()))
        evs: list[NetworkEvent] = [
            self._event(
                Severity.DEBUG,
                hop_event_category(h.kind),
                f"{h.kind.value} at {h.device_name}: {h.reason}",
                h.device_id,
                run_id=run_id,
                hop=h.index,
            )
            for h in result.hops
            if h.kind in _FORWARD_KINDS
        ]
        dst = result.request.dst_ip if result.request else "?"
        src = topo.get_device(result.path[0]).hostname if result.path else "?"
        if result.delivered:
            evs.append(
                self._event(
                    Severity.INFO,
                    EventCategory.DELIVERY,
                    f"packet {src} → {dst} delivered ({len(result.path) - 1} hops)",
                    result.final_device_id,
                    run_id=run_id,
                )
            )
        else:
            reason = result.drop_reason.value if result.drop_reason else "DROPPED"
            if (
                result.drop_reason is not None
                and result.drop_reason.value == "ARP_FAILED"
            ):
                evs.append(
                    self._event(
                        Severity.WARNING,
                        EventCategory.ARP,
                        f"ARP resolution failed for packet {src} → {dst}",
                        result.drop_device_id,
                        run_id=run_id,
                    )
                )
            evs.append(
                self._event(
                    Severity.WARNING,
                    EventCategory.DROP,
                    f"packet {src} → {dst} dropped: {reason}",
                    result.drop_device_id,
                    run_id=run_id,
                    reason=reason,
                )
            )
        stored = self._store(uow, evs)
        return result, stored

    def send_packet(self, req: SendPacketRequest) -> SimulationResultDTO:
        """Simulate one packet (runs in a TUI worker thread)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            result = self._engine(uow, topo).simulate(self._request(uow, req))
            result, events = self._record(uow, topo, result)
            dto = result_dto(topo, result)
        self._publish(events)
        return dto

    def traceroute(self, req: SendPacketRequest) -> TracerouteDTO:
        """Traceroute with increasing TTL (US-SIM-4)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            request = self._request(uow, req)
            trace = self._engine(uow, topo).traceroute(request)
            _final, events = self._record(uow, topo, trace.final)
            dto = TracerouteDTO(
                tuple(
                    TracerouteHopDTO(h.ttl, h.device_name, h.status) for h in trace.hops
                ),
                trace.reached,
                result_dto(topo, trace.final),
            )
        self._publish(events)
        return dto

    def history(self, limit: int = 20) -> list[SimulationSummaryDTO]:
        """Last runs (US-SIM-5)."""
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            runs = uow.simulations.recent(limit)
        summaries = []
        for run in runs:
            dto = result_dto(topo, run)
            summaries.append(
                SimulationSummaryDTO(
                    run.run_id,
                    run.started_at,
                    dto.path_names[0] if dto.path_names else "?",
                    str(run.request.dst_ip) if run.request else "?",
                    run.status,
                    run.drop_reason,
                    len(run.hops),
                )
            )
        return summaries

    def replay(self, run_id: int) -> SimulationResultDTO | None:
        """Stored result of a past run (US-SIM-5)."""
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            runs = uow.simulations.recent(200)
        for run in runs:
            if run.run_id == run_id:
                return result_dto(topo, run)
        return None
