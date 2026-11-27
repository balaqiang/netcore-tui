"""Application services (T-302, T-303) over fake UoW and in-memory SQLite."""

from __future__ import annotations

import pytest

from netcore.application.dto import (
    AddRouteRequest,
    AssignAddressRequest,
    ConnectRequest,
    CreateDeviceRequest,
    CreateSubnetRequest,
    DeviceFilter,
    DeviceStatus,
    DeviceType,
    DropReason,
    EventCategory,
    EventFilterDTO,
    RouteType,
    SendPacketRequest,
    Severity,
    SimulationStatus,
    StartFlowRequest,
    UpdateDeviceRequest,
    UpdatePortRequest,
    UpdateSettingsRequest,
)
from netcore.application.errors import ApplicationError
from tests.unit.application.conftest import dev_id


# ------------------------------------------------------------------ devices
def test_create_list_filter_device(services):
    created = services.devices.create_device(
        CreateDeviceRequest("core-r1", DeviceType.ROUTER, location="rack-1")
    )
    assert created.interface_count == 4
    assert created.interfaces[0].name == "ge0/0"
    assert created.interfaces[0].mac.startswith("02:")
    services.devices.create_device(CreateDeviceRequest("sw-01", DeviceType.SWITCH))
    assert len(services.devices.list_devices()) == 2
    only = services.devices.list_devices(DeviceFilter(device_type=DeviceType.SWITCH))
    assert [d.hostname for d in only] == ["sw-01"]
    assert (
        services.devices.list_devices(DeviceFilter(text="rack-1"))[0].hostname
        == "core-r1"
    )


def test_duplicate_hostname_maps_code(services):
    services.devices.create_device(CreateDeviceRequest("a1", DeviceType.SERVER))
    with pytest.raises(ApplicationError) as exc:
        services.devices.create_device(CreateDeviceRequest("A1", DeviceType.SERVER))
    assert exc.value.code == "NET007"
    assert exc.value.kind == "conflict"


def test_invalid_interface_count(services):
    with pytest.raises(ApplicationError) as exc:
        services.devices.create_device(CreateDeviceRequest("s", DeviceType.SWITCH, 97))
    assert exc.value.code == "NET022"


def test_update_and_status_cycle(lab):
    srv = dev_id(lab, "srv-a")
    dto = lab.devices.update_device(
        UpdateDeviceRequest(
            srv, hostname="web-01", description="web", default_gateway=""
        )
    )
    assert dto.hostname == "web-01" and dto.default_gateway is None
    with pytest.raises(ApplicationError):
        lab.devices.update_device(UpdateDeviceRequest(srv, default_gateway="10.9.9.9"))
    r1 = dev_id(lab, "r1")
    with pytest.raises(ApplicationError):
        lab.devices.update_device(UpdateDeviceRequest(r1, default_gateway="10.0.1.1"))
    assert lab.devices.cycle_status(r1).status is DeviceStatus.OFFLINE
    assert lab.devices.cycle_status(r1).status is DeviceStatus.MAINTENANCE
    assert lab.devices.cycle_status(r1).status is DeviceStatus.ONLINE
    events = lab.events.query(EventFilterDTO(category=EventCategory.STATE))
    assert len(events) == 3


def test_delete_device_with_preview(lab):
    r2 = dev_id(lab, "r2")
    preview = lab.devices.removal_preview(r2)
    assert len(preview.removed_links) == 2
    assert dev_id(lab, "r2") == r2  # preview did not delete
    report = lab.devices.delete_device(r2)
    assert report.hostname == "r2"
    assert all(d.hostname != "r2" for d in lab.devices.list_devices())
    with pytest.raises(ApplicationError) as exc:
        lab.devices.get_device(r2)
    assert exc.value.kind == "not_found"


def test_arp_table_and_clear(lab):
    srv = dev_id(lab, "srv-a")
    lab.simulation.send_packet(SendPacketRequest(srv, "10.0.2.10"))
    entries = lab.devices.arp_table(srv)
    assert [e.ip for e in entries] == ["10.0.1.1"]
    lab.devices.clear_arp(srv)
    assert lab.devices.arp_table(srv) == []
    with pytest.raises(ApplicationError):
        lab.devices.clear_arp(dev_id(lab, "sw-a"))


def test_interface_admin(lab):
    srv = dev_id(lab, "srv-a")
    dto = lab.devices.set_interface_admin(srv, "eth0", False)
    assert not dto.interfaces[0].admin_up
    result = lab.simulation.send_packet(SendPacketRequest(srv, "10.0.2.10"))
    assert result.drop_reason is DropReason.NO_INTERFACE


