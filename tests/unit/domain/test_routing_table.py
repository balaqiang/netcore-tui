"""NETWORK_SPEC §6.2 — longest prefix match (AT-06)."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv4Interface, IPv4Network

import pytest

from netcore.domain.addressing import MacAddress
from netcore.domain.devices.router import Router, RoutingEntry, RoutingTable
from netcore.domain.enums import RouteType
from netcore.domain.errors import (
    DuplicateRouteError,
    InvalidNextHopError,
    RouteNotFoundError,
)
from netcore.domain.ids import DeviceId
from netcore.domain.interface import NetworkInterface


def _entry(dest, via, iface, metric=0, rtype=RouteType.STATIC, ad=1):
    return RoutingEntry(
        0,
        IPv4Network(dest),
        IPv4Address(via) if via else None,
        iface,
        rtype,
        ad,
        metric,
    )


@pytest.fixture
def spec_table() -> RoutingTable:
    table = RoutingTable()
    table.add(_entry("0.0.0.0/0", "10.0.0.1", "ge0/0", rtype=RouteType.DEFAULT))
    table.add(_entry("10.0.0.0/8", "10.0.0.2", "ge0/1"))
    table.add(_entry("10.1.0.0/16", "10.0.0.3", "ge0/1"))
    iface = NetworkInterface(
        "ge0/2", MacAddress.parse("02:00:00:00:00:01"), IPv4Interface("10.1.2.1/24")
    )
    table.sync_connected([iface])
    return table


@pytest.mark.parametrize(
    ("dst", "expected"),
    [
        ("10.1.2.5", "10.1.2.0/24"),
        ("10.1.3.5", "10.1.0.0/16"),
        ("10.9.9.9", "10.0.0.0/8"),
        ("8.8.8.8", "0.0.0.0/0"),
        ("10.1.2.0", "10.1.2.0/24"),
    ],
)
def test_at06_spec_table(spec_table, dst, expected):
    """AT-06 / NETWORK_SPEC §6.2 example table, used verbatim."""
    match = spec_table.longest_prefix_match(IPv4Address(dst))
    assert match is not None
    assert str(match.destination) == expected


def test_lpm_is_not_string_prefix():
    """Defect #1: '10.1.2.0/24' must not match 10.1.20.5 by string prefix."""
    table = RoutingTable()
    table.add(_entry("10.1.2.0/24", "1.1.1.1", "x"))
    assert table.longest_prefix_match(IPv4Address("10.1.20.5")) is None


def test_tie_break_ad_metric_order():
    table = RoutingTable()
    table.add(_entry("10.0.0.0/8", "1.1.1.2", "a", metric=5))
    best = table.add(_entry("10.0.0.0/8", "1.1.1.3", "a", metric=1))
    assert table.longest_prefix_match(IPv4Address("10.2.3.4")) == best
    first = table.add(_entry("172.16.0.0/12", "1.1.1.4", "a"))
    table.add(_entry("172.16.0.0/12", "1.1.1.5", "a"))
    assert table.longest_prefix_match(IPv4Address("172.16.1.1")) == first


def test_duplicate_route(spec_table):
    with pytest.raises(DuplicateRouteError):
        spec_table.add(_entry("10.0.0.0/8", "10.0.0.2", "ge0/1"))


def test_connected_route_not_removable(spec_table):
    connected = next(
        e for e in spec_table.entries() if e.route_type is RouteType.CONNECTED
    )
    with pytest.raises(RouteNotFoundError):
        spec_table.remove(connected.id)
    with pytest.raises(RouteNotFoundError):
        spec_table.remove(999)


def test_router_static_route_validation():
    r = Router(
        DeviceId(1),
        "r1",
        [
            NetworkInterface(
                "ge0/0",
                MacAddress.parse("02:00:00:00:00:01"),
                IPv4Interface("10.0.12.1/30"),
            ),
            NetworkInterface("ge0/1", MacAddress.parse("02:00:00:00:00:02")),
        ],
    )
    with pytest.raises(InvalidNextHopError):
        r.add_static_route(_entry("10.0.2.0/24", "172.16.0.1", "ge0/0"))
    with pytest.raises(InvalidNextHopError):
        r.add_static_route(_entry("10.0.2.0/24", "10.0.12.2", "ge0/1"))
    with pytest.raises(InvalidNextHopError):
        r.add_static_route(_entry("10.0.2.0/24", "10.0.12.1", "ge0/0"))
    added = r.add_static_route(_entry("0.0.0.0/0", "10.0.12.2", "ge0/0"))
    assert added.route_type is RouteType.DEFAULT
    assert r.lookup(IPv4Address("8.8.8.8")) == added
    assert "via 10.0.12.2" in added.describe()
    r.remove_route(added.id)
    assert r.lookup(IPv4Address("8.8.8.8")) is None


def test_connected_routes_follow_addresses():
    """US-RT-2: connected route appears and disappears with the address."""
    iface = NetworkInterface("ge0/0", MacAddress.parse("02:00:00:00:00:01"))
    r = Router(DeviceId(1), "r1", [iface])
    assert r.routing_table.entries() == ()
    iface.assign_address(IPv4Interface("10.0.0.1/24"))
    r.on_address_changed()
    assert [str(e.destination) for e in r.routing_table.entries()] == ["10.0.0.0/24"]
    iface.clear_address()
    r.on_address_changed()
    assert r.routing_table.entries() == ()
