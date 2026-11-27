"""Persistence integration tests (T-201..T-204), in-memory SQLite."""

from __future__ import annotations

import random
from datetime import timedelta
from ipaddress import IPv4Address

import pytest

from netcore.application.ports import EventFilter
from netcore.domain.enums import (
    DeviceStatus,
    Direction,
    DropReason,
    EventCategory,
    Severity,
)
from netcore.domain.events import NetworkEvent, TrafficEvent
from netcore.domain.ids import DeviceId
from netcore.domain.labs import build_spine_leaf_lab
from netcore.domain.simulation.result import PacketRequest
from netcore.domain.topology import NetworkTopology
from netcore.infrastructure.persistence.connection import ConnectionFactory
from netcore.infrastructure.persistence.migrator import Migrator
from netcore.infrastructure.persistence.unit_of_work import SqliteUnitOfWork


def snapshot(topo: NetworkTopology) -> dict:
    """Canonical comparable view of a topology."""
    devices = {}
    for d in topo.devices():
        devices[d.id] = {
            "hostname": d.hostname,
            "type": d.device_type,
            "status": d.status,
            "location": d.location,
            "interfaces": [
                (i.name, i.mac, i.address, i.admin_up, i.link_id, i.description)
                for i in d.interfaces()
            ],
            "routes": [
                (e.describe(), e.route_type, e.admin_distance, e.metric)
                for e in getattr(d, "routing_table", None).entries()
            ]
            if hasattr(d, "routing_table")
            else None,
            "gateway": getattr(d, "default_gateway", None),
        }
    return {
        "devices": devices,
        "links": [
            (lk.id, lk.endpoint_a, lk.endpoint_b, lk.capacity_mbps, lk.admin_up)
            for lk in topo.links()
        ],
        "subnets": [
            (s.id, s.network, s.name, s.gateway, s.parent_id) for s in topo.subnets()
        ],
    }


@pytest.fixture
def factory():
    f = ConnectionFactory(":memory:")
    Migrator(f.connect()).migrate()
    yield f
    f.close()


def test_migrator_idempotent(factory):
    conn = factory.connect()
    assert Migrator(conn).migrate() == []
    assert Migrator(conn).applied() == {1}
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"devices", "interfaces", "links", "routes", "events", "settings"} <= tables
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_at11_round_trip(factory, two_router_lab, engine_factory, request_for):
    """AT-11 — save lab, reopen DB, topology and routes are equal."""
    engine_factory(two_router_lab).simulate(
        request_for(two_router_lab, "srv-a", "10.0.2.10")
    )
    two_router_lab.require("r2").set_status(DeviceStatus.MAINTENANCE)
    two_router_lab.links()[0].set_admin(False)
    with SqliteUnitOfWork(factory) as uow:
        uow.topology.save(two_router_lab)
    with SqliteUnitOfWork(factory) as uow:
        loaded = uow.topology.load()
    assert snapshot(loaded) == snapshot(two_router_lab)
    r1 = loaded.get_router(loaded.require("r1").id)
    assert len(r1.arp_table.entries()) == 2
    sw = loaded.get_switch(loaded.require("sw-a").id)
    assert len(sw.mac_table.entries()) == 2


def test_file_database_round_trip(tmp_path, two_router_lab):
    """AT-11 against a real file (reopen = new factory)."""
    db = tmp_path / "lab.db"
    f1 = ConnectionFactory(db)
    Migrator(f1.connect()).migrate()
    with SqliteUnitOfWork(f1) as uow:
        uow.topology.save(two_router_lab)
    f2 = ConnectionFactory(db)
    with SqliteUnitOfWork(f2) as uow:
        loaded = uow.topology.load()
    assert snapshot(loaded) == snapshot(two_router_lab)


def test_save_prunes_removed_entities(factory, two_router_lab):
    with SqliteUnitOfWork(factory) as uow:
        uow.topology.save(two_router_lab)
    two_router_lab.remove_device(two_router_lab.require("srv-b").id)
    with SqliteUnitOfWork(factory) as uow:
        uow.topology.save(two_router_lab)
    with SqliteUnitOfWork(factory) as uow:
        loaded = uow.topology.load()
    assert loaded.find_by_hostname("srv-b") is None
    assert snapshot(loaded) == snapshot(two_router_lab)


def test_rollback_on_exception(factory, two_router_lab):
    with pytest.raises(RuntimeError), SqliteUnitOfWork(factory) as uow:
        uow.topology.save(two_router_lab)
        raise RuntimeError("boom")
    with SqliteUnitOfWork(factory) as uow:
        assert uow.topology.load().devices() == ()


def test_events_query_and_prune(factory, fixed_now):
    with SqliteUnitOfWork(factory) as uow:
        for i in range(10):
            uow.events.add(
                NetworkEvent(
                    timestamp=fixed_now + timedelta(seconds=i),
                    severity=Severity.WARNING if i % 2 else Severity.INFO,
                    category=EventCategory.CONFIG,
                    message=f"event 100%_{i}",
                    device_id=DeviceId(999),  # unknown device -> stored as NULL
                    payload={"i": i},
                )
            )
    with SqliteUnitOfWork(factory) as uow:
        warn = uow.events.query(EventFilter(severities=frozenset({Severity.WARNING})))
        assert len(warn) == 5
        assert warn[0].payload == {"i": 9}
        assert warn[0].device_id is None
        assert len(uow.events.query(EventFilter(text="100%_3"))) == 1
        assert (
            len(uow.events.query(EventFilter(since=fixed_now + timedelta(seconds=8))))
            == 2
        )
        assert uow.events.prune(3) == 7
        assert len(uow.events.query(EventFilter())) == 3
        uow.events.clear()
        assert uow.events.query(EventFilter()) == []


