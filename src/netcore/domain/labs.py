"""Sample labs built through public topology methods (T-204)."""

from __future__ import annotations

import random
from collections.abc import Callable
from ipaddress import IPv4Address, IPv4Interface, IPv4Network

from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.router import Router, RoutingEntry
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch, port_name
from netcore.domain.enums import DeviceType, RouteType
from netcore.domain.errors import InvalidValueError
from netcore.domain.ids import DeviceId, SubnetId
from netcore.domain.interface import InterfaceRef, NetworkInterface
from netcore.domain.subnet import Subnet
from netcore.domain.topology import NetworkTopology


def interface_names(device_type: DeviceType, count: int) -> list[str]:
    """Default interface names per device type (NETWORK_SPEC §3)."""
    if device_type is DeviceType.ROUTER:
        return [f"ge0/{i}" for i in range(count)]
    if device_type is DeviceType.SWITCH:
        return [port_name(i) for i in range(1, count + 1)]
    return [f"eth{i}" for i in range(count)]


_CLASSES: dict[DeviceType, type[Router] | type[Switch] | type[Server]] = {
    DeviceType.ROUTER: Router,
    DeviceType.SWITCH: Switch,
    DeviceType.SERVER: Server,
}


def build_device(
    topology: NetworkTopology,
    rng: random.Random,
    device_type: DeviceType,
    hostname: str,
    interface_count: int | None = None,
    location: str = "",
    description: str = "",
) -> NetworkDevice:
    """Create (not add) a device with generated unique MACs."""
    cls = _CLASSES[device_type]
    count = cls.DEFAULT_INTERFACES if interface_count is None else interface_count
    if not cls.MIN_INTERFACES <= count <= cls.MAX_INTERFACES:
        raise InvalidValueError(
            f"{device_type.value.title()} interface count {count} must be between "
            f"{cls.MIN_INTERFACES} and {cls.MAX_INTERFACES}."
        )
    macs = topology.generate_macs(rng, count)
    ifaces = [
        NetworkInterface(name, mac)
        for name, mac in zip(interface_names(device_type, count), macs, strict=True)
    ]
    return cls(
        topology.next_device_id(),
        hostname,
        ifaces,
        location=location,
        description=description,
    )


def add_device(
    topology: NetworkTopology,
    rng: random.Random,
    device_type: DeviceType,
    hostname: str,
    interface_count: int | None = None,
    location: str = "",
) -> NetworkDevice:
    """Create and add a device."""
    device = build_device(
        topology, rng, device_type, hostname, interface_count, location
    )
    topology.add_device(device)
    return device


class _Builder:
    def __init__(self, rng: random.Random) -> None:
        self.topo = NetworkTopology()
        self.rng = rng

    def dev(self, kind: DeviceType, name: str, count: int | None = None) -> DeviceId:
        return add_device(self.topo, self.rng, kind, name, count).id

    def subnet(self, cidr: str, name: str, gateway: str | None = None) -> None:
        self.topo.add_subnet(
            Subnet(
                SubnetId(self.topo.next_subnet_id()),
                IPv4Network(cidr),
                name,
                IPv4Address(gateway) if gateway else None,
            )
        )

    def ip(self, dev: DeviceId, iface: str, addr: str) -> None:
        self.topo.assign_address(dev, iface, IPv4Interface(addr))

    def link(
        self, a: DeviceId, ai: str, b: DeviceId, bi: str, capacity: int = 1000
    ) -> None:
        self.topo.connect(InterfaceRef(a, ai), InterfaceRef(b, bi), capacity)

    def route(
        self, router: DeviceId, dest: str, via: str, iface: str, metric: int = 0
    ) -> None:
        self.topo.get_router(router).add_static_route(
            RoutingEntry(
                0,
                IPv4Network(dest),
                IPv4Address(via),
                iface,
                RouteType.STATIC,
                1,
                metric,
            )
        )

    def gateway(self, server: DeviceId, ip: str) -> None:
        self.topo.get_server(server).set_default_gateway(IPv4Address(ip))


