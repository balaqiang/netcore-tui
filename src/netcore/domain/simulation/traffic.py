"""Traffic flows, counters and utilization (NETWORK_SPEC §10)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Address

from netcore.domain.enums import (
    Direction,
    DropReason,
    EventCategory,
    Protocol,
    Severity,
)
from netcore.domain.errors import InvalidValueError
from netcore.domain.events import TrafficEvent
from netcore.domain.ids import DeviceId, LinkId
from netcore.domain.link import Link
from netcore.domain.simulation.constants import (
    ARP_FRAME_BYTES,
    ARP_FRAMES_PER_EXCHANGE,
)
from netcore.domain.simulation.engine import ForwardingEngine
from netcore.domain.simulation.result import PacketRequest, SimulationResult
from netcore.domain.topology import NetworkTopology

MIN_PPS = 1
MAX_PPS = 100_000
MIN_DURATION = 1
MAX_DURATION = 3600


@dataclass(frozen=True, slots=True)
class TrafficFlow:
    """A simulated constant-rate flow."""

    src_device_id: DeviceId
    dst_ip: IPv4Address
    protocol: Protocol = Protocol.UDP
    packet_size: int = 512
    packets_per_second: int = 1000
    duration_s: int = 60
    seed: int = 0

    def __post_init__(self) -> None:
        if not MIN_PPS <= self.packets_per_second <= MAX_PPS:
            raise InvalidValueError("Packets per second must be 1-100000.")
        if not MIN_DURATION <= self.duration_s <= MAX_DURATION:
            raise InvalidValueError("Duration must be 1-3600 seconds.")
        if not 64 <= self.packet_size <= 9000:
            raise InvalidValueError("Packet size must be 64-9000 bytes.")

    @property
    def load_mbps(self) -> float:
        """Offered load ``pps x size x 8 / 1e6``."""
        return self.packets_per_second * self.packet_size * 8 / 1_000_000

    @property
    def total_packets(self) -> int:
        """``pps x duration``."""
        return self.packets_per_second * self.duration_s


LinkDirKey = tuple[LinkId, Direction]


@dataclass(frozen=True, slots=True)
class FlowReport:
    """Result of starting a flow."""

    flow: TrafficFlow
    probe: SimulationResult
    link_directions: tuple[LinkDirKey, ...]
    delivered_packets: int
    dropped_packets: int
    congestion_drops: int
    events: tuple[TrafficEvent, ...]


def utilization_pct(load_mbps: float, capacity_mbps: int) -> float:
    """``min(100, load / capacity x 100)`` rounded to 1 decimal."""
    if capacity_mbps <= 0:
        return 0.0
    return round(min(100.0, load_mbps / capacity_mbps * 100), 1)


def link_direction(a_to_b: bool) -> Direction:
    """Direction enum for a traversal."""
    return Direction.A_TO_B if a_to_b else Direction.B_TO_A


def counter_events(
    result: SimulationResult,
    packets: int,
    size_bytes: int,
    now: datetime,
    dropped_override: int | None = None,
    drop_reason: DropReason | None = None,
) -> list[TrafficEvent]:
    """Counter deltas for ``packets`` copies following ``result``'s path."""
    events: list[TrafficEvent] = []
    nbytes = packets * size_bytes

    def ev(
        *,
        device_id: DeviceId | None = None,
        link_id: LinkId | None = None,
        direction: Direction,
        count: int = 0,
        size: int = 0,
        dropped: int = 0,
        reason: DropReason | None = None,
    ) -> TrafficEvent:
        return TrafficEvent(
            timestamp=now,
            severity=Severity.WARNING if reason else Severity.DEBUG,
            category=EventCategory.TRAFFIC,
            message="counter update (simulated)",
            device_id=device_id,
            link_id=link_id,
            direction=direction,
            packets=count,
            bytes=size,
            dropped=dropped,
            drop_reason=reason,
        )

    for trav in result.traversals:
        dir_ = link_direction(trav.a_to_b)
        events.append(
            ev(link_id=trav.link_id, direction=dir_, count=packets, size=nbytes)
        )
        events.append(
            ev(
                device_id=trav.from_device,
                direction=Direction.TX,
                count=packets,
                size=nbytes,
            )
        )
        events.append(
            ev(
                device_id=trav.to_device,
                direction=Direction.RX,
                count=packets,
                size=nbytes,
            )
        )
    if result.arp_exchanges and result.path:
        frames = result.arp_exchanges * ARP_FRAMES_PER_EXCHANGE
        events.append(
            ev(
                device_id=result.path[0],
                direction=Direction.TX,
                count=frames,
                size=frames * ARP_FRAME_BYTES,
            )
        )
    if dropped_override is not None:
        dropped = dropped_override
    else:
        dropped = 0 if result.delivered else packets
    reason = drop_reason or result.drop_reason
    drop_device = result.drop_device_id
    if drop_device is None and result.path:
        drop_device = result.path[0]
    if dropped and drop_device is not None:
        events.append(
            ev(
                device_id=drop_device,
                direction=Direction.RX,
                dropped=dropped,
                reason=reason,
            )
        )
    return events


class TrafficGenerator:
    """Accounts flows on the path of one representative packet."""

    def run(
        self,
        flow: TrafficFlow,
        topology: NetworkTopology,
        engine: ForwardingEngine,
        now: datetime,
        existing_load: dict[LinkDirKey, float] | None = None,
    ) -> FlowReport:
        """Simulate one probe, then account ``pps x duration`` packets."""
        probe = engine.simulate(
            PacketRequest(
                flow.src_device_id,
                flow.dst_ip,
                flow.protocol,
                64,
                flow.packet_size,
                "flow",
            )
        )
        total = flow.total_packets
        keys = tuple((t.link_id, link_direction(t.a_to_b)) for t in probe.traversals)
        if not probe.delivered:
            events = counter_events(probe, total, flow.packet_size, now)
            return FlowReport(flow, probe, keys, 0, total, 0, tuple(events))
        load = dict(existing_load or {})
        worst_excess = 0.0
        for key in keys:
            new_load = load.get(key, 0.0) + flow.load_mbps
            capacity = topology.get_link(key[0]).capacity_mbps
            if new_load > capacity:
                excess = (new_load - capacity) / new_load
                worst_excess = max(worst_excess, excess)
        congestion = round(total * worst_excess)
        events = counter_events(
            probe,
            total - congestion,
            flow.packet_size,
            now,
            dropped_override=congestion,
            drop_reason=DropReason.CONGESTION if congestion else None,
        )
        return FlowReport(
            flow, probe, keys, total - congestion, congestion, congestion, tuple(events)
        )

    def utilization(self, link: Link, active_flows: Iterable[FlowReport]) -> float:
        """Utilization % of ``link`` (max of both directions) from active flows."""
        loads = {Direction.A_TO_B: 0.0, Direction.B_TO_A: 0.0}
        for report in active_flows:
            if not report.probe.delivered:
                continue
            for link_id, direction in report.link_directions:
                if link_id == link.id:
                    loads[direction] += report.flow.load_mbps
        return utilization_pct(max(loads.values()), link.capacity_mbps)

    def load_by_direction(
        self, active_flows: Iterable[FlowReport]
    ) -> dict[LinkDirKey, float]:
        """Summed offered load per link direction."""
        loads: dict[LinkDirKey, float] = {}
        for report in active_flows:
            if not report.probe.delivered:
                continue
            for key in report.link_directions:
                loads[key] = loads.get(key, 0.0) + report.flow.load_mbps
        return loads
