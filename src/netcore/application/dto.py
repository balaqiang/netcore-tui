"""Immutable DTOs exchanged with the TUI.

Domain enums are re-exported here so the TUI never imports the domain.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from netcore.domain.enums import (
    DeviceStatus,
    DeviceType,
    DropReason,
    EventCategory,
    HopKind,
    Protocol,
    RouteType,
    Severity,
    SimulationStatus,
)

__all__ = [
    "AddRouteRequest",
    "AddressDTO",
    "ArpEntryDTO",
    "AssignAddressRequest",
    "ConnectRequest",
    "CreateDeviceRequest",
    "CreateSubnetRequest",
    "DashboardDTO",
    "DeviceDTO",
    "DeviceFilter",
    "DeviceStatsDTO",
    "DeviceStatus",
    "DeviceType",
    "DropReason",
    "EventCategory",
    "EventDTO",
    "EventFilterDTO",
    "ExportResultDTO",
    "FlowDTO",
    "HopDTO",
    "HopKind",
    "InterfaceDTO",
    "LinkDTO",
    "LinkStatsDTO",
    "MacEntryDTO",
    "NodeDTO",
    "Protocol",
    "RemovalReportDTO",
    "RouteDTO",
    "RouteLookupDTO",
    "RouteType",
    "SendPacketRequest",
    "SettingsDTO",
    "Severity",
    "SimulationResultDTO",
    "SimulationStatus",
    "SimulationSummaryDTO",
    "StartFlowRequest",
    "SubnetDTO",
    "SwitchPortDTO",
    "TopologyDTO",
    "TracerouteDTO",
    "TracerouteHopDTO",
    "UpdateDeviceRequest",
    "UpdatePortRequest",
    "UpdateSettingsRequest",
]


# ------------------------------------------------------------------ devices
@dataclass(frozen=True, slots=True)
class InterfaceDTO:
    """Interface view."""

    name: str
    mac: str
    address: str | None
    admin_up: bool
    link_id: int | None
    peer: str | None
    operational: bool


@dataclass(frozen=True, slots=True)
class DeviceDTO:
    """Device row + detail."""

    id: int
    hostname: str
    device_type: DeviceType
    status: DeviceStatus
    location: str
    description: str
    interfaces: tuple[InterfaceDTO, ...]
    default_gateway: str | None = None

    @property
    def interface_count(self) -> int:
        """Number of interfaces."""
        return len(self.interfaces)


@dataclass(frozen=True, slots=True)
class DeviceFilter:
    """Device list filter (US-DEV-5)."""

    text: str = ""
    device_type: DeviceType | None = None
    status: DeviceStatus | None = None


@dataclass(frozen=True, slots=True)
class CreateDeviceRequest:
    """New device form."""

    hostname: str
    device_type: DeviceType
    interface_count: int | None = None
    location: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class UpdateDeviceRequest:
    """Edit device form; ``None`` leaves a field unchanged."""

    device_id: int
    hostname: str | None = None
    location: str | None = None
    description: str | None = None
    default_gateway: str | None = None


@dataclass(frozen=True, slots=True)
class RemovalReportDTO:
    """What deleting a device removed."""

    hostname: str
    removed_links: tuple[str, ...]
    removed_routes: tuple[str, ...]
    released_addresses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArpEntryDTO:
    """ARP cache row."""

    ip: str
    mac: str
    interface: str
    entry_type: str
    expires_in_s: int | None


# --------------------------------------------------------------------- IPAM
@dataclass(frozen=True, slots=True)
class SubnetDTO:
    """Subnet with usage."""

    id: int
    cidr: str
    name: str
    gateway: str | None
    parent_id: int | None
    total: int
    used: int
    free: int
    utilization_pct: float


@dataclass(frozen=True, slots=True)
class AddressDTO:
    """Assigned address in a subnet."""

    ip: str
    prefix: int
    device_id: int
    device_name: str
    interface: str
    mac: str


@dataclass(frozen=True, slots=True)
class CreateSubnetRequest:
    """New subnet form."""

    cidr: str
    name: str = ""
    gateway: str | None = None
    parent_id: int | None = None


@dataclass(frozen=True, slots=True)
class AssignAddressRequest:
    """Assign ``address`` (``a.b.c.d/nn`` or bare IP) to an interface."""

    device_id: int
    interface: str
    address: str


# ------------------------------------------------------------------ routing
@dataclass(frozen=True, slots=True)
class RouteDTO:
    """Routing table row."""

    id: int
    router_id: int
    route_type: RouteType
    destination: str
    next_hop: str | None
    interface: str
    admin_distance: int
    metric: int

    @property
    def removable(self) -> bool:
        """Connected routes are derived and cannot be removed."""
        return self.route_type is not RouteType.CONNECTED

    @property
    def type_code(self) -> str:
        """C / S / D."""
        return self.route_type.value[0]


@dataclass(frozen=True, slots=True)
class AddRouteRequest:
    """New static route form."""

    router_id: int
    destination: str
    next_hop: str
    interface: str | None = None
    metric: int = 0


@dataclass(frozen=True, slots=True)
class RouteLookupDTO:
    """Result of the route lookup tool (US-RT-4)."""

    dst_ip: str
    matched: RouteDTO | None
    message: str


# ---------------------------------------------------------------- switching
@dataclass(frozen=True, slots=True)
class SwitchPortDTO:
    """Switch port view."""

    switch_id: int
    number: int
    admin_up: bool
    speed_mbps: int
    description: str
    peer: str | None
    operational: bool
    tx_packets: int = 0
    rx_packets: int = 0


@dataclass(frozen=True, slots=True)
class UpdatePortRequest:
    """Edit port form."""

    switch_id: int
    port: int
    speed_mbps: int | None = None
    description: str | None = None
    admin_up: bool | None = None


@dataclass(frozen=True, slots=True)
class MacEntryDTO:
    """MAC table row."""

    mac: str
    port: int
    age_s: int


# ----------------------------------------------------------------- topology
@dataclass(frozen=True, slots=True)
class LinkDTO:
    """Link view."""

    id: int
    a_device_id: int
    a_device: str
    a_interface: str
    b_device_id: int
    b_device: str
    b_interface: str
    capacity_mbps: int
    latency_ms: float
    admin_up: bool
    operational: bool

    @property
    def label(self) -> str:
        """``a:if ↔ b:if``."""
        return (
            f"{self.a_device}:{self.a_interface} ↔ {self.b_device}:{self.b_interface}"
        )


@dataclass(frozen=True, slots=True)
class NodeDTO:
    """Topology node."""

    id: int
    hostname: str
    device_type: DeviceType
    status: DeviceStatus


@dataclass(frozen=True, slots=True)
class TopologyDTO:
    """Whole topology for the canvas."""

    nodes: tuple[NodeDTO, ...]
    links: tuple[LinkDTO, ...]
    last_path: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ConnectRequest:
    """New link form."""

    device_a: int
    interface_a: str
    device_b: int
    interface_b: str
    capacity_mbps: int | None = None
    latency_ms: float | None = None


# --------------------------------------------------------------- simulation
@dataclass(frozen=True, slots=True)
class SendPacketRequest:
    """Packet lab form."""

    src_device_id: int
    dst_ip: str
    protocol: Protocol = Protocol.ICMP
    ttl: int | None = None
    size_bytes: int = 64
    payload: str = ""


@dataclass(frozen=True, slots=True)
class HopDTO:
    """One hop in the trace."""

    index: int
    kind: HopKind
    device_id: int
    device_name: str
    device_type: DeviceType
    ingress: str | None
    egress: str | None
    ttl_in: int | None
    ttl_out: int | None
    matched_route: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationResultDTO:
    """Packet simulation outcome."""

    run_id: int
    status: SimulationStatus
    drop_reason: DropReason | None
    hops: tuple[HopDTO, ...]
    path_ids: tuple[int, ...]
    path_names: tuple[str, ...]
    total_latency_ms: float
    ttl_start: int
    ttl_end: int | None
    drop_device: str | None
    summary: str


@dataclass(frozen=True, slots=True)
class TracerouteHopDTO:
    """Traceroute line."""

    ttl: int
    device_name: str
    status: str


@dataclass(frozen=True, slots=True)
class TracerouteDTO:
    """Traceroute outcome."""

    hops: tuple[TracerouteHopDTO, ...]
    reached: bool
    final: SimulationResultDTO


@dataclass(frozen=True, slots=True)
class SimulationSummaryDTO:
    """History row."""

    run_id: int
    started_at: datetime
    src_name: str
    dst_ip: str
    status: SimulationStatus
    drop_reason: DropReason | None
    hop_count: int


# --------------------------------------------------------------- monitoring
@dataclass(frozen=True, slots=True)
class LinkStatsDTO:
    """Per-link simulated stats (capacity vs utilization kept separate)."""

    link_id: int
    label: str
    capacity_mbps: int
    load_mbps: float
    utilization_pct: float
    tx_packets: int
    rx_packets: int
    dropped: int
    admin_up: bool


@dataclass(frozen=True, slots=True)
class DeviceStatsDTO:
    """Per-device simulated counters."""

    device_id: int
    hostname: str
    tx_packets: int
    rx_packets: int
    tx_bytes: int
    rx_bytes: int
    dropped: int
    top_drop_reason: str | None


@dataclass(frozen=True, slots=True)
class FlowDTO:
    """Active (or just started) simulated flow."""

    flow_id: int
    src_name: str
    dst_ip: str
    protocol: Protocol
    packet_size: int
    packets_per_second: int
    duration_s: int
    remaining_s: int
    load_mbps: float
    delivered: bool
    drop_reason: DropReason | None
    congestion_drops: int


@dataclass(frozen=True, slots=True)
class StartFlowRequest:
    """Flow form."""

    src_device_id: int
    dst_ip: str
    protocol: Protocol = Protocol.UDP
    packet_size: int = 512
    packets_per_second: int = 1000
    duration_s: int = 60


@dataclass(frozen=True, slots=True)
class EventDTO:
    """Event log row."""

    id: int
    timestamp: datetime
    severity: Severity
    category: EventCategory
    device_id: int | None
    device_name: str | None
    message: str
    payload: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DashboardDTO:
    """Dashboard summary."""

    lab_name: str
    device_total: int
    online: int
    offline: int
    maintenance: int
    link_total: int
    links_up: int
    links_down: int
    subnet_count: int
    subnet_util_pct: float
    warnings_1h: int
    errors_1h: int
    top_links: tuple[LinkStatsDTO, ...]
    recent_events: tuple[EventDTO, ...]


@dataclass(frozen=True, slots=True)
class EventFilterDTO:
    """Event screen filter; ``window`` is 15m, 1h, 24h or all."""

    severities: frozenset[Severity] | None = None
    category: EventCategory | None = None
    device_id: int | None = None
    text: str = ""
    window: str = "all"
    limit: int = 1000


@dataclass(frozen=True, slots=True)
class ExportResultDTO:
    """Export outcome."""

    path: str
    count: int
    fmt: str


# ----------------------------------------------------------------- settings
@dataclass(frozen=True, slots=True)
class SettingsDTO:
    """Effective settings."""

    default_ttl: int
    default_capacity_mbps: int
    arp_timeout_s: int
    mac_timeout_s: int
    max_hops: int
    event_retention: int
    seed: int
    lab_name: str
    db_path: str
    theme: str = "dark"


@dataclass(frozen=True, slots=True)
class UpdateSettingsRequest:
    """Settings form; ``None`` leaves a field unchanged."""

    default_ttl: int | None = None
    default_capacity_mbps: int | None = None
    arp_timeout_s: int | None = None
    mac_timeout_s: int | None = None
    max_hops: int | None = None
    event_retention: int | None = None
    seed: int | None = None
