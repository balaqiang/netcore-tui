"""Simulation request/result value objects (NETWORK_SPEC §9.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from ipaddress import IPv4Address

from netcore.domain.enums import (
    DeviceType,
    DropReason,
    HopKind,
    Protocol,
    SimulationStatus,
)
from netcore.domain.ids import DeviceId, LinkId


@dataclass(frozen=True, slots=True)
class PacketRequest:
    """Input to ``ForwardingEngine.simulate``."""

    src_device_id: DeviceId
    dst_ip: IPv4Address
    protocol: Protocol = Protocol.ICMP
    ttl: int = 64
    size_bytes: int = 64
    payload: str = ""


@dataclass(frozen=True, slots=True)
class HopRecord:
    """One explained decision in the trace."""

    index: int
    device_id: DeviceId
    device_name: str
    device_type: DeviceType
    kind: HopKind
    ingress: str | None = None
    egress: str | None = None
    ttl_in: int | None = None
    ttl_out: int | None = None
    matched_route: str | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class LinkTraversal:
    """A frame crossing a link from one device to another."""

    link_id: LinkId
    from_device: DeviceId
    to_device: DeviceId
    a_to_b: bool


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Outcome of one simulated packet."""

    run_id: int
    status: SimulationStatus
    drop_reason: DropReason | None
    hops: tuple[HopRecord, ...]
    path: tuple[DeviceId, ...]
    total_latency_ms: float
    started_at: datetime
    seed: int
    traversals: tuple[LinkTraversal, ...] = field(default=())
    arp_exchanges: int = 0
    drop_device_id: DeviceId | None = None
    final_device_id: DeviceId | None = None
    request: PacketRequest | None = None

    @property
    def delivered(self) -> bool:
        """True if the packet reached its destination."""
        return self.status is SimulationStatus.DELIVERED


@dataclass(frozen=True, slots=True)
class TracerouteHop:
    """One line of traceroute output."""

    ttl: int
    device_id: DeviceId | None
    device_name: str
    status: str


@dataclass(frozen=True, slots=True)
class TracerouteResult:
    """Traceroute output (NETWORK_SPEC §9.2)."""

    hops: tuple[TracerouteHop, ...]
    reached: bool
    final: SimulationResult
