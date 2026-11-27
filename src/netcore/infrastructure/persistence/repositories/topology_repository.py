"""SqliteTopologyRepository — whole-aggregate load/save (DEC-008)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.router import Router
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import Switch, port_number
from netcore.domain.enums import DeviceStatus, DeviceType
from netcore.domain.ids import DeviceId, LinkId
from netcore.domain.interface import InterfaceRef, NetworkInterface
from netcore.domain.topology import NetworkTopology
from netcore.infrastructure.persistence.mappers import (
    arp_from_row,
    interface_from_row,
    ip_or_none,
    mac_entry_from_row,
    route_from_row,
    subnet_from_row,
    ts,
)


class SqliteTopologyRepository:
    """Persists the full topology with upsert + prune (keeps event FKs)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ----------------------------------------------------------------- load
    def load(self) -> NetworkTopology:
        """Rebuild the aggregate from all tables."""
        conn = self._conn
        topo = NetworkTopology()
        subnet_rows = conn.execute("SELECT * FROM subnets").fetchall()
        subnets = sorted(
            (subnet_from_row(r) for r in subnet_rows),
            key=lambda s: s.network.prefixlen,
        )
        for subnet in subnets:
            topo.add_subnet(subnet)

        iface_rows: dict[int, list[sqlite3.Row]] = {}
        for row in conn.execute(
            "SELECT * FROM interfaces ORDER BY device_id, position"
        ):
            iface_rows.setdefault(row["device_id"], []).append(row)

        for row in conn.execute("SELECT * FROM devices ORDER BY id"):
            rows = iface_rows.get(row["id"], [])
            topo.add_device(self._device_from_rows(row, rows))

        routes: dict[int, list[sqlite3.Row]] = {}
        for row in conn.execute(
            "SELECT * FROM routes ORDER BY device_id, insertion_index"
        ):
            routes.setdefault(row["device_id"], []).append(row)
        for device_id, rows in routes.items():
            router = topo.get_router(DeviceId(device_id))
            for r in rows:
                router.routing_table.add(route_from_row(r))

        for row in conn.execute("SELECT * FROM arp_entries ORDER BY id"):
            cache = topo.get_device(DeviceId(row["device_id"])).arp_cache()
            if cache is not None:
                cache.restore(arp_from_row(row))
        for row in conn.execute("SELECT * FROM mac_entries ORDER BY id"):
            topo.get_switch(DeviceId(row["device_id"])).mac_table.restore(
                mac_entry_from_row(row)
            )

        link_sql = (
            "SELECT l.*, ia.device_id AS a_dev, ia.name AS a_name, "
            "ib.device_id AS b_dev, ib.name AS b_name FROM links l "
            "JOIN interfaces ia ON ia.id = l.interface_a_id "
            "JOIN interfaces ib ON ib.id = l.interface_b_id ORDER BY l.id"
        )
        for row in conn.execute(link_sql):
            topo.connect(
                InterfaceRef(DeviceId(row["a_dev"]), row["a_name"]),
                InterfaceRef(DeviceId(row["b_dev"]), row["b_name"]),
                row["capacity_mbps"],
                row["latency_ms"],
                LinkId(row["id"]),
                bool(row["admin_up"]),
            )
        return topo

    @staticmethod
    def _device_from_rows(row: sqlite3.Row, rows: list[sqlite3.Row]) -> NetworkDevice:
        ifaces: list[NetworkInterface] = [interface_from_row(r) for r in rows]
        dtype = DeviceType(row["device_type"])
        status = DeviceStatus(row["status"])
        location: str = row["location"]
        description: str = row["description"]
        did = DeviceId(row["id"])
        name: str = row["hostname"]
        if dtype is DeviceType.ROUTER:
            return Router(did, name, ifaces, status, location, description)
        if dtype is DeviceType.SWITCH:
            speeds = {
                r["port_number"]: r["speed_mbps"]
                for r in rows
                if r["port_number"] is not None and r["speed_mbps"] is not None
            }
            return Switch(did, name, ifaces, status, location, description, speeds)
        server = Server(did, name, ifaces, status, location, description)
        server.restore_gateway(ip_or_none(row["default_gateway"]))
        return server

    def clear(self) -> None:
        """Delete every lab row (events are kept; their device ids nulled)."""
        for table in (
            "traffic_counters",
            "links",
            "routes",
            "arp_entries",
            "mac_entries",
            "interfaces",
            "devices",
        ):
            self._conn.execute(f"DELETE FROM {table}")
        while self._conn.execute("SELECT COUNT(*) FROM subnets").fetchone()[0]:
            self._conn.execute(
                "DELETE FROM subnets WHERE id NOT IN "
                "(SELECT parent_id FROM subnets WHERE parent_id IS NOT NULL)"
            )

    # ----------------------------------------------------------------- save
    def save(self, topology: NetworkTopology) -> None:
        """Upsert current state and prune removed rows."""
        conn = self._conn
        now = ts(datetime.now(UTC))
        link_ids = {link.id for link in topology.links()}
        device_ids = {d.id for d in topology.devices()}
        subnet_ids = {s.id for s in topology.subnets()}

        existing_links = {r[0] for r in conn.execute("SELECT id FROM links")}
        conn.executemany(
            "DELETE FROM links WHERE id = ?", [(i,) for i in existing_links - link_ids]
        )
        existing_devices = {r[0] for r in conn.execute("SELECT id FROM devices")}
        conn.executemany(
            "DELETE FROM devices WHERE id = ?",
            [(i,) for i in existing_devices - device_ids],
        )
        removed_subnets = conn.execute("SELECT id, cidr FROM subnets").fetchall()
        doomed = sorted(
            (r for r in removed_subnets if r["id"] not in subnet_ids),
            key=lambda r: -int(r["cidr"].split("/")[1]),
        )
        for r in doomed:
            conn.execute("DELETE FROM subnets WHERE id = ?", (r["id"],))

        for subnet in sorted(topology.subnets(), key=lambda s: s.network.prefixlen):
            conn.execute(
                "INSERT INTO subnets(id, cidr, name, gateway, parent_id) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "cidr=excluded.cidr, name=excluded.name, gateway=excluded.gateway, "
                "parent_id=excluded.parent_id",
                (
                    subnet.id,
                    str(subnet.network),
                    subnet.name,
                    str(subnet.gateway) if subnet.gateway else None,
                    subnet.parent_id,
                ),
            )

        conn.execute("UPDATE interfaces SET ip_address = NULL, prefix_len = NULL")
        for device in topology.devices():
            self._save_device(topology, device, now)

        iface_ids = {
            (r["device_id"], r["name"]): r["id"]
            for r in conn.execute("SELECT id, device_id, name FROM interfaces")
        }
        for link in topology.links():
            a, b = link.endpoint_a, link.endpoint_b
            conn.execute(
                "INSERT INTO links(id, interface_a_id, interface_b_id, capacity_mbps, "
                "latency_ms, admin_up) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET interface_a_id=excluded.interface_a_id, "
                "interface_b_id=excluded.interface_b_id, "
                "capacity_mbps=excluded.capacity_mbps, latency_ms=excluded.latency_ms, "
                "admin_up=excluded.admin_up",
                (
                    link.id,
                    iface_ids[(a.device_id, a.interface)],
                    iface_ids[(b.device_id, b.interface)],
                    link.capacity_mbps,
                    link.latency_ms,
                    int(link.admin_up),
                ),
            )

    def _save_device(
        self, topology: NetworkTopology, device: NetworkDevice, now: str | None
    ) -> None:
        conn = self._conn
        gateway = None
        port_count = None
        if isinstance(device, Server) and device.default_gateway is not None:
            gateway = str(device.default_gateway)
        if isinstance(device, Switch):
            port_count = device.port_count
        conn.execute(
            "INSERT INTO devices(id, hostname, device_type, status, location, "
            "description, default_gateway, port_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
            "hostname=excluded.hostname, device_type=excluded.device_type, "
            "status=excluded.status, "
            "location=excluded.location, description=excluded.description, "
            "default_gateway=excluded.default_gateway, "
            "port_count=excluded.port_count, updated_at=excluded.updated_at",
            (
                device.id,
                device.hostname,
                device.device_type.value,
                device.status.value,
                device.location,
                device.description,
                gateway,
                port_count,
                now,
                now,
            ),
        )
        names = [i.name for i in device.interfaces()]
        stale = conn.execute(
            "SELECT name FROM interfaces WHERE device_id = ?", (device.id,)
        ).fetchall()
        for row in stale:
            if row["name"] not in names:
                conn.execute(
                    "DELETE FROM interfaces WHERE device_id = ? AND name = ?",
                    (device.id, row["name"]),
                )
        speeds = (
            {p.interface.name: p.speed_mbps for p in device.ports()}
            if isinstance(device, Switch)
            else {}
        )
        for position, iface in enumerate(device.interfaces()):
            subnet = topology.subnet_for(iface.address.ip) if iface.address else None
            conn.execute(
                "INSERT INTO interfaces(device_id, position, name, mac, ip_address, "
                "prefix_len, subnet_id, admin_up, port_number, speed_mbps, "
                "description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(device_id, name) DO UPDATE SET "
                "position=excluded.position, mac=excluded.mac, "
                "ip_address=excluded.ip_address, prefix_len=excluded.prefix_len, "
                "subnet_id=excluded.subnet_id, admin_up=excluded.admin_up, "
                "port_number=excluded.port_number, speed_mbps=excluded.speed_mbps, "
                "description=excluded.description",
                (
                    device.id,
                    position,
                    iface.name,
                    iface.mac.value,
                    str(iface.address.ip) if iface.address else None,
                    iface.address.network.prefixlen if iface.address else None,
                    subnet.id if subnet else None,
                    int(iface.admin_up),
                    port_number(iface.name) if isinstance(device, Switch) else None,
                    speeds.get(iface.name),
                    iface.description,
                ),
            )
        conn.execute("DELETE FROM routes WHERE device_id = ?", (device.id,))
        conn.execute("DELETE FROM arp_entries WHERE device_id = ?", (device.id,))
        conn.execute("DELETE FROM mac_entries WHERE device_id = ?", (device.id,))
        if isinstance(device, Router):
            conn.executemany(
                "INSERT INTO routes(device_id, route_no, insertion_index, destination, "
                "next_hop, interface_name, route_type, admin_distance, metric) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        device.id,
                        e.id,
                        e.insertion_index,
                        str(e.destination),
                        str(e.next_hop) if e.next_hop else None,
                        e.interface,
                        e.route_type.value,
                        e.admin_distance,
                        e.metric,
                    )
                    for e in device.routing_table.static_entries()
                ],
            )
        cache = device.arp_cache()
        if cache is not None:
            conn.executemany(
                "INSERT INTO arp_entries(device_id, ip, mac, interface_name, "
                "entry_type, learned_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        device.id,
                        str(e.ip),
                        e.mac.value,
                        e.interface,
                        e.entry_type.value,
                        ts(e.learned_at),
                        ts(e.expires_at),
                    )
                    for e in cache.entries()
                ],
            )
        if isinstance(device, Switch):
            conn.executemany(
                "INSERT INTO mac_entries(device_id, mac, port_number, learned_at, "
                "expires_at) VALUES (?, ?, ?, ?, ?)",
                [
                    (device.id, e.mac.value, e.port, ts(e.learned_at), ts(e.expires_at))
                    for e in device.mac_table.entries()
                ],
            )
