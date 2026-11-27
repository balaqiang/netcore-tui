"""NetworkTopology aggregate root (DEC-008)."""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Address, IPv4Interface

from netcore.domain.addressing import MacAddress, MacGenerator
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.router import Router
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch, port_name
from netcore.domain.enums import DeviceType, DropReason
from netcore.domain.errors import (
    AddressNotInSubnetError,
    DeviceNotFoundError,
    DuplicateAddressError,
    DuplicateHostnameError,
    DuplicateMacError,
    InterfaceInUseError,
    InvalidAddressError,
    InvalidLinkError,
    InvalidSubnetError,
    LinkNotFoundError,
    OverlappingSubnetError,
    SubnetInUseError,
    SubnetNotFoundError,
)
from netcore.domain.ids import DeviceId, LinkId, SubnetId
from netcore.domain.interface import InterfaceRef, NetworkInterface
from netcore.domain.link import DEFAULT_CAPACITY_MBPS, DEFAULT_LATENCY_MS, Link
from netcore.domain.logging_mixin import LoggerMixin
from netcore.domain.subnet import Subnet

L2Path = list[tuple[InterfaceRef, InterfaceRef]]


@dataclass(frozen=True, slots=True)
class RemovalReport:
    """What was cleaned up when a device was removed (FR-DEV-04)."""

    device_id: DeviceId
    hostname: str
    removed_links: tuple[LinkId, ...]
    removed_routes: tuple[str, ...]
    released_addresses: tuple[str, ...]


