"""NETWORK_SPEC §10 — traffic and utilization (T-110)."""

from __future__ import annotations

from ipaddress import IPv4Address

import pytest

from netcore.domain.enums import Direction, DropReason
from netcore.domain.errors import InvalidValueError
from netcore.domain.simulation.traffic import (
    TrafficFlow,
    TrafficGenerator,
    counter_events,
    utilization_pct,
)


def test_utilization_formula():
    assert utilization_pct(500, 1000) == 50.0
    assert utilization_pct(1500, 1000) == 100.0
    assert utilization_pct(1, 3) == 33.3
    assert utilization_pct(5, 0) == 0.0


def test_flow_validation():
    with pytest.raises(InvalidValueError):
        TrafficFlow(1, IPv4Address("10.0.0.1"), packets_per_second=0)  # type: ignore[arg-type]
    with pytest.raises(InvalidValueError):
        TrafficFlow(1, IPv4Address("10.0.0.1"), duration_s=0)  # type: ignore[arg-type]
    with pytest.raises(InvalidValueError):
        TrafficFlow(1, IPv4Address("10.0.0.1"), packet_size=10)  # type: ignore[arg-type]


def _flow(topo, pps, size=1000):
    return TrafficFlow(
        topo.require("srv-a").id,
        IPv4Address("10.0.2.10"),
        packet_size=size,
        packets_per_second=pps,
        duration_s=10,
    )


def test_flow_accounts_path_without_congestion(
    two_router_lab, engine_factory, fixed_now
):
    topo = two_router_lab
    gen = TrafficGenerator()
    flow = _flow(topo, 1000)  # 8 Mbps
    report = gen.run(flow, topo, engine_factory(topo), fixed_now)
    assert report.delivered_packets == 10_000
    assert report.congestion_drops == 0
    link = topo.links()[0]
    capacity_before = link.capacity_mbps
    assert gen.utilization(link, [report]) == 0.8
    assert link.capacity_mbps == capacity_before
    loads = gen.load_by_direction([report])
    assert all(v == pytest.approx(8.0) for v in loads.values())


def test_congestion_drops(two_router_lab, engine_factory, fixed_now):
    topo = two_router_lab
    gen = TrafficGenerator()
    flow = _flow(topo, 100_000, 2000)  # 1600 Mbps on 1000 Mbps links
    report = gen.run(flow, topo, engine_factory(topo), fixed_now)
    assert report.congestion_drops == round(1_000_000 * (600 / 1600))
    assert gen.utilization(topo.links()[0], [report]) == 100.0
    drops = [e for e in report.events if e.dropped]
    assert drops
    assert drops[0].drop_reason is DropReason.CONGESTION


def test_undelivered_flow_counts_drops(two_router_lab, engine_factory, fixed_now):
    topo = two_router_lab
    topo.links()[2].set_admin(False)
    report = TrafficGenerator().run(
        _flow(topo, 10), topo, engine_factory(topo), fixed_now
    )
    assert report.dropped_packets == 100
    assert TrafficGenerator().utilization(topo.links()[0], [report]) == 0.0


def test_counter_events_directions(
    two_router_lab, engine_factory, request_for, fixed_now
):
    topo = two_router_lab
    result = engine_factory(topo).simulate(request_for(topo, "srv-a", "10.0.2.10"))
    events = counter_events(result, 1, 64, fixed_now)
    link_events = [e for e in events if e.link_id is not None]
    assert len(link_events) == 5
    assert {e.direction for e in link_events} <= {Direction.A_TO_B, Direction.B_TO_A}
    arp = [e for e in events if e.packets == 6]
    assert arp  # 3 ARP exchanges x 2 frames
