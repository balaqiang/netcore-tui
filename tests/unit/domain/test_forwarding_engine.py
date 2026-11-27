"""ForwardingEngine scenarios (T-109) — NETWORK_SPEC §6-§9."""

from __future__ import annotations

import time
from ipaddress import IPv4Interface

import pytest

from netcore.domain.addressing import MacAddress
from netcore.domain.enums import DeviceStatus, DropReason, HopKind, SimulationStatus
from netcore.domain.errors import InvalidSourceError
from netcore.domain.interface import InterfaceRef
from netcore.domain.packet import Frame
from netcore.domain.simulation.constants import SimulationSettings
from netcore.domain.simulation.context import ForwardingContext


def names(topo, result):
    return [topo.get_device(d).hostname for d in result.path]


def test_arp_hops_visible_and_do_not_consume_ttl(
    two_router_lab, engine_factory, request_for
):
    """NETWORK_SPEC §7.2 — ARP hops are recorded and leave TTL untouched."""
    topo = two_router_lab
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    arp = [h for h in result.hops if h.kind is HopKind.ARP]
    assert len(arp) == 3
    assert all(h.ttl_in is None and h.ttl_out is None for h in arp)
    routes = [h for h in result.hops if h.kind is HopKind.ROUTE]
    assert [(h.ttl_in, h.ttl_out) for h in routes] == [(64, 63), (63, 62)]
    assert result.arp_exchanges == 3