class NetworkTopology(LoggerMixin):
    """Owns devices, links and subnets; enforces lab-wide invariants."""

    def __init__(self) -> None:
        self._devices: dict[DeviceId, NetworkDevice] = {}
        self._links: dict[LinkId, Link] = {}
        self._subnets: dict[SubnetId, Subnet] = {}
        self._link_by_ref: dict[InterfaceRef, LinkId] = {}

    # ------------------------------------------------------------ identity
    def next_device_id(self) -> DeviceId:
        """Next free device id."""
        return DeviceId(max(self._devices, default=0) + 1)

    def next_link_id(self) -> LinkId:
        """Next free link id."""
        return LinkId(max(self._links, default=0) + 1)

    def next_subnet_id(self) -> SubnetId:
        """Next free subnet id."""
        return SubnetId(max(self._subnets, default=0) + 1)

    def all_macs(self) -> set[MacAddress]:
        """Every MAC in the lab."""
        return {i.mac for d in self._devices.values() for i in d.interfaces()}

    def generate_macs(self, rng: random.Random, count: int) -> list[MacAddress]:
        """``count`` new unique MACs (deterministic for a seeded ``rng``)."""
        gen = MacGenerator(rng)
        taken = self.all_macs()
        result: list[MacAddress] = []
        for _ in range(count):
            mac = gen.generate(taken)
            taken.add(mac)
            result.append(mac)
        return result

    # ------------------------------------------------------------- devices
    def devices(self) -> tuple[NetworkDevice, ...]:
        """All devices ordered by id."""
        return tuple(self._devices[k] for k in sorted(self._devices))

    def get_device(self, device_id: DeviceId) -> NetworkDevice:
        """Device by id or ``DeviceNotFoundError``."""
        try:
            return self._devices[device_id]
        except KeyError:
            raise DeviceNotFoundError(f"Device {device_id} not found.") from None

    def find_by_hostname(self, name: str) -> NetworkDevice | None:
        """Case-insensitive hostname lookup."""
        key = name.lower()
        for device in self._devices.values():
            if device.hostname.lower() == key:
                return device
        return None

    def require(self, name: str) -> NetworkDevice:
        """Device by hostname or ``DeviceNotFoundError``."""
        device = self.find_by_hostname(name)
        if device is None:
            raise DeviceNotFoundError(f'Device "{name}" not found.')
        return device

    def get_router(self, device_id: DeviceId) -> Router:
        """Device that must be a router."""
        device = self.get_device(device_id)
        if not isinstance(device, Router):
            raise DeviceNotFoundError(f"Device {device.hostname} is not a router.")
        return device

    def get_switch(self, device_id: DeviceId) -> Switch:
        """Device that must be a switch."""
        device = self.get_device(device_id)
        if not isinstance(device, Switch):
            raise DeviceNotFoundError(f"Device {device.hostname} is not a switch.")
        return device

    def get_server(self, device_id: DeviceId) -> Server:
        """Device that must be a server."""
        device = self.get_device(device_id)
        if not isinstance(device, Server):
            raise DeviceNotFoundError(f"Device {device.hostname} is not a server.")
        return device

    def _owner_of_mac(self, mac: MacAddress) -> tuple[NetworkDevice, str] | None:
        for device in self._devices.values():
            for iface in device.interfaces():
                if iface.mac == mac:
                    return device, iface.name
        return None

    def _owner_of_ip(self, ip: IPv4Address) -> tuple[NetworkDevice, str] | None:
        for device in self._devices.values():
            iface = device.interface_for_ip(ip)
            if iface is not None:
                return device, iface.name
        return None

    def add_device(self, device: NetworkDevice) -> None:
        """Add a device after checking hostname/MAC/IP uniqueness."""
        if device.id in self._devices:
            raise DuplicateHostnameError(f"Device id {device.id} already exists.")
        if self.find_by_hostname(device.hostname) is not None:
            raise DuplicateHostnameError(
                f'Hostname "{device.hostname}" already exists.'
            )
        mac_owners = {
            i.mac: (d, i.name) for d in self._devices.values() for i in d.interfaces()
        }
        seen: set[MacAddress] = set()
        for iface in device.interfaces():
            owner = mac_owners.get(iface.mac)
            if owner is not None:
                raise DuplicateMacError(
                    f"{iface.mac} is already used by {owner[0].hostname} {owner[1]}."
                )
            if iface.mac in seen:
                raise DuplicateMacError(
                    f"{iface.mac} is used twice on {device.hostname}."
                )
            seen.add(iface.mac)
            if iface.address is not None:
                ip_owner = self._owner_of_ip(iface.address.ip)
                if ip_owner is not None:
                    raise DuplicateAddressError(
                        f"{iface.address.ip} is already assigned to "
                        f"{ip_owner[0].hostname} {ip_owner[1]}."
                    )
        self._devices[device.id] = device
        device.on_address_changed()

    def rename_device(self, device_id: DeviceId, hostname: str) -> None:
        """Rename keeping hostname uniqueness."""
        device = self.get_device(device_id)
        other = self.find_by_hostname(hostname)
        if other is not None and other.id != device_id:
            raise DuplicateHostnameError(f'Hostname "{hostname}" already exists.')
        device.rename(hostname)

    def remove_device(self, device_id: DeviceId) -> RemovalReport:
        """Remove a device and everything that references it."""
        device = self.get_device(device_id)
        links = tuple(link.id for link in self.links() if link.involves(device_id))
        for link_id in links:
            self.disconnect(link_id)
        own_ips = {i.address.ip for i in device.addressed_interfaces() if i.address}
        released = tuple(
            f"{i.address} ({i.name})" for i in device.addressed_interfaces()
        )
        routes: list[str] = []
        for other in self._devices.values():
            if other.id == device_id:
                continue
            if isinstance(other, Router):
                for entry in other.routing_table.static_entries():
                    if entry.next_hop in own_ips:
                        other.remove_route(entry.id)
                        routes.append(f"{other.hostname}: {entry.describe()}")
            elif isinstance(other, Server) and other.default_gateway in own_ips:
                routes.append(
                    f"{other.hostname}: default gateway {other.default_gateway}"
                )
                other.restore_gateway(None)
        del self._devices[device_id]
        return RemovalReport(device_id, device.hostname, links, tuple(routes), released)

    # ------------------------------------------------------------- subnets
    def subnets(self) -> tuple[Subnet, ...]:
        """All subnets ordered by network address."""
        return tuple(
            sorted(
                self._subnets.values(),
                key=lambda s: (int(s.network.network_address), s.network.prefixlen),
            )
        )

    def get_subnet(self, subnet_id: SubnetId) -> Subnet:
        """Subnet by id."""
        try:
            return self._subnets[subnet_id]
        except KeyError:
            raise SubnetNotFoundError(f"Subnet {subnet_id} not found.") from None

    def add_subnet(self, subnet: Subnet) -> Subnet:
        """Add a subnet; overlap only allowed with a declared parent."""
        if subnet.parent_id is not None:
            parent = self.get_subnet(subnet.parent_id)
            if not subnet.network.subnet_of(parent.network) or (
                subnet.network == parent.network
            ):
                raise InvalidSubnetError(
                    f"{subnet.network} is not inside parent {parent.network}."
                )
        for existing in self._subnets.values():
            if existing.id == subnet.id:
                raise OverlappingSubnetError(f"Subnet id {subnet.id} already exists.")
            if not subnet.network.overlaps(existing.network):
                continue
            allowed = self._is_ancestor(existing.id, subnet) or (
                existing.parent_id is not None
                and self._chain_contains(existing, subnet.id)
            )
            if not allowed:
                raise OverlappingSubnetError(
                    f"{subnet.network} overlaps {existing.network}."
                )
        self._subnets[subnet.id] = subnet
        return subnet

    def _is_ancestor(self, candidate: SubnetId, subnet: Subnet) -> bool:
        current = subnet.parent_id
        while current is not None:
            if current == candidate:
                return True
            current = self._subnets[current].parent_id
        return False

    def _chain_contains(self, subnet: Subnet, target: SubnetId) -> bool:
        return self._is_ancestor(target, subnet)

    def remove_subnet(self, subnet_id: SubnetId) -> Subnet:
        """Remove an unused subnet without children."""
        subnet = self.get_subnet(subnet_id)
        used = self.addresses_in(subnet)
        if used:
            raise SubnetInUseError(
                f"Subnet {subnet.network} still has {len(used)} assigned address(es)."
            )
        if any(s.parent_id == subnet_id for s in self._subnets.values()):
            raise SubnetInUseError(f"Subnet {subnet.network} has child subnets.")
        del self._subnets[subnet_id]
        return subnet

    def subnet_for(self, ip: IPv4Address) -> Subnet | None:
        """Most specific subnet containing ``ip``."""
        best: Subnet | None = None
        for subnet in self._subnets.values():
            if ip in subnet.network and (
                best is None or subnet.network.prefixlen > best.network.prefixlen
            ):
                best = subnet
        return best

    def addresses_in(
        self, subnet: Subnet
    ) -> list[tuple[NetworkDevice, NetworkInterface]]:
        """Interfaces whose address lies in ``subnet`` (most specific match)."""
        result: list[tuple[NetworkDevice, NetworkInterface]] = []
        for device in self.devices():
            for iface in device.addressed_interfaces():
                assert iface.address is not None
                owner = self.subnet_for(iface.address.ip)
                if owner is not None and owner.id == subnet.id:
                    result.append((device, iface))
        result.sort(key=lambda p: int(p[1].address.ip) if p[1].address else 0)
        return result

    def next_free_address(self, subnet: Subnet) -> IPv4Address | None:
        """Lowest unused host address (skipping the gateway)."""
        used = {i.address.ip for _, i in self.addresses_in(subnet) if i.address}
        for ip in subnet.hosts():
            if ip in used or ip == subnet.gateway:
                continue
            if self._owner_of_ip(ip) is None:
                return ip
        return None

    # ----------------------------------------------------------- addresses
    def assign_address(
        self, device_id: DeviceId, if_name: str, addr: IPv4Interface
    ) -> Subnet:
        """Validate (§2.1, §2.3) and assign ``addr`` to an interface."""
        device = self.get_device(device_id)
        iface = device.get_interface(if_name)
        if isinstance(device, Switch):
            raise InvalidAddressError(
                f"{device.hostname} is an L2 switch; ports cannot have IP addresses."
            )
        subnet = self.subnet_for(addr.ip)
        if subnet is None:
            raise AddressNotInSubnetError(
                f"{addr.ip} is not inside any defined subnet."
            )
        if subnet.network != addr.network:
            raise AddressNotInSubnetError(
                f"{addr} does not match subnet {subnet.network} "
                f"(expected prefix /{subnet.network.prefixlen})."
            )
        subnet.validate_host(addr.ip, loopback=iface.is_loopback)
        owner = self._owner_of_ip(addr.ip)
        if owner is not None and not (owner[0].id == device_id and owner[1] == if_name):
            raise DuplicateAddressError(
                f"{addr.ip} is already assigned to {owner[0].hostname} {owner[1]}."
            )
        iface.assign_address(addr)
        device.on_address_changed()
        return subnet

    def release_address(self, device_id: DeviceId, if_name: str) -> None:
        """Remove an interface address (connected routes follow)."""
        device = self.get_device(device_id)
        iface = device.get_interface(if_name)
        iface.clear_address()
        cache = device.arp_cache()
        if cache is not None:
            cache.remove_interface(if_name)
        device.on_address_changed()

    # --------------------------------------------------------------- links
    def links(self) -> tuple[Link, ...]:
        """All links ordered by id."""
        return tuple(self._links[k] for k in sorted(self._links))

    def get_link(self, link_id: LinkId) -> Link:
        """Link by id."""
        try:
            return self._links[link_id]
        except KeyError:
            raise LinkNotFoundError(f"Link {link_id} not found.") from None

    def link_for(self, ref: InterfaceRef) -> Link | None:
        """Link attached to ``ref``."""
        link_id = self._link_by_ref.get(ref)
        return None if link_id is None else self._links[link_id]

    def connect(
        self,
        a: InterfaceRef,
        b: InterfaceRef,
        capacity_mbps: int = DEFAULT_CAPACITY_MBPS,
        latency_ms: float = DEFAULT_LATENCY_MS,
        link_id: LinkId | None = None,
        admin_up: bool = True,
    ) -> Link:
        """Create a link; each interface may have at most one link."""
        if a.device_id == b.device_id:
            raise InvalidLinkError("A link must connect two different devices.")
        for ref in (a, b):
            device = self.get_device(ref.device_id)
            iface = device.get_interface(ref.interface)
            if iface.link_id is not None or ref in self._link_by_ref:
                raise InterfaceInUseError(
                    f"{ref.interface} on {device.hostname} is already linked."
                )
        new_id = link_id if link_id is not None else self.next_link_id()
        if new_id in self._links:
            raise InvalidLinkError(f"Link id {new_id} already exists.")
        link = Link(new_id, a, b, capacity_mbps, latency_ms, admin_up)
        self._links[new_id] = link
        for ref in (a, b):
            self._link_by_ref[ref] = new_id
            self.get_device(ref.device_id).get_interface(ref.interface).attach_link(
                new_id
            )
        return link

    def disconnect(self, link_id: LinkId) -> Link:
        """Remove a link."""
        link = self.get_link(link_id)
        for ref in link.endpoints():
            self._link_by_ref.pop(ref, None)
            device = self._devices.get(ref.device_id)
            if device is not None and device.has_interface(ref.interface):
                device.get_interface(ref.interface).detach_link()
        del self._links[link_id]
        return link

    def peer(self, ref: InterfaceRef) -> InterfaceRef | None:
        """Interface at the other end of ``ref``'s link."""
        link = self.link_for(ref)
        return None if link is None else link.peer_of(ref)

    def has_switch_loop(self) -> bool:
        """True if switches alone form a cycle (§8.4 warning)."""
        parent: dict[DeviceId, DeviceId] = {}

        def find(x: DeviceId) -> DeviceId:
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for link in self.links():
            da = self._devices[link.endpoint_a.device_id]
            db = self._devices[link.endpoint_b.device_id]
            if not (isinstance(da, Switch) and isinstance(db, Switch)):
                continue
            ra, rb = find(da.id), find(db.id)
            if ra == rb:
                return True
            parent[ra] = rb
        return False

    # -------------------------------------------------- operational state
    def egress_failure(self, ref: InterfaceRef) -> DropReason | None:
        """Why ``ref`` cannot transmit, or ``None`` (NETWORK_SPEC §3.1)."""
        device = self.get_device(ref.device_id)
        iface = device.get_interface(ref.interface)
        if not device.is_online():
            return DropReason.DEVICE_OFFLINE
        if not iface.admin_up:
            return (
                DropReason.PORT_DOWN
                if isinstance(device, Switch)
                else DropReason.INTERFACE_DOWN
            )
        link = self.link_for(ref)
        if link is None or not link.admin_up:
            return DropReason.LINK_DOWN
        peer_ref = link.peer_of(ref)
        peer_dev = self.get_device(peer_ref.device_id)
        if not peer_dev.get_interface(peer_ref.interface).admin_up:
            return (
                DropReason.PORT_DOWN
                if isinstance(peer_dev, Switch)
                else DropReason.LINK_DOWN
            )
        if not peer_dev.is_online():
            return DropReason.DEVICE_OFFLINE
        return None

    def describe_failure(self, ref: InterfaceRef) -> str:
        """Human explanation of ``egress_failure``."""
        device = self.get_device(ref.device_id)
        iface = device.get_interface(ref.interface)
        if not device.is_online():
            return f"{device.hostname} is {device.status.value.lower()}"
        if not iface.admin_up:
            return f"{device.hostname} {ref.interface} is admin down"
        link = self.link_for(ref)
        if link is None:
            return f"{device.hostname} {ref.interface} has no link"
        peer_ref = link.peer_of(ref)
        peer_dev = self.get_device(peer_ref.device_id)
        if not link.admin_up:
            return (
                f"link {device.hostname}:{ref.interface} ↔ "
                f"{peer_dev.hostname}:{peer_ref.interface} is down"
            )
        if not peer_dev.get_interface(peer_ref.interface).admin_up:
            return f"peer {peer_dev.hostname} {peer_ref.interface} is admin down"
        if not peer_dev.is_online():
            return f"next device {peer_dev.hostname} is {peer_dev.status.value.lower()}"
        return "operational"

    def is_operational(self, ref: InterfaceRef) -> bool:
        """NETWORK_SPEC §3.1 operational-up predicate."""
        return self.egress_failure(ref) is None

    # -------------------------------------------------------------- L2 walk
    def _bfs(self, start: InterfaceRef) -> dict[InterfaceRef, L2Path]:
        """Static L2 reachability through switches (ignores state)."""
        reached: dict[InterfaceRef, L2Path] = {}
        visited_switches: set[DeviceId] = set()
        queue: deque[tuple[InterfaceRef, L2Path]] = deque([(start, [])])
        while queue:
            out_ref, path = queue.popleft()
            link = self.link_for(out_ref)
            if link is None:
                continue
            in_ref = link.peer_of(out_ref)
            if in_ref in reached or in_ref == start:
                continue
            new_path = [*path, (out_ref, in_ref)]
            reached[in_ref] = new_path
            device = self._devices[in_ref.device_id]
            if isinstance(device, Switch):
                if device.id in visited_switches:
                    continue
                visited_switches.add(device.id)
                for iface in device.interfaces():
                    if iface.name != in_ref.interface and iface.link_id is not None:
                        queue.append((InterfaceRef(device.id, iface.name), new_path))
        return reached

    def l2_segment(self, ref: InterfaceRef) -> frozenset[InterfaceRef]:
        """Interfaces in the same broadcast domain (stops at routers/hosts)."""
        return frozenset({ref, *self._bfs(ref)})

    def l2_path_to_owner(self, ref: InterfaceRef, ip: IPv4Address) -> L2Path | None:
        """Shortest static L2 path from ``ref`` to the interface owning ``ip``."""
        for in_ref, path in self._bfs(ref).items():
            device = self._devices[in_ref.device_id]
            if device.device_type is DeviceType.SWITCH:
                continue
            iface = device.get_interface(in_ref.interface)
            if iface.address is not None and iface.address.ip == ip:
                return path
        return None

    def l2_path_to_mac(self, ref: InterfaceRef, mac: MacAddress) -> L2Path | None:
        """Shortest static L2 path from ``ref`` to the interface with ``mac``."""
        for in_ref, path in self._bfs(ref).items():
            iface = self._devices[in_ref.device_id].get_interface(in_ref.interface)
            if iface.mac == mac:
                return path
        return None

    def path_failure(self, path: L2Path) -> tuple[DropReason, str] | None:
        """First operational failure along an L2 path."""
        for out_ref, _in_ref in path:
            reason = self.egress_failure(out_ref)
            if reason is not None:
                return reason, self.describe_failure(out_ref)
        return None

    def switch_learn(
        self, ref: InterfaceRef, mac: MacAddress, now: datetime, timeout_s: int
    ) -> bool:
        """If ``ref`` is a switch port, learn ``mac`` there. Returns True if so."""
        device = self._devices.get(ref.device_id)
        if isinstance(device, Switch):
            device.learn(mac, ref.interface, now, timeout_s)
            return True
        return False

    # ------------------------------------------------------------- helpers
    def interface_refs(self, device_id: DeviceId) -> Iterable[InterfaceRef]:
        """All interface refs of a device."""
        for iface in self.get_device(device_id).interfaces():
            yield InterfaceRef(device_id, iface.name)

    def port_ref(self, switch_id: DeviceId, number: int) -> InterfaceRef:
        """Ref for a switch port (validates the number)."""
        switch = self.get_switch(switch_id)
        switch.get_port(number)
        return InterfaceRef(switch_id, port_name(number))