def build_two_router_lab(rng: random.Random) -> NetworkTopology:
    """Reference topology of NETWORK_SPEC §13."""
    b = _Builder(rng)
    rt, sw, srv_t = DeviceType.ROUTER, DeviceType.SWITCH, DeviceType.SERVER
    srv_a = b.dev(srv_t, "srv-a")
    sw_a = b.dev(sw, "sw-a")
    r1 = b.dev(rt, "r1")
    r2 = b.dev(rt, "r2")
    sw_b = b.dev(sw, "sw-b")
    srv_b = b.dev(srv_t, "srv-b")
    b.subnet("10.0.1.0/24", "lan-a", "10.0.1.1")
    b.subnet("10.0.2.0/24", "lan-b", "10.0.2.1")
    b.subnet("10.0.12.0/30", "r1-r2")
    b.ip(srv_a, "eth0", "10.0.1.10/24")
    b.ip(srv_b, "eth0", "10.0.2.10/24")
    b.ip(r1, "ge0/1", "10.0.1.1/24")
    b.ip(r1, "ge0/0", "10.0.12.1/30")
    b.ip(r2, "ge0/0", "10.0.12.2/30")
    b.ip(r2, "ge0/1", "10.0.2.1/24")
    b.gateway(srv_a, "10.0.1.1")
    b.gateway(srv_b, "10.0.2.1")
    b.link(srv_a, "eth0", sw_a, "port1")
    b.link(sw_a, "port24", r1, "ge0/1")
    b.link(r1, "ge0/0", r2, "ge0/0")
    b.link(r2, "ge0/1", sw_b, "port24")
    b.link(sw_b, "port1", srv_b, "eth0")
    b.route(r1, "10.0.2.0/24", "10.0.12.2", "ge0/0")
    b.route(r2, "10.0.1.0/24", "10.0.12.1", "ge0/0")
    return b.topo


def build_spine_leaf_lab(rng: random.Random) -> NetworkTopology:
    """2 spines, 4 leaves (L3), 4 ToR switches, 8 servers."""
    b = _Builder(rng)
    rt, sw, srv_t = DeviceType.ROUTER, DeviceType.SWITCH, DeviceType.SERVER
    spines = [b.dev(rt, f"spine-{s}", 4) for s in (1, 2)]
    for leaf_no in range(1, 5):
        leaf = b.dev(rt, f"leaf-{leaf_no}", 4)
        tor = b.dev(sw, f"tor-{leaf_no}", 24)
        lan = f"10.0.{leaf_no}"
        b.subnet(f"{lan}.0/24", f"rack-{leaf_no}", f"{lan}.1")
        b.ip(leaf, "ge0/2", f"{lan}.1/24")
        b.link(leaf, "ge0/2", tor, "port24", 10000)
        for s_idx, spine in enumerate(spines, start=1):
            p2p = f"10.255.{s_idx}{leaf_no}"
            b.subnet(f"{p2p}.0/30", f"spine{s_idx}-leaf{leaf_no}")
            spine_if = f"ge0/{leaf_no - 1}"
            leaf_if = f"ge0/{s_idx - 1}"
            b.ip(spine, spine_if, f"{p2p}.1/30")
            b.ip(leaf, leaf_if, f"{p2p}.2/30")
            b.link(spine, spine_if, leaf, leaf_if, 40000)
            b.route(spine, f"{lan}.0/24", f"{p2p}.2", spine_if)
            b.route(leaf, "0.0.0.0/0", f"{p2p}.1", leaf_if, metric=(s_idx - 1) * 10)
        for host_no in (1, 2):
            srv = b.dev(srv_t, f"srv-{leaf_no}{host_no}")
            b.ip(srv, "eth0", f"{lan}.{10 + host_no}/24")
            b.gateway(srv, f"{lan}.1")
            b.link(srv, "eth0", tor, f"port{host_no}", 10000)
    return b.topo


SAMPLE_LABS: dict[str, Callable[[random.Random], NetworkTopology]] = {
    "two-router": build_two_router_lab,
    "spine-leaf": build_spine_leaf_lab,
}
