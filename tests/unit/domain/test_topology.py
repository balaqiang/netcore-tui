"""NetworkTopology aggregate invariants (T-107)."""

from __future__ import annotations

import random
from ipaddress import IPv4Address, IPv4Interface, IPv4Network

import pytest

from netcore.domain.addressing import MacAddress
from netcore.domain.devices.server import Server
from netcore.domain.enums import DeviceStatus, DeviceType, DropReason
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
    ReservedAddressError,
    SubnetInUseError,
)
from netcore.domain.ids import DeviceId, SubnetId
from netcore.domain.interface import InterfaceRef, NetworkInterface
from netcore.domain.labs import add_device
from netcore.domain.subnet import Subnet
from netcore.domain.topology import NetworkTopology


def _ref(topo, name, iface):
    return InterfaceRef(topo.require(name).id, iface)


def test_at03_duplicate_ip(two_router_lab):
    """AT-03 — second assignment of 10.0.1.10 rejected (NET005)."""
    topo = two_router_lab
    with pytest.raises(DuplicateAddressError) as exc:
        topo.assign_address(
            topo.require("srv-a").id, "eth1", IPv4Interface("10.0.1.10/24")
        )
    assert exc.value.code == "NET005"
    assert "srv-a eth0" in exc.value.message


def test_at04_duplicate_mac(two_router_lab):
    """AT-04 — interface with an existing MAC rejected (NET006)."""
    topo = two_router_lab
    existing = topo.require("r1").get_interface("ge0/0").mac
    server = Server(
        topo.next_device_id(),
        "srv-x",
        [NetworkInterface("eth0", existing)],
    )
    with pytest.raises(DuplicateMacError) as exc:
        topo.add_device(server)
    assert exc.value.code == "NET006"


def test_duplicate_hostname_case_insensitive(two_router_lab, rng):
    with pytest.raises(DuplicateHostnameError):
        add_device(two_router_lab, rng, DeviceType.SERVER, "SRV-A")
    with pytest.raises(DuplicateHostnameError):
        two_router_lab.rename_device(two_router_lab.require("r1").id, "R2")
    two_router_lab.rename_device(two_router_lab.require("r1").id, "core-r1")
    assert two_router_lab.find_by_hostname("CORE-R1") is not None


def test_overlapping_subnets(two_router_lab):
    topo = two_router_lab
    with pytest.raises(OverlappingSubnetError):
        topo.add_subnet(Subnet(topo.next_subnet_id(), IPv4Network("10.0.0.0/16")))
    parent = topo.add_subnet(
        Subnet(topo.next_subnet_id(), IPv4Network("172.16.0.0/16"), "dc")
    )
    child = topo.add_subnet(
        Subnet(topo.next_subnet_id(), IPv4Network("172.16.1.0/24"), parent_id=parent.id)
    )
    assert topo.subnet_for(IPv4Address("172.16.1.5")) == child
    with pytest.raises(InvalidSubnetError):
        topo.add_subnet(
            Subnet(
                topo.next_subnet_id(),
                IPv4Network("192.168.0.0/24"),
                parent_id=parent.id,
            )
        )
    with pytest.raises(SubnetInUseError):
        topo.remove_subnet(parent.id)
    topo.remove_subnet(child.id)


def test_assign_address_rules(two_router_lab):
    topo = two_router_lab
    srv = topo.require("srv-a").id
    with pytest.raises(AddressNotInSubnetError):
        topo.assign_address(srv, "eth1", IPv4Interface("192.168.9.9/24"))
    with pytest.raises(AddressNotInSubnetError):
        topo.assign_address(srv, "eth1", IPv4Interface("10.0.1.20/25"))
    with pytest.raises(ReservedAddressError):
        topo.assign_address(srv, "eth1", IPv4Interface("10.0.1.255/24"))
    with pytest.raises(InvalidAddressError):
        topo.assign_address(
            topo.require("sw-a").id, "port2", IPv4Interface("10.0.1.9/24")
        )
    subnet = topo.subnet_for(IPv4Address("10.0.1.10"))
    assert subnet is not None
    assert topo.next_free_address(subnet) == IPv4Address("10.0.1.2")
    topo.assign_address(srv, "eth1", IPv4Interface("10.0.1.20/24"))
    assert len(topo.addresses_in(subnet)) == 3
    with pytest.raises(SubnetInUseError):
        topo.remove_subnet(subnet.id)
    topo.release_address(srv, "eth1")
    assert len(topo.addresses_in(subnet)) == 2


