"""Mandatory acceptance scenarios AT-01..AT-10 (PRD §8), headless."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv4Interface

import pytest

from netcore.domain.addressing import parse_ipv4_address
from netcore.domain.devices.server import Server
from netcore.domain.enums import DeviceStatus, DropReason, HopKind, SimulationStatus
from netcore.domain.errors import (
    DuplicateAddressError,
    DuplicateMacError,
    InvalidAddressError,
    InvalidPortError,
)
from netcore.domain.interface import NetworkInterface


def hostnames(topo, result):
    return [topo.get_device(d).hostname for d in result.path]


def test_at01_successful_delivery(two_router_lab, engine_factory, request_for):
    """AT-01 — srv-a → srv-b across two routers: DELIVERED, TTL 64→62."""
    topo = two_router_lab
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    assert result.status is SimulationStatus.DELIVERED
    assert result.drop_reason is None
    assert hostnames(topo, result) == ["srv-a", "sw-a", "r1", "r2", "sw-b", "srv-b"]
    routes = [h for h in result.hops if h.kind is HopKind.ROUTE]
    assert routes[0].ttl_in == 64
    assert routes[-1].ttl_out == 62
    assert result.hops[-1].kind is HopKind.DELIVER
    assert result.hops[-1].device_name == "srv-b"


def test_at02_invalid_ipv4():
    """AT-02."""
    with pytest.raises(InvalidAddressError):
        parse_ipv4_address("10.0.0.256")


def test_at03_duplicate_ip(two_router_lab):
    """AT-03."""
    topo = two_router_lab
    with pytest.raises(DuplicateAddressError):
        topo.assign_address(
            topo.require("srv-b").id, "eth1", IPv4Interface("10.0.1.10/24")
        )


def test_at04_duplicate_mac(two_router_lab):
    """AT-04."""
    topo = two_router_lab
    mac = topo.require("srv-a").get_interface("eth0").mac
    with pytest.raises(DuplicateMacError):
        topo.add_device(
            Server(topo.next_device_id(), "srv-c", [NetworkInterface("eth0", mac)])
        )


def test_at05_missing_route(two_router_lab, engine_factory, request_for):
    """AT-05 — no matching route and no default: DROPPED / NO_ROUTE."""
    topo = two_router_lab
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "172.16.5.5"))
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason is DropReason.NO_ROUTE
    assert result.hops[-1].device_name == "r1"


def test_at06_longest_prefix_match(two_router_lab, request_for):
    """AT-06 — 10.0.0.0/8 and 10.1.2.0/24 present: 10.1.2.5 uses /24."""
    from ipaddress import IPv4Network

    from netcore.domain.devices.router import RoutingEntry
    from netcore.domain.enums import RouteType

    topo = two_router_lab
    r1 = topo.get_router(topo.require("r1").id)
    r1.add_static_route(
        RoutingEntry(
            0,
            IPv4Network("10.0.0.0/8"),
            IPv4Address("10.0.12.2"),
            "ge0/0",
            RouteType.STATIC,
            1,
        )
    )
    r1.add_static_route(
        RoutingEntry(
            0,
            IPv4Network("10.1.2.0/24"),
            IPv4Address("10.0.12.2"),
            "ge0/0",
            RouteType.STATIC,
            1,
        )
    )
    match = r1.lookup(IPv4Address("10.1.2.5"))
    assert match is not None
    assert str(match.destination) == "10.1.2.0/24"


def test_at07_ttl_expiration(two_router_lab, engine_factory, request_for):
    """AT-07 — TTL=1 crossing a router: DROPPED / TTL_EXPIRED at that router."""
    topo = two_router_lab
    result = engine_factory(topo).simulate(
        request_for(topo, "srv-a", "10.0.2.10", ttl=1)
    )
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason is DropReason.TTL_EXPIRED
    assert result.hops[-1].device_name == "r1"
    assert hostnames(topo, result) == ["srv-a", "sw-a", "r1"]


def test_at08_offline_device(two_router_lab, engine_factory, request_for):
    """AT-08 — middle router OFFLINE: DROPPED / DEVICE_OFFLINE."""
    topo = two_router_lab
    topo.require("r2").set_status(DeviceStatus.OFFLINE)
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason is DropReason.DEVICE_OFFLINE
    assert "r2" in result.hops[-1].reason


def test_at08_first_hop_router_offline(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    topo.require("r1").set_status(DeviceStatus.MAINTENANCE)
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    assert result.drop_reason is DropReason.DEVICE_OFFLINE


def test_at09_link_down(two_router_lab, engine_factory, request_for):
    """AT-09 — link down on path: DROPPED / LINK_DOWN."""
    topo = two_router_lab
    from netcore.domain.interface import InterfaceRef

    link = topo.link_for(InterfaceRef(topo.require("r1").id, "ge0/0"))
    assert link is not None
    link.set_admin(False)
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason is DropReason.LINK_DOWN
    assert result.hops[-1].device_name == "r1"


def test_at10_invalid_switch_port(two_router_lab):
    """AT-10."""
    topo = two_router_lab
    with pytest.raises(InvalidPortError):
        topo.get_switch(topo.require("sw-a").id).get_port(99)
