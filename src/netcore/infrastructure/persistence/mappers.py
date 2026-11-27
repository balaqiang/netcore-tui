"""Row <-> domain conversions (DEC-006). Never leaks sqlite3.Row upward."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from ipaddress import IPv4Address, IPv4Interface, IPv4Network

from netcore.domain.addressing import MacAddress
from netcore.domain.arp import ArpEntry
from netcore.domain.devices.router import RoutingEntry
from netcore.domain.devices.switch import MacTableEntry
from netcore.domain.enums import (
    ArpEntryType,
    DeviceType,
    DropReason,
    EventCategory,
    HopKind,
    RouteType,
    Severity,
)
from netcore.domain.events import NetworkEvent
from netcore.domain.ids import DeviceId, SubnetId
from netcore.domain.interface import NetworkInterface
from netcore.domain.simulation.result import HopRecord
from netcore.domain.subnet import Subnet


def ts(value: datetime | None) -> str | None:
    """Datetime to ISO-8601 text."""
    return None if value is None else value.isoformat()


def parse_ts(value: str | None) -> datetime | None:
    """ISO-8601 text to datetime."""
    return None if value is None else datetime.fromisoformat(value)


def require_ts(value: str) -> datetime:
    """ISO-8601 text to datetime (non-null)."""
    return datetime.fromisoformat(value)


def ip_or_none(value: str | None) -> IPv4Address | None:
    """Text to address or None."""
    return None if value is None else IPv4Address(value)


def subnet_from_row(row: sqlite3.Row) -> Subnet:
    """``subnets`` row → Subnet."""
    return Subnet(
        SubnetId(row["id"]),
        IPv4Network(row["cidr"]),
        row["name"],
        ip_or_none(row["gateway"]),
        SubnetId(row["parent_id"]) if row["parent_id"] is not None else None,
    )


def interface_from_row(row: sqlite3.Row) -> NetworkInterface:
    """``interfaces`` row → NetworkInterface (link attached later)."""
    address = None
    if row["ip_address"] is not None:
        address = IPv4Interface(f"{row['ip_address']}/{row['prefix_len']}")
    return NetworkInterface(
        row["name"],
        MacAddress(row["mac"]),
        address,
        bool(row["admin_up"]),
        None,
        row["description"],
    )


def route_from_row(row: sqlite3.Row) -> RoutingEntry:
    """``routes`` row → RoutingEntry."""
    return RoutingEntry(
        row["route_no"],
        IPv4Network(row["destination"]),
        ip_or_none(row["next_hop"]),
        row["interface_name"],
        RouteType(row["route_type"]),
        row["admin_distance"],
        row["metric"],
        row["insertion_index"],
    )


def arp_from_row(row: sqlite3.Row) -> ArpEntry:
    """``arp_entries`` row → ArpEntry."""
    return ArpEntry(
        IPv4Address(row["ip"]),
        MacAddress(row["mac"]),
        row["interface_name"],
        parse_ts(row["learned_at"]),
        parse_ts(row["expires_at"]),
        ArpEntryType(row["entry_type"]),
    )


def mac_entry_from_row(row: sqlite3.Row) -> MacTableEntry:
    """``mac_entries`` row → MacTableEntry."""
    return MacTableEntry(
        MacAddress(row["mac"]),
        row["port_number"],
        require_ts(row["learned_at"]),
        require_ts(row["expires_at"]),
    )


def event_from_row(row: sqlite3.Row) -> NetworkEvent:
    """``events`` row → NetworkEvent."""
    return NetworkEvent(
        id=row["id"],
        timestamp=require_ts(row["timestamp"]),
        severity=Severity(row["severity"]),
        category=EventCategory(row["category"]),
        device_id=DeviceId(row["device_id"]) if row["device_id"] is not None else None,
        message=row["message"],
        payload=json.loads(row["payload_json"]),
    )


def hop_from_row(row: sqlite3.Row) -> HopRecord:
    """``hop_records`` row → HopRecord."""
    return HopRecord(
        index=row["hop_index"],
        device_id=DeviceId(row["device_id"]),
        device_name=row["device_name"],
        device_type=DeviceType(row["device_type"]),
        kind=HopKind(row["kind"]),
        ingress=row["ingress"],
        egress=row["egress"],
        ttl_in=row["ttl_in"],
        ttl_out=row["ttl_out"],
        matched_route=row["matched_route"],
        reason=row["reason"],
    )


def drop_reasons_from_json(text: str) -> dict[DropReason, int]:
    """JSON object → reason counts."""
    return {DropReason(k): int(v) for k, v in json.loads(text).items()}


def drop_reasons_to_json(reasons: dict[DropReason, int]) -> str:
    """Reason counts → JSON object."""
    return json.dumps({k.value: v for k, v in sorted(reasons.items())})