def test_simulation_history(factory, two_router_lab, engine_factory, request_for):
    result = engine_factory(two_router_lab).simulate(
        request_for(two_router_lab, "srv-a", "10.0.2.10")
    )
    with SqliteUnitOfWork(factory) as uow:
        uow.topology.save(two_router_lab)
        run_id = uow.simulations.add(result)
    with SqliteUnitOfWork(factory) as uow:
        runs = uow.simulations.recent(5)
    assert runs[0].run_id == run_id
    assert runs[0].status is result.status
    assert runs[0].hops == result.hops
    assert runs[0].path == result.path
    assert isinstance(runs[0].request, PacketRequest)


def test_traffic_counters(factory, two_router_lab, fixed_now):
    with SqliteUnitOfWork(factory) as uow:
        uow.topology.save(two_router_lab)
    dev = two_router_lab.require("r1").id
    link = two_router_lab.links()[0].id
    evs = [
        TrafficEvent(
            timestamp=fixed_now,
            severity=Severity.DEBUG,
            category=EventCategory.TRAFFIC,
            message="x",
            device_id=dev,
            direction=Direction.TX,
            packets=5,
            bytes=500,
        ),
        TrafficEvent(
            timestamp=fixed_now,
            severity=Severity.DEBUG,
            category=EventCategory.TRAFFIC,
            message="x",
            device_id=dev,
            direction=Direction.TX,
            packets=1,
            bytes=100,
            dropped=2,
            drop_reason=DropReason.CONGESTION,
        ),
        TrafficEvent(
            timestamp=fixed_now,
            severity=Severity.DEBUG,
            category=EventCategory.TRAFFIC,
            message="x",
            link_id=link,
            direction=Direction.A_TO_B,
            packets=3,
            bytes=300,
        ),
    ]
    with SqliteUnitOfWork(factory) as uow:
        uow.traffic.apply(evs)
    with SqliteUnitOfWork(factory) as uow:
        counters = uow.traffic.counters()
        row = counters[(dev, None, Direction.TX)]
        assert (row.packets, row.bytes, row.dropped) == (6, 600, 2)
        assert row.drop_reasons == {DropReason.CONGESTION: 2}
        assert counters[(None, link, Direction.A_TO_B)].packets == 3
        uow.traffic.reset()
        assert uow.traffic.counters() == {}


def test_settings(factory):
    with SqliteUnitOfWork(factory) as uow:
        uow.settings.set_many({"default_ttl": "32", "seed": "7"})
        uow.settings.set_many({"default_ttl": "16"})
    with SqliteUnitOfWork(factory) as uow:
        assert uow.settings.get_all() == {"default_ttl": "16", "seed": "7"}


def test_spine_leaf_seed_all_pairs_delivered(factory, engine_factory):
    """T-204 — packet between any two servers is DELIVERED (after reload)."""
    with SqliteUnitOfWork(factory) as uow:
        uow.topology.save(build_spine_leaf_lab(random.Random(9)))
    with SqliteUnitOfWork(factory) as uow:
        topo = uow.topology.load()
    servers = [d for d in topo.devices() if d.hostname.startswith("srv")]
    assert len(servers) == 8
    engine = engine_factory(topo)
    for a in servers:
        for b in servers:
            if a is b:
                continue
            ip = b.addressed_interfaces()[0].address.ip
            assert engine.simulate(PacketRequest(a.id, ip)).delivered, (a, b)
    assert IPv4Address("10.0.1.11") in {
        s.addressed_interfaces()[0].address.ip for s in servers
    }


def test_nfr02_large_lab_load_under_one_second(factory, rng):
    """NFR-02 — 200 devices / 400 links load in < 1 s."""
    import time

    from netcore.domain.enums import DeviceType
    from netcore.domain.interface import InterfaceRef
    from netcore.domain.labs import add_device

    topo = NetworkTopology()
    switches = [
        add_device(topo, rng, DeviceType.SWITCH, f"sw{i}", 48) for i in range(10)
    ]
    servers = [add_device(topo, rng, DeviceType.SERVER, f"h{i}", 2) for i in range(190)]
    links = 0
    for idx, srv in enumerate(servers):
        sw = switches[idx % 10]
        for nic in (0, 1):
            port = (idx // 10) * 2 + nic + 1
            topo.connect(
                InterfaceRef(srv.id, f"eth{nic}"), InterfaceRef(sw.id, f"port{port}")
            )
            links += 1
    for i in range(9):
        topo.connect(
            InterfaceRef(switches[i].id, "port48"),
            InterfaceRef(switches[i + 1].id, "port47"),
        )
        links += 1
    assert len(topo.devices()) == 200 and links >= 389
    with SqliteUnitOfWork(factory) as uow:
        uow.topology.save(topo)
    start = time.perf_counter()
    with SqliteUnitOfWork(factory) as uow:
        loaded = uow.topology.load()
    elapsed = time.perf_counter() - start
    assert len(loaded.links()) == links
    assert elapsed < 1.0