def test_arp_cache_hit_second_run(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    engine = engine_factory(topo)
    engine.simulate(request_for(topo, "srv-a", "10.0.2.10"))
    second = engine.simulate(request_for(topo, "srv-a", "10.0.2.10"))
    assert second.delivered
    assert second.arp_exchanges == 0
    assert any("cache hit" in h.reason for h in second.hops)


def test_mac_tables_learned(two_router_lab, engine_factory, request_for, fixed_now):
    topo = two_router_lab
    engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    sw = topo.get_switch(topo.require("sw-a").id)
    learned = {e.port for e in sw.mac_table.entries(fixed_now)}
    assert learned == {1, 24}


def test_switch_never_reads_dst_ip(two_router_lab, fixed_now):
    """Defect #3 — switch decisions use dst MAC only (test double payload)."""

    class Exploding:
        def __getattr__(self, item):
            raise AssertionError(f"switch read payload.{item}")

    topo = two_router_lab
    sw = topo.get_switch(topo.require("sw-a").id)
    r1_mac = topo.require("r1").get_interface("ge0/1").mac
    src_mac = topo.require("srv-a").get_interface("eth0").mac
    sw.mac_table.learn(r1_mac, 24, fixed_now)
    ctx = ForwardingContext(topo, fixed_now, SimulationSettings())
    frame = Frame(1, src_mac, r1_mac, Exploding())  # type: ignore[arg-type]
    decision = sw.receive(frame, "port1", ctx)
    assert decision.egress == ("port24",)
    unknown = Frame(2, src_mac, MacAddress.parse("02:99:99:99:99:99"), Exploding())  # type: ignore[arg-type]
    flood = sw.receive(unknown, "port1", ctx)
    assert "port24" in flood.egress
    assert "port1" not in flood.egress
    same = sw.receive(Frame(3, r1_mac, src_mac, Exploding()), "port1", ctx)  # type: ignore[arg-type]
    assert same.drop_reason is DropReason.FILTERED


def test_switch_ingress_port_down(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    topo.get_switch(topo.require("sw-b").id).set_port_admin(1, False)
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason is DropReason.PORT_DOWN


def test_switch_offline_on_arp_path(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    topo.require("sw-a").set_status(DeviceStatus.OFFLINE)
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    assert result.drop_reason is DropReason.DEVICE_OFFLINE
    assert names(topo, result) == ["srv-a"]


def test_arp_failure_no_owner(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.1.99"))
    assert result.drop_reason is DropReason.ARP_FAILED


def test_router_interface_admin_down(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    topo.require("r1").get_interface("ge0/0").set_admin(False)
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    assert result.drop_reason is DropReason.INTERFACE_DOWN
    assert result.hops[-1].device_name == "r1"


def test_deliver_to_router_address(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.12.2"))
    assert result.delivered
    assert result.hops[-1].device_name == "r2"


def test_router_as_source(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    result = engine_factory(topo).simulate(request_for(topo, "r1", "10.0.2.10"))
    assert result.delivered
    assert names(topo, result) == ["r1", "r2", "sw-b", "srv-b"]


def test_local_delivery(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.1.10"))
    assert result.delivered
    assert names(topo, result) == ["srv-a"]


def test_server_without_gateway(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    topo.get_server(topo.require("srv-a").id).set_default_gateway(None)
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    assert result.drop_reason is DropReason.NO_ROUTE
    assert result.hops[-1].device_name == "srv-a"


def test_no_interface_when_all_down(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    topo.require("srv-a").get_interface("eth0").set_admin(False)
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    assert result.drop_reason is DropReason.NO_INTERFACE


def test_invalid_sources(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    engine = engine_factory(topo)
    with pytest.raises(InvalidSourceError):
        engine.simulate(request_for(topo, "sw-a", "10.0.2.10"))
    topo.require("srv-a").set_status(DeviceStatus.OFFLINE)
    with pytest.raises(InvalidSourceError):
        engine.simulate(request_for(topo, "srv-a", "10.0.2.10"))
    topo.release_address(topo.require("srv-b").id, "eth0")
    with pytest.raises(InvalidSourceError):
        engine.simulate(request_for(topo, "srv-b", "10.0.1.10"))


def test_hop_limit_guard(two_router_lab, engine_factory, request_for):
    """FR-SIM-04 — a routing loop is stopped by TTL or the hop guard."""
    topo = two_router_lab
    from ipaddress import IPv4Address, IPv4Network

    from netcore.domain.devices.router import RoutingEntry
    from netcore.domain.enums import RouteType

    r1, r2 = (
        topo.get_router(topo.require("r1").id),
        topo.get_router(topo.require("r2").id),
    )
    for router, via in ((r1, "10.0.12.2"), (r2, "10.0.12.1")):
        router.add_static_route(
            RoutingEntry(
                0,
                IPv4Network("192.168.0.0/16"),
                IPv4Address(via),
                "ge0/0",
                RouteType.STATIC,
                1,
            )
        )
    loop_ttl = engine_factory(topo).simulate(
        request_for(topo, "srv-a", "192.168.1.1", ttl=10)
    )
    assert loop_ttl.drop_reason is DropReason.TTL_EXPIRED
    guard = engine_factory(topo, SimulationSettings(max_hops=8)).simulate(
        request_for(topo, "srv-a", "192.168.1.1", ttl=255)
    )
    assert guard.drop_reason is DropReason.HOP_LIMIT


def test_deterministic(engine_factory, request_for):
    from tests.fixtures.two_router_lab import make_two_router_lab

    results = []
    for _ in range(2):
        topo = make_two_router_lab()
        r = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
        results.append([(h.kind, h.device_name, h.reason) for h in r.hops])
    assert results[0] == results[1]


def test_traceroute(two_router_lab, engine_factory, request_for):
    """NETWORK_SPEC §9.2."""
    topo = two_router_lab
    tr = engine_factory(topo).traceroute(request_for(topo, "srv-a", "10.0.2.10"))
    assert tr.reached
    assert [(h.ttl, h.device_name, h.status) for h in tr.hops] == [
        (1, "r1", "TTL_EXPIRED"),
        (2, "r2", "TTL_EXPIRED"),
        (3, "srv-b", "DELIVERED"),
    ]


def test_traceroute_unreachable(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    tr = engine_factory(topo).traceroute(request_for(topo, "srv-a", "172.16.0.1"))
    assert not tr.reached
    assert tr.hops[-1].status == "NO_ROUTE"


def test_latency_is_simulated_sum(two_router_lab, engine_factory, request_for):
    topo = two_router_lab
    r = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    # 5 links x 0.1 + 2 switches x 0.01 + 2 routers x 0.05
    assert r.total_latency_ms == pytest.approx(0.62)


def test_nfr01_performance(engine_factory, request_for, rng):
    """NFR-01 — a ≤50-hop simulation completes in < 50 ms."""
    from ipaddress import IPv4Address, IPv4Network

    from netcore.domain.devices.router import RoutingEntry
    from netcore.domain.enums import DeviceType, RouteType
    from netcore.domain.labs import add_device
    from netcore.domain.subnet import Subnet
    from netcore.domain.topology import NetworkTopology

    topo = NetworkTopology()
    routers = [add_device(topo, rng, DeviceType.ROUTER, f"r{i}", 2) for i in range(24)]
    for i in range(23):
        net = IPv4Network(f"10.{i}.0.0/30")
        topo.add_subnet(Subnet(topo.next_subnet_id(), net))
        topo.assign_address(routers[i].id, "ge0/1", IPv4Interface(f"10.{i}.0.1/30"))
        topo.assign_address(routers[i + 1].id, "ge0/0", IPv4Interface(f"10.{i}.0.2/30"))
        topo.connect(
            InterfaceRef(routers[i].id, "ge0/1"),
            InterfaceRef(routers[i + 1].id, "ge0/0"),
        )
    for i in range(23):
        topo.get_router(routers[i].id).add_static_route(
            RoutingEntry(
                0,
                IPv4Network("0.0.0.0/0"),
                IPv4Address(f"10.{i}.0.2"),
                "ge0/1",
                RouteType.DEFAULT,
                1,
            )
        )
    engine = engine_factory(topo)
    start = time.perf_counter()
    result = engine.simulate(request_for(topo, "r0", "10.22.0.2"))
    elapsed = time.perf_counter() - start
    assert result.delivered
    assert elapsed < 0.05