def test_connect_one_link_per_interface(two_router_lab):
    topo = two_router_lab
    with pytest.raises(InterfaceInUseError):
        topo.connect(_ref(topo, "r1", "ge0/0"), _ref(topo, "srv-a", "eth1"))
    with pytest.raises(InvalidLinkError):
        topo.connect(_ref(topo, "r1", "ge0/2"), _ref(topo, "r1", "ge0/3"))
    link = topo.connect(_ref(topo, "r1", "ge0/2"), _ref(topo, "srv-a", "eth1"))
    assert topo.peer(_ref(topo, "r1", "ge0/2")) == _ref(topo, "srv-a", "eth1")
    topo.disconnect(link.id)
    assert topo.peer(_ref(topo, "r1", "ge0/2")) is None
    with pytest.raises(LinkNotFoundError):
        topo.get_link(link.id)


def test_is_operational_per_spec(two_router_lab):
    """NETWORK_SPEC §3.1 operational predicate."""
    topo = two_router_lab
    ref = _ref(topo, "r1", "ge0/0")
    assert topo.is_operational(ref)
    link = topo.link_for(ref)
    assert link is not None
    link.set_admin(False)
    assert topo.egress_failure(ref) is DropReason.LINK_DOWN
    link.set_admin(True)
    topo.require("r2").get_interface("ge0/0").set_admin(False)
    assert topo.egress_failure(ref) is DropReason.LINK_DOWN
    topo.require("r2").get_interface("ge0/0").set_admin(True)
    topo.require("r2").set_status(DeviceStatus.OFFLINE)
    assert topo.egress_failure(ref) is DropReason.DEVICE_OFFLINE
    assert "offline" in topo.describe_failure(ref)
    topo.require("r1").get_interface("ge0/0").set_admin(False)
    assert topo.egress_failure(ref) is DropReason.INTERFACE_DOWN
    assert topo.egress_failure(_ref(topo, "r1", "ge0/3")) is DropReason.LINK_DOWN


def test_l2_segment_stops_at_routers(two_router_lab):
    topo = two_router_lab
    seg = topo.l2_segment(_ref(topo, "srv-a", "eth0"))
    names = {topo.get_device(r.device_id).hostname for r in seg}
    assert names == {"srv-a", "sw-a", "r1"}
    assert _ref(topo, "r1", "ge0/0") not in seg


def test_remove_device_cleans_up(two_router_lab):
    topo = two_router_lab
    report = topo.remove_device(topo.require("r2").id)
    assert len(report.removed_links) == 2
    assert any("10.0.2.0/24 via 10.0.12.2" in r for r in report.removed_routes)
    assert topo.find_by_hostname("r2") is None
    assert len(topo.links()) == 3
    with pytest.raises(DeviceNotFoundError):
        topo.get_device(report.device_id)


def test_remove_router_clears_server_gateway(two_router_lab):
    topo = two_router_lab
    report = topo.remove_device(topo.require("r1").id)
    assert any("default gateway" in r for r in report.removed_routes)
    srv = topo.get_server(topo.require("srv-a").id)
    assert srv.default_gateway is None


def test_switch_loop_detection(rng):
    topo = NetworkTopology()
    a = add_device(topo, rng, DeviceType.SWITCH, "s1", 4)
    b = add_device(topo, rng, DeviceType.SWITCH, "s2", 4)
    topo.connect(InterfaceRef(a.id, "port1"), InterfaceRef(b.id, "port1"))
    assert not topo.has_switch_loop()
    topo.connect(InterfaceRef(a.id, "port2"), InterfaceRef(b.id, "port2"))
    assert topo.has_switch_loop()


def test_generated_macs_are_unique_and_deterministic():
    t1, t2 = NetworkTopology(), NetworkTopology()
    m1 = t1.generate_macs(random.Random(3), 50)
    m2 = t2.generate_macs(random.Random(3), 50)
    assert m1 == m2
    assert len(set(m1)) == 50


def test_typed_getters(two_router_lab):
    topo = two_router_lab
    with pytest.raises(DeviceNotFoundError):
        topo.get_router(topo.require("srv-a").id)
    with pytest.raises(DeviceNotFoundError):
        topo.get_switch(topo.require("srv-a").id)
    with pytest.raises(DeviceNotFoundError):
        topo.get_server(topo.require("r1").id)
    with pytest.raises(DeviceNotFoundError):
        topo.require("nope")
    assert topo.port_ref(topo.require("sw-a").id, 3).interface == "port3"


def test_add_device_with_duplicate_ip_rejected(two_router_lab):
    topo = two_router_lab
    iface = NetworkInterface(
        "eth0", MacAddress.parse("02:aa:00:00:00:01"), IPv4Interface("10.0.1.10/24")
    )
    with pytest.raises(DuplicateAddressError):
        topo.add_device(Server(DeviceId(99), "srv-z", [iface]))
    assert SubnetId(1) in {s.id for s in topo.subnets()}