# --------------------------------------------------------------------- IPAM
def test_ipam_flow(services):
    subnet = services.ipam.create_subnet(
        CreateSubnetRequest("10.5.0.0/24", "lab", "10.5.0.1")
    )
    assert subnet.total == 254 and subnet.used == 0
    srv = services.devices.create_device(CreateDeviceRequest("h1", DeviceType.SERVER))
    suggestion = services.ipam.next_free_address(subnet.id)
    assert suggestion == "10.5.0.2/24"
    iface = services.ipam.assign_address(
        AssignAddressRequest(srv.id, "eth0", "10.5.0.2")
    )
    assert iface.address == "10.5.0.2/24"
    assert services.ipam.list_subnets()[0].used == 1
    assert services.ipam.addresses(subnet.id)[0].device_name == "h1"
    with pytest.raises(ApplicationError) as exc:
        services.ipam.assign_address(
            AssignAddressRequest(srv.id, "eth1", "10.5.0.2/24")
        )
    assert exc.value.code == "NET005"
    with pytest.raises(ApplicationError) as exc:
        services.ipam.assign_address(
            AssignAddressRequest(srv.id, "eth1", "10.0.0.256/24")
        )
    assert exc.value.code == "NET001"
    with pytest.raises(ApplicationError) as exc:
        services.ipam.delete_subnet(subnet.id)
    assert exc.value.code == "NET020"
    services.ipam.release_address(srv.id, "eth0")
    services.ipam.delete_subnet(subnet.id)
    assert services.ipam.list_subnets() == []


def test_subnet_errors_and_public_warning(services):
    with pytest.raises(ApplicationError) as exc:
        services.ipam.create_subnet(CreateSubnetRequest("10.0.1.5/24"))
    assert exc.value.code == "NET002"
    services.ipam.create_subnet(CreateSubnetRequest("10.0.0.0/16"))
    with pytest.raises(ApplicationError) as exc:
        services.ipam.create_subnet(CreateSubnetRequest("10.0.1.0/24"))
    assert exc.value.code == "NET008"
    services.ipam.create_subnet(CreateSubnetRequest("8.8.8.0/24"))
    warnings = services.events.query(
        EventFilterDTO(severities=frozenset({Severity.WARNING}))
    )
    assert any("public range" in e.message for e in warnings)


# ------------------------------------------------------------------ routing
def test_routing_service(lab):
    r1 = dev_id(lab, "r1")
    assert (r1, "r1") in lab.routing.routers()
    routes = lab.routing.routes(r1)
    assert {r.type_code for r in routes} == {"C", "S"}
    added = lab.routing.add_static_route(AddRouteRequest(r1, "0.0.0.0/0", "10.0.12.2"))
    assert added.route_type is RouteType.DEFAULT and added.interface == "ge0/0"
    lookup = lab.routing.lookup(r1, "8.8.8.8")
    assert lookup.matched is not None and "prefix /0" in lookup.message
    assert lab.routing.lookup(r1, "10.0.2.7").matched.destination == "10.0.2.0/24"
    with pytest.raises(ApplicationError) as exc:
        lab.routing.add_static_route(AddRouteRequest(r1, "10.9.0.0/16", "172.16.0.1"))
    assert exc.value.code == "NET009"
    with pytest.raises(ApplicationError) as exc:
        lab.routing.add_static_route(AddRouteRequest(r1, "0.0.0.0/0", "10.0.12.2"))
    assert exc.value.code == "NET010"
    connected = next(r for r in lab.routing.routes(r1) if not r.removable)
    with pytest.raises(ApplicationError):
        lab.routing.remove_route(r1, connected.id)
    lab.routing.remove_route(r1, added.id)
    assert lab.routing.lookup(r1, "8.8.8.8").matched is None


# ---------------------------------------------------------------- switching
def test_switch_service(lab):
    sw = dev_id(lab, "sw-a")
    assert lab.switches.switches()[0][1] == "sw-a"
    ports = lab.switches.ports(sw)
    assert len(ports) == 24 and ports[0].peer == "srv-a:eth0"
    lab.simulation.send_packet(SendPacketRequest(dev_id(lab, "srv-a"), "10.0.2.10"))
    assert {e.port for e in lab.switches.mac_table(sw)} == {1, 24}
    assert lab.switches.ports(sw)[0].rx_packets >= 1
    down = lab.switches.set_port_admin(sw, 1, False)
    assert not down.admin_up and not down.operational
    edited = lab.switches.update_port(
        UpdatePortRequest(sw, 2, speed_mbps=10000, description="uplink")
    )
    assert edited.speed_mbps == 10000 and edited.description == "uplink"
    with pytest.raises(ApplicationError) as exc:
        lab.switches.set_port_admin(sw, 99, False)
    assert exc.value.code == "NET011"
    lab.switches.clear_mac_table(sw)
    assert lab.switches.mac_table(sw) == []


