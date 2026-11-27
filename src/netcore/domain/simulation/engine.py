"""ForwardingEngine — single packet and traceroute (NETWORK_SPEC §9)."""

from __future__ import annotations

import random
from datetime import datetime

from netcore.domain.devices.router import Router
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch
from netcore.domain.enums import (
    DropReason,
    ForwardAction,
    HopKind,
    SimulationStatus,
)
from netcore.domain.errors import InvalidSourceError
from netcore.domain.ids import DeviceId
from netcore.domain.interface import InterfaceRef
from netcore.domain.logging_mixin import LoggerMixin
from netcore.domain.packet import Packet
from netcore.domain.simulation.constants import (
    ROUTER_PROCESSING_MS,
    SWITCH_PROCESSING_MS,
    SimulationSettings,
)
from netcore.domain.simulation.context import ForwardDecision, ForwardingContext
from netcore.domain.simulation.result import (
    LinkTraversal,
    PacketRequest,
    SimulationResult,
    TracerouteHop,
    TracerouteResult,
)
from netcore.domain.topology import NetworkTopology


class ForwardingEngine(LoggerMixin):
    """Deterministic hop-by-hop packet simulator."""

    def __init__(
        self,
        topology: NetworkTopology,
        settings: SimulationSettings,
        rng: random.Random,
        clock_start: datetime,
        seed: int = 0,
    ) -> None:
        self._topology = topology
        self._settings = settings
        self._rng = rng
        self._clock_start = clock_start
        self._seed = seed
        self._run_counter = 0
        self._packet_counter = 0

    def _validate_source(self, request: PacketRequest) -> None:
        device = self._topology.get_device(request.src_device_id)
        if not isinstance(device, (Router, Server)):
            raise InvalidSourceError(
                f"Source {device.hostname} must be a server or router."
            )
        if not device.is_online():
            raise InvalidSourceError(f"Source {device.hostname} is offline.")
        if not device.addressed_interfaces():
            raise InvalidSourceError(
                f"Source {device.hostname} has no addressed interface."
            )

    def simulate(self, request: PacketRequest) -> SimulationResult:
        """Simulate one packet from ``request.src_device_id`` to ``dst_ip``."""
        self._validate_source(request)
        topo = self._topology
        src = topo.get_device(request.src_device_id)
        self._run_counter += 1
        self._packet_counter += 1
        src_iface = src.addressed_interfaces()[0]
        assert src_iface.address is not None
        egress_hint = src.interface_for_ip(request.dst_ip)
        src_ip = src_iface.address.ip if egress_hint is None else request.dst_ip
        if isinstance(src, Server):
            for iface in src.addressed_interfaces():
                assert iface.address is not None
                if request.dst_ip in iface.address.network or (
                    src.default_gateway is not None
                    and src.default_gateway in iface.address.network
                ):
                    src_ip = iface.address.ip
                    break
        packet = Packet(
            self._packet_counter,
            src_ip,
            request.dst_ip,
            request.protocol,
            request.ttl,
            request.size_bytes,
            request.payload,
        )
        ctx = ForwardingContext(topo, self._clock_start, self._settings)
        path: list[DeviceId] = [src.id]
        traversals: list[LinkTraversal] = []
        latency = 0.0
        visits = 0
        visited_floods: set[tuple[DeviceId, int]] = set()
        current = src
        decision = src.originate(packet, ctx)
        status = SimulationStatus.DROPPED
        reason: DropReason | None = None
        while True:
            if decision.action is ForwardAction.DELIVER:
                status = SimulationStatus.DELIVERED
                break
            if decision.action is ForwardAction.DROP:
                reason = decision.drop_reason or DropReason.NO_ROUTE
                break
            frame = decision.frame
            assert frame is not None
            if decision.action is ForwardAction.FLOOD:
                key = (current.id, frame.frame_id)
                egress = self._choose_flood_branch(current.id, decision)
                if egress is None or key in visited_floods:
                    ctx.hop(
                        current,
                        HopKind.DROP,
                        f"flooded frame for {frame.dst_mac} reached no owner",
                    )
                    reason = DropReason.LINK_DOWN
                    break
                visited_floods.add(key)
            else:
                egress = decision.egress[0]
            out_ref = InterfaceRef(current.id, egress)
            link = topo.link_for(out_ref)
            assert link is not None
            in_ref = link.peer_of(out_ref)
            traversals.append(
                LinkTraversal(
                    link.id, current.id, in_ref.device_id, link.endpoint_a == out_ref
                )
            )
            latency += link.latency_ms
            visits += 1
            nxt = topo.get_device(in_ref.device_id)
            if visits > self._settings.max_hops:
                ctx.hop(
                    nxt,
                    HopKind.DROP,
                    f"hop limit {self._settings.max_hops} exceeded (loop guard)",
                    ingress=in_ref.interface,
                )
                reason = DropReason.HOP_LIMIT
                path.append(nxt.id)
                current = nxt
                break
            path.append(nxt.id)
            hops_before = len(ctx.hops)
            decision = nxt.receive(frame, in_ref.interface, ctx)
            if isinstance(nxt, Switch):
                latency += SWITCH_PROCESSING_MS
            elif isinstance(nxt, Router) and any(
                h.kind is HopKind.ROUTE for h in ctx.hops[hops_before:]
            ):
                latency += ROUTER_PROCESSING_MS
            current = nxt
        return SimulationResult(
            run_id=self._run_counter,
            status=status,
            drop_reason=reason,
            hops=tuple(ctx.hops),
            path=tuple(path),
            total_latency_ms=round(latency, 3),
            started_at=self._clock_start,
            seed=self._seed,
            traversals=tuple(traversals),
            arp_exchanges=ctx.arp_exchanges,
            drop_device_id=current.id if reason is not None else None,
            final_device_id=current.id,
            request=request,
        )

    def _choose_flood_branch(
        self, switch_id: DeviceId, decision: ForwardDecision
    ) -> str | None:
        """Follow only the flood copy that leads to the dst MAC owner (§8.3)."""
        frame = decision.frame
        assert frame is not None
        for port in decision.egress:
            path = self._topology.l2_path_to_mac(
                InterfaceRef(switch_id, port), frame.dst_mac
            )
            if path is not None:
                return port
        return None

    def traceroute(self, request: PacketRequest) -> TracerouteResult:
        """Repeat ``simulate`` with TTL 1, 2, … (NETWORK_SPEC §9.2)."""
        hops: list[TracerouteHop] = []
        last: SimulationResult | None = None
        for ttl in range(1, self._settings.max_hops + 1):
            probe = PacketRequest(
                request.src_device_id,
                request.dst_ip,
                request.protocol,
                ttl,
                request.size_bytes,
                request.payload,
            )
            last = self.simulate(probe)
            dev_id = last.final_device_id
            name = self._topology.get_device(dev_id).hostname if dev_id else "*"
            if last.delivered:
                hops.append(TracerouteHop(ttl, dev_id, name, "DELIVERED"))
                return TracerouteResult(tuple(hops), True, last)
            if last.drop_reason is DropReason.TTL_EXPIRED:
                hops.append(TracerouteHop(ttl, dev_id, name, "TTL_EXPIRED"))
                continue
            reason = last.drop_reason.value if last.drop_reason else "DROPPED"
            hops.append(TracerouteHop(ttl, None, "*", reason))
            return TracerouteResult(tuple(hops), False, last)
        assert last is not None
        return TracerouteResult(tuple(hops), False, last)
