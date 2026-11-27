"""Router, RoutingEntry and RoutingTable (NETWORK_SPEC §6)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import TYPE_CHECKING, ClassVar

from netcore.domain.arp import ArpTable
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.l3 import transmit
from netcore.domain.enums import (
    DeviceStatus,
    DeviceType,
    DropReason,
    HopKind,
    RouteType,
)
from netcore.domain.errors import (
    DuplicateRouteError,
    InvalidNextHopError,
    InvalidValueError,
    RouteNotFoundError,
)
from netcore.domain.ids import DeviceId
from netcore.domain.interface import NetworkInterface
from netcore.domain.packet import Packet
from netcore.domain.simulation.context import ForwardDecision

if TYPE_CHECKING:
    from netcore.domain.packet import Frame
    from netcore.domain.simulation.context import ForwardingContext

DEFAULT_NETWORK = IPv4Network("0.0.0.0/0")
CONNECTED_AD = 0
STATIC_AD = 1
MAX_METRIC = 65535


@dataclass(frozen=True, slots=True)
class RoutingEntry:
    """One routing table row."""

    id: int
    destination: IPv4Network
    next_hop: IPv4Address | None
    interface: str
    route_type: RouteType
    admin_distance: int
    metric: int = 0
    insertion_index: int = 0

    def describe(self) -> str:
        """Human-readable form, e.g. ``10.1.0.0/16 via 10.0.0.3 ge0/1``."""
        if self.next_hop is None:
            return f"{self.destination} connected {self.interface}"
        return f"{self.destination} via {self.next_hop} {self.interface}"


class RoutingTable:
    """Connected + static routes with integer longest prefix match."""

    def __init__(self) -> None:
        self._entries: list[RoutingEntry] = []
        self._next_id = 1
        self._next_index = 1

    def entries(self) -> tuple[RoutingEntry, ...]:
        """Entries sorted for display (prefix desc, then AD, metric)."""
        return tuple(
            sorted(
                self._entries,
                key=lambda e: (
                    -e.destination.prefixlen,
                    int(e.destination.network_address),
                    e.admin_distance,
                    e.metric,
                    e.insertion_index,
                ),
            )
        )

    def static_entries(self) -> tuple[RoutingEntry, ...]:
        """Static/default routes in insertion order."""
        return tuple(
            sorted(
                (e for e in self._entries if e.route_type is not RouteType.CONNECTED),
                key=lambda e: e.insertion_index,
            )
        )

    def get(self, entry_id: int) -> RoutingEntry:
        """Entry by id."""
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        raise RouteNotFoundError(f"Route {entry_id} not found.")

    def add(self, entry: RoutingEntry) -> RoutingEntry:
        """Add a static/default entry; assigns id/index when they are ≤ 0."""
        if not 0 <= entry.metric <= MAX_METRIC:
            raise InvalidValueError(f"Metric {entry.metric} must be 0-65535.")
        for existing in self._entries:
            if (
                existing.destination == entry.destination
                and existing.next_hop == entry.next_hop
            ):
                via = entry.next_hop if entry.next_hop else "connected"
                raise DuplicateRouteError(
                    f"Route {entry.destination} via {via} already exists."
                )
        entry_id = entry.id if entry.id > 0 else self._next_id
        index = entry.insertion_index if entry.insertion_index > 0 else self._next_index
        stored = RoutingEntry(
            entry_id,
            entry.destination,
            entry.next_hop,
            entry.interface,
            entry.route_type,
            entry.admin_distance,
            entry.metric,
            index,
        )
        self._entries.append(stored)
        self._next_id = max(self._next_id, entry_id + 1)
        self._next_index = max(self._next_index, index + 1)
        return stored

    def remove(self, entry_id: int) -> RoutingEntry:
        """Remove a static/default entry (connected routes are derived)."""
        entry = self.get(entry_id)
        if entry.route_type is RouteType.CONNECTED:
            raise RouteNotFoundError(
                f"Connected route {entry.destination} cannot be removed; "
                "release the interface address instead."
            )
        self._entries.remove(entry)
        return entry

    def sync_connected(self, interfaces: Iterable[NetworkInterface]) -> None:
        """Regenerate connected routes from interface addresses."""
        self._entries = [
            e for e in self._entries if e.route_type is not RouteType.CONNECTED
        ]
        for idx, iface in enumerate(interfaces, start=1):
            if iface.address is None:
                continue
            self._entries.append(
                RoutingEntry(
                    -idx,
                    iface.address.network,
                    None,
                    iface.name,
                    RouteType.CONNECTED,
                    CONNECTED_AD,
                    0,
                    -idx,
                )
            )

    def longest_prefix_match(self, dst: IPv4Address) -> RoutingEntry | None:
        """NETWORK_SPEC §6.2 — integer LPM with AD/metric/order tie-breaks."""
        candidates = [e for e in self._entries if dst in e.destination]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda e: (
                e.destination.prefixlen,
                -e.admin_distance,
                -e.metric,
                -e.insertion_index,
            ),
        )


class Router(NetworkDevice):
    """L3 router: decrements TTL and forwards by routing table."""

    device_type: ClassVar[DeviceType] = DeviceType.ROUTER
    MIN_INTERFACES: ClassVar[int] = 1
    MAX_INTERFACES: ClassVar[int] = 16
    DEFAULT_INTERFACES: ClassVar[int] = 4

    def __init__(
        self,
        device_id: DeviceId,
        hostname: str,
        interfaces: Iterable[NetworkInterface],
        status: DeviceStatus = DeviceStatus.ONLINE,
        location: str = "",
        description: str = "",
    ) -> None:
        super().__init__(device_id, hostname, interfaces, status, location, description)
        self.routing_table = RoutingTable()
        self.arp_table = ArpTable()
        self.routing_table.sync_connected(self.interfaces())

    def arp_cache(self) -> ArpTable:
        """Router ARP table."""
        return self.arp_table

    def on_address_changed(self) -> None:
        """Keep connected routes in sync with addresses (US-RT-2)."""
        self.routing_table.sync_connected(self.interfaces())

    def connected_interface_for(self, ip: IPv4Address) -> NetworkInterface | None:
        """Interface whose connected subnet contains ``ip``."""
        best: NetworkInterface | None = None
        for iface in self.addressed_interfaces():
            assert iface.address is not None
            if ip in iface.address.network and (
                best is None
                or best.address is None
                or iface.address.network.prefixlen > best.address.network.prefixlen
            ):
                best = iface
        return best

    def add_static_route(self, entry: RoutingEntry) -> RoutingEntry:
        """Validate (§6.1) and add a static/default route."""
        if entry.next_hop is None:
            raise InvalidNextHopError("Static routes require a next hop.")
        iface = self.get_interface(entry.interface)
        connected = self.connected_interface_for(entry.next_hop)
        if connected is None:
            raise InvalidNextHopError(
                f"Next hop {entry.next_hop} is not on a connected subnet of "
                f"{self.hostname}."
            )
        if connected.name != iface.name:
            raise InvalidNextHopError(
                f"Next hop {entry.next_hop} is reachable via {connected.name}, "
                f"not {iface.name}."
            )
        if self.owns_ip(entry.next_hop):
            raise InvalidNextHopError(
                f"Next hop {entry.next_hop} is an address of {self.hostname} itself."
            )
        route_type = (
            RouteType.DEFAULT
            if entry.destination == DEFAULT_NETWORK
            else RouteType.STATIC
        )
        return self.routing_table.add(
            RoutingEntry(
                entry.id,
                entry.destination,
                entry.next_hop,
                entry.interface,
                route_type,
                STATIC_AD,
                entry.metric,
                entry.insertion_index,
            )
        )

    def remove_route(self, entry_id: int) -> RoutingEntry:
        """Remove a static/default route by id."""
        return self.routing_table.remove(entry_id)

    def lookup(self, dst: IPv4Address) -> RoutingEntry | None:
        """Longest prefix match."""
        return self.routing_table.longest_prefix_match(dst)

    def _route_and_send(
        self,
        packet: Packet,
        ctx: ForwardingContext,
        ingress: str | None,
        ttl_in: int,
    ) -> ForwardDecision:
        route = self.lookup(packet.dst_ip)
        if route is None:
            ctx.hop(
                self,
                HopKind.DROP,
                f"no route to {packet.dst_ip} and no default route",
                ingress=ingress,
                ttl_in=ttl_in,
            )
            return ForwardDecision.drop(DropReason.NO_ROUTE)
        next_hop = route.next_hop or packet.dst_ip
        kind = HopKind.ROUTE if ingress is not None else HopKind.SEND
        prefix = f"LPM /{route.destination.prefixlen}: "
        ctx.hop(
            self,
            kind,
            prefix
            + (
                f"via {route.next_hop}"
                if route.next_hop
                else f"{route.destination} directly connected"
            )
            + f" out {route.interface}",
            ingress=ingress,
            egress=route.interface,
            ttl_in=ttl_in,
            ttl_out=packet.ttl,
            matched_route=route.describe(),
        )
        return transmit(self, packet, route.interface, next_hop, ctx)

    def originate(self, packet: Packet, ctx: ForwardingContext) -> ForwardDecision:
        """Router-originated packet: no TTL decrement at the source."""
        if self.owns_ip(packet.dst_ip):
            ctx.hop(self, HopKind.DELIVER, "destination is local", ttl_in=packet.ttl)
            return ForwardDecision.deliver()
        return self._route_and_send(packet, ctx, None, packet.ttl)

    def receive(
        self, frame: Frame, ingress: str, ctx: ForwardingContext
    ) -> ForwardDecision:
        """NETWORK_SPEC §6.3."""
        packet = frame.payload
        if not isinstance(packet, Packet):
            return ForwardDecision.drop(DropReason.NOT_FOR_ME)
        if not self.is_online():
            ctx.hop(
                self,
                HopKind.DROP,
                f"{self.hostname} is {self.status.value.lower()}",
                ingress=ingress,
                ttl_in=packet.ttl,
            )
            return ForwardDecision.drop(DropReason.DEVICE_OFFLINE)
        if not self.get_interface(ingress).admin_up:
            ctx.hop(
                self,
                HopKind.DROP,
                f"ingress {ingress} is admin down",
                ingress=ingress,
                ttl_in=packet.ttl,
            )
            return ForwardDecision.drop(DropReason.INTERFACE_DOWN)
        if self.owns_ip(packet.dst_ip):
            ctx.hop(
                self,
                HopKind.DELIVER,
                f"{packet.dst_ip} is an address of {self.hostname}",
                ingress=ingress,
                ttl_in=packet.ttl,
            )
            return ForwardDecision.deliver()
        ttl_out = packet.ttl - 1
        if ttl_out <= 0:
            ctx.hop(
                self,
                HopKind.DROP,
                f"TTL reached 0 at {self.hostname} (ICMP time-exceeded would be sent)",
                ingress=ingress,
                ttl_in=packet.ttl,
                ttl_out=0,
            )
            return ForwardDecision.drop(DropReason.TTL_EXPIRED)
        return self._route_and_send(packet.with_ttl(ttl_out), ctx, ingress, packet.ttl)