# ----------------------------------------------------------------- topology
def test_topology_service(lab):
    snap = lab.topology.snapshot()
    assert len(snap.nodes) == 6 and len(snap.links) == 5
    link = snap.links[2]
    assert lab.topology.set_link_admin(link.id, False).admin_up is False
    result = lab.simulation.send_packet(
        SendPacketRequest(dev_id(lab, "srv-a"), "10.0.2.10")
    )
    assert result.drop_reason is DropReason.LINK_DOWN
    assert lab.topology.snapshot().last_path == result.path_ids
    lab.topology.disconnect(link.id)
    r1, r2 = dev_id(lab, "r1"), dev_id(lab, "r2")
    assert "ge0/0" in lab.topology.free_interfaces(r1)
    new = lab.topology.connect(ConnectRequest(r1, "ge0/0", r2, "ge0/0", 10000))
    assert new.capacity_mbps == 10000 and new.operational
    with pytest.raises(ApplicationError) as exc:
        lab.topology.connect(ConnectRequest(r1, "ge0/0", r2, "ge0/2"))
    assert exc.value.code == "NET012"


def test_switch_loop_warning(services):
    a = services.devices.create_device(CreateDeviceRequest("s1", DeviceType.SWITCH, 4))
    b = services.devices.create_device(CreateDeviceRequest("s2", DeviceType.SWITCH, 4))
    services.topology.connect(ConnectRequest(a.id, "port1", b.id, "port1"))
    services.topology.connect(ConnectRequest(a.id, "port2", b.id, "port2"))
    assert any("loop" in e.message for e in services.events.query())


# --------------------------------------------------------------- simulation
def test_send_packet_and_history(lab):
    received = []
    lab.bus.subscribe(EventCategory.DELIVERY, received.append)
    src = dev_id(lab, "srv-a")
    result = lab.simulation.send_packet(SendPacketRequest(src, "10.0.2.10"))
    assert result.status is SimulationStatus.DELIVERED
    assert result.path_names == ("srv-a", "sw-a", "r1", "r2", "sw-b", "srv-b")
    assert result.ttl_start == 64 and result.ttl_end == 62
    assert "DELIVERED" in result.summary
    assert len(received) == 1
    dropped = lab.simulation.send_packet(SendPacketRequest(src, "10.0.2.10", ttl=1))
    assert dropped.drop_reason is DropReason.TTL_EXPIRED
    assert dropped.drop_device == "r1"
    assert "TTL_EXPIRED at r1" in dropped.summary
    history = lab.simulation.history()
    assert [h.status for h in history] == [
        SimulationStatus.DROPPED,
        SimulationStatus.DELIVERED,
    ]
    replay = lab.simulation.replay(history[1].run_id)
    assert replay is not None and replay.status is SimulationStatus.DELIVERED
    assert lab.simulation.replay(9999) is None
    assert lab.events.query(EventFilterDTO(category=EventCategory.FORWARD))


def test_send_packet_errors(lab):
    with pytest.raises(ApplicationError) as exc:
        lab.simulation.send_packet(SendPacketRequest(dev_id(lab, "sw-a"), "10.0.2.10"))
    assert exc.value.code == "NET014"
    with pytest.raises(ApplicationError) as exc:
        lab.simulation.send_packet(SendPacketRequest(dev_id(lab, "srv-a"), "10.0.2"))
    assert exc.value.code == "NET001"
    with pytest.raises(ApplicationError):
        lab.simulation.send_packet(
            SendPacketRequest(dev_id(lab, "srv-a"), "10.0.2.10", ttl=0)
        )


def test_arp_failure_event(lab):
    lab.simulation.send_packet(SendPacketRequest(dev_id(lab, "srv-a"), "10.0.1.77"))
    arp = lab.events.query(EventFilterDTO(category=EventCategory.ARP))
    assert any(e.severity is Severity.WARNING for e in arp)


def test_traceroute(lab):
    tr = lab.simulation.traceroute(SendPacketRequest(dev_id(lab, "srv-a"), "10.0.2.10"))
    assert tr.reached
    assert [h.device_name for h in tr.hops] == ["r1", "r2", "srv-b"]


