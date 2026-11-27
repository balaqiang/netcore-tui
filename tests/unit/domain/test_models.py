"""Subnet, Link, Packet, interface and device basics (T-103, T-104, T-108)."""

from __future__ import annotations

from datetime import timedelta
from ipaddress import IPv4Address, IPv4Network

import pytest

from netcore.domain.addressing import MacAddress
from netcore.domain.arp import ArpTable
from netcore.domain.devices.router import Router
from netcore.domain.devices.switch import MacTable, Switch, SwitchPort
from netcore.domain.enums import DeviceStatus
from netcore.domain.errors import (
    AddressNotInSubnetError,
    DuplicateInterfaceError,
    InterfaceNotFoundError,
    InvalidLinkError,
    InvalidNextHopError,
    InvalidPortError,
    InvalidValueError,
    ReservedAddressError,
)
from netcore.domain.ids import DeviceId, LinkId, SubnetId
from netcore.domain.interface import InterfaceRef, NetworkInterface
from netcore.domain.link import Link
from netcore.domain.packet import Packet
from netcore.domain.subnet import Subnet

MAC1 = MacAddress.parse("02:00:00:00:00:01")
MAC2 = MacAddress.parse("02:00:00:00:00:02")


def _subnet(cidr: str) -> Subnet:
    return Subnet(SubnetId(1), IPv4Network(cidr), "s")


def test_subnet_reserved_addresses():
    s = _subnet("10.0.1.0/24")
    assert s.usable_hosts() == 254
    with pytest.raises(ReservedAddressError):
        s.validate_host(IPv4Address("10.0.1.0"))
    with pytest.raises(ReservedAddressError):
        s.validate_host(IPv4Address("10.0.1.255"))
    with pytest.raises(AddressNotInSubnetError):
        s.validate_host(IPv4Address("10.0.2.5"))
    s.validate_host(IPv4Address("10.0.1.10"))


def test_subnet_p2p_and_host_routes():
    p2p = _subnet("10.0.0.0/31")
    assert p2p.usable_hosts() == 2
    p2p.validate_host(IPv4Address("10.0.0.0"))
    p2p.validate_host(IPv4Address("10.0.0.1"))
    host = _subnet("10.9.9.9/32")
    assert host.usable_hosts() == 1
    with pytest.raises(ReservedAddressError):
        host.validate_host(IPv4Address("10.9.9.9"))
    host.validate_host(IPv4Address("10.9.9.9"), loopback=True)


def test_subnet_gateway_validation():
    with pytest.raises(InvalidNextHopError):
        Subnet(SubnetId(1), IPv4Network("10.0.1.0/24"), gateway=IPv4Address("10.0.2.1"))
    assert _subnet("10.0.1.0/30").hosts() == [
        IPv4Address("10.0.1.1"),
        IPv4Address("10.0.1.2"),
    ]


def test_link_rejects_same_device_and_bad_capacity():
    a = InterfaceRef(DeviceId(1), "eth0")
    with pytest.raises(InvalidLinkError):
        Link(LinkId(1), a, InterfaceRef(DeviceId(1), "eth1"))
    with pytest.raises(InvalidLinkError):
        Link(LinkId(1), a, InterfaceRef(DeviceId(2), "eth0"), capacity_mbps=0)
    link = Link(LinkId(1), a, InterfaceRef(DeviceId(2), "eth0"))
    assert link.peer_of(a) == InterfaceRef(DeviceId(2), "eth0")
    with pytest.raises(InvalidLinkError):
        link.peer_of(InterfaceRef(DeviceId(3), "x"))


def test_packet_validation_and_with_ttl():
    p = Packet(1, IPv4Address("10.0.0.1"), IPv4Address("10.0.0.2"))
    q = p.with_ttl(10)
    assert q.ttl == 10
    assert p.ttl == 64
    assert q is not p
    with pytest.raises(InvalidValueError):
        Packet(1, p.src_ip, p.dst_ip, ttl=0)
    with pytest.raises(InvalidValueError):
        Packet(1, p.src_ip, p.dst_ip, size_bytes=10)
    with pytest.raises(InvalidValueError):
        Packet(1, p.src_ip, p.dst_ip, payload="x" * 200)


def test_device_interface_limits_and_lookup():
    with pytest.raises(InvalidValueError):
        Router(DeviceId(1), "r", [])
    with pytest.raises(DuplicateInterfaceError):
        Router(
            DeviceId(1),
            "r",
            [NetworkInterface("ge0/0", MAC1), NetworkInterface("ge0/0", MAC2)],
        )
    r = Router(DeviceId(1), "r", [NetworkInterface("ge0/0", MAC1)])
    with pytest.raises(InterfaceNotFoundError):
        r.get_interface("ge9/9")
    r.set_status(DeviceStatus.MAINTENANCE)
    assert not r.is_online()


def test_at10_invalid_switch_port():
    """AT-10 — port 99 on a 24-port switch raises InvalidPortError."""
    sw = Switch(
        DeviceId(1),
        "sw-01",
        [
            NetworkInterface(f"port{i}", MacAddress(f"02:00:00:00:01:{i:02x}"))
            for i in range(1, 25)
        ],
    )
    with pytest.raises(InvalidPortError) as exc:
        sw.get_port(99)
    assert exc.value.code == "NET011"
    assert "1-24" in exc.value.message
    sw.set_port_admin(3, False)
    assert not sw.get_port(3).admin_up


def test_switch_port_speed():
    with pytest.raises(InvalidValueError):
        SwitchPort(1, NetworkInterface("port1", MAC1), speed_mbps=123)


def test_mac_table_expiry(fixed_now):
    t = MacTable(timeout_s=10)
    t.learn(MAC1, 3, fixed_now)
    assert t.lookup(MAC1, fixed_now + timedelta(seconds=5)) == 3
    assert t.lookup(MAC1, fixed_now + timedelta(seconds=10)) is None
    assert t.entries(fixed_now + timedelta(seconds=11)) == ()
    t.clear()
    assert t.entries() == ()


def test_arp_table_static_never_expires(fixed_now):
    t = ArpTable(timeout_s=10)
    ip1, ip2 = IPv4Address("10.0.0.1"), IPv4Address("10.0.0.2")
    t.learn(ip1, MAC1, "eth0", fixed_now)
    t.add_static(ip2, MAC2, "eth0")
    later = fixed_now + timedelta(days=1)
    assert t.get(ip1, later) is None
    assert t.get(ip2, later) == MAC2
    t.learn(ip2, MAC1, "eth0", fixed_now)  # does not override static
    assert t.get(ip2, later) == MAC2
    assert len(t.entries(later)) == 1