# --------------------------------------------------------------- monitoring
def test_flows_and_stats(lab, clock):
    src = dev_id(lab, "srv-a")
    flow = lab.monitoring.start_flow(
        StartFlowRequest(
            src, "10.0.2.10", packet_size=1000, packets_per_second=25_000, duration_s=10
        )
    )
    assert flow.delivered and flow.load_mbps == 200.0
    stats = lab.monitoring.link_stats()
    assert all(s.capacity_mbps == 1000 for s in stats)
    assert max(s.utilization_pct for s in stats) == 20.0
    assert lab.monitoring.flows()[0].remaining_s == 10
    big = lab.monitoring.start_flow(
        StartFlowRequest(
            src, "10.0.2.10", packet_size=2000, packets_per_second=60_000, duration_s=5
        )
    )
    assert big.congestion_drops > 0
    talkers = lab.monitoring.device_stats()
    assert talkers[0].tx_packets + talkers[0].rx_packets > 0
    assert any(d.top_drop_reason == "CONGESTION" for d in talkers)
    dash = lab.monitoring.dashboard_summary()
    assert dash.device_total == 6 and dash.online == 6 and dash.links_up == 5
    assert dash.top_links[0].utilization_pct == 100.0
    assert dash.warnings_1h >= 1
    assert dash.lab_name == "two-router"
    lab.monitoring.stop_flow(big.flow_id)
    with pytest.raises(ApplicationError):
        lab.monitoring.stop_flow(big.flow_id)
    clock.advance(11)
    assert lab.monitoring.flows() == []
    assert max(s.utilization_pct for s in lab.monitoring.link_stats()) == 0.0
    lab.monitoring.reset_counters()
    assert lab.monitoring.counters_snapshot() == {}


def test_undeliverable_flow(lab):
    lab.devices.set_status(dev_id(lab, "r2"), DeviceStatus.OFFLINE)
    flow = lab.monitoring.start_flow(
        StartFlowRequest(dev_id(lab, "srv-a"), "10.0.2.10")
    )
    assert not flow.delivered and flow.drop_reason is DropReason.DEVICE_OFFLINE
    assert lab.monitoring.flows() == []


# ------------------------------------------------------------------- events
def test_event_filters_and_export(lab, tmp_path):
    lab.devices.set_status(dev_id(lab, "r1"), DeviceStatus.OFFLINE)
    warn = lab.events.query(EventFilterDTO(severities=frozenset({Severity.WARNING})))
    assert warn and warn[0].device_name == "r1"
    assert lab.events.query(EventFilterDTO(text="lab two-router", window="15m"))
    assert lab.events.query(EventFilterDTO(device_id=dev_id(lab, "r1")))
    with pytest.raises(ApplicationError):
        lab.events.query(EventFilterDTO(window="2d"))
    out = tmp_path / "events.csv"
    res = lab.events.export(EventFilterDTO(), "csv", str(out))
    assert res.count >= 2 and out.read_text().startswith("id,timestamp")
    with pytest.raises(ApplicationError) as exc:
        lab.events.export(EventFilterDTO(), "csv", str(out))
    assert exc.value.kind == "conflict"
    lab.events.export(EventFilterDTO(), "json", str(out), overwrite=True)
    assert out.read_text().startswith("[")
    with pytest.raises(ApplicationError):
        lab.events.export(EventFilterDTO(), "xml", str(tmp_path / "x"))
    with pytest.raises(ApplicationError):
        lab.events.export(EventFilterDTO(), "csv", str(tmp_path / "missing" / "x.csv"))


# ----------------------------------------------------------------- settings
def test_settings_service(services):
    s = services.settings.get()
    assert s.default_ttl == 64 and s.max_hops == 64 and s.lab_name == "empty-lab"
    s = services.settings.update(UpdateSettingsRequest(default_ttl=32, seed=7))
    assert s.default_ttl == 32 and s.seed == 7
    with pytest.raises(ApplicationError):
        services.settings.update(UpdateSettingsRequest(max_hops=3))
    assert services.settings.sample_labs() == ["spine-leaf", "two-router"]
    services.settings.load_sample_lab("spine-leaf")
    assert len(services.devices.list_devices()) == 18
    assert services.settings.get().lab_name == "spine-leaf"
    with pytest.raises(ApplicationError):
        services.settings.load_sample_lab("nope")
    services.settings.reset_lab()
    assert services.settings.lab_is_empty()


def test_default_ttl_from_settings(lab):
    lab.settings.update(UpdateSettingsRequest(default_ttl=2))
    r = lab.simulation.send_packet(SendPacketRequest(dev_id(lab, "srv-a"), "10.0.2.10"))
    assert r.drop_reason is DropReason.TTL_EXPIRED and r.drop_device == "r2"


def test_event_retention(services):
    services.settings.update(UpdateSettingsRequest(event_retention=100))
    for i in range(110):
        services.devices.create_device(
            CreateDeviceRequest(f"h{i}", DeviceType.SERVER, 1)
        )
    assert len(services.events.query(EventFilterDTO(limit=10_000))) == 100
