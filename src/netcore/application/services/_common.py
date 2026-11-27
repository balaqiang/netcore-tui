"""Shared service plumbing: context, settings model, DTO mapping."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime

from netcore.application.dto import (
    DeviceDTO,
    EventDTO,
    HopDTO,
    InterfaceDTO,
    LinkDTO,
    RouteDTO,
    SettingsDTO,
    SimulationResultDTO,
)
from netcore.application.errors import ApplicationError
from netcore.application.event_bus import EventBus
from netcore.application.ports import (
    Clock,
    EventExporter,
    UnitOfWork,
    UnitOfWorkFactory,
)
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.router import RoutingEntry
from netcore.domain.devices.server import Server
from netcore.domain.enums import EventCategory, HopKind, Severity
from netcore.domain.errors import NetCoreError
from netcore.domain.events import NetworkEvent
from netcore.domain.ids import DeviceId
from netcore.domain.interface import InterfaceRef
from netcore.domain.link import Link
from netcore.domain.simulation.constants import SimulationSettings
from netcore.domain.simulation.result import SimulationResult
from netcore.domain.topology import NetworkTopology

# key: (default, minimum, maximum)
SETTING_RANGES: dict[str, tuple[int, int, int]] = {
    "default_ttl": (64, 1, 255),
    "default_capacity_mbps": (1000, 1, 400_000),
    "arp_timeout_s": (300, 10, 3600),
    "mac_timeout_s": (300, 10, 3600),
    "max_hops": (64, 8, 255),
    "event_retention": (10_000, 100, 1_000_000),
    "seed": (42, 0, 2**31 - 1),
}
SETTING_LABELS: dict[str, str] = {
    "default_ttl": "Default TTL",
    "default_capacity_mbps": "Default link capacity (Mbps)",
    "arp_timeout_s": "ARP timeout (s)",
    "mac_timeout_s": "MAC table timeout (s)",
    "max_hops": "Max hops",
    "event_retention": "Event retention (rows)",
    "seed": "Simulation seed",
}


@dataclass(frozen=True, slots=True)
class ServiceContext:
    """Dependencies shared by all services (constructor injection)."""

    uow_factory: UnitOfWorkFactory
    bus: EventBus
    clock: Clock
    db_path: str = ":memory:"
    exporter: EventExporter | None = None


def read_settings(uow: UnitOfWork, db_path: str) -> SettingsDTO:
    """Effective settings: stored value if valid, else default."""
    stored = uow.settings.get_all()
    values: dict[str, int] = {}
    for key, (default, low, high) in SETTING_RANGES.items():
        raw = stored.get(key)
        try:
            value = int(raw) if raw is not None else default
        except ValueError:
            value = default
        values[key] = value if low <= value <= high else default
    return SettingsDTO(
        default_ttl=values["default_ttl"],
        default_capacity_mbps=values["default_capacity_mbps"],
        arp_timeout_s=values["arp_timeout_s"],
        mac_timeout_s=values["mac_timeout_s"],
        max_hops=values["max_hops"],
        event_retention=values["event_retention"],
        seed=values["seed"],
        lab_name=stored.get("lab_name", "empty-lab"),
        db_path=db_path,
    )


def validate_setting(key: str, value: int) -> int:
    """Raise ``ApplicationError`` if ``value`` is out of range."""
    _default, low, high = SETTING_RANGES[key]
    if not low <= value <= high:
        raise ApplicationError(
            "APP002", f"{SETTING_LABELS[key]} must be between {low} and {high}."
        )
    return value


def sim_settings(settings: SettingsDTO) -> SimulationSettings:
    """Engine settings from app settings."""
    return SimulationSettings(
        default_ttl=settings.default_ttl,
        max_hops=settings.max_hops,
        arp_timeout_s=settings.arp_timeout_s,
        mac_timeout_s=settings.mac_timeout_s,
    )


def seeded_rng(seed: int, salt: int) -> random.Random:
    """Deterministic RNG for (seed, salt)."""
    return random.Random(seed * 1_000_003 + salt)


class BaseService:
    """Common helpers: events, settings, publishing."""

    def __init__(self, ctx: ServiceContext) -> None:
        self._ctx = ctx

    @property
    def _bus(self) -> EventBus:
        return self._ctx.bus

    def _now(self) -> datetime:
        return self._ctx.clock.now()

    def _settings(self, uow: UnitOfWork) -> SettingsDTO:
        return read_settings(uow, self._ctx.db_path)

    def _event(
        self,
        severity: Severity,
        category: EventCategory,
        message: str,
        device_id: int | None = None,
        **payload: object,
    ) -> NetworkEvent:
        return NetworkEvent(
            timestamp=self._now(),
            severity=severity,
            category=category,
            message=message,
            device_id=DeviceId(device_id) if device_id is not None else None,
            payload=payload,
        )

    def _store(
        self, uow: UnitOfWork, events: Iterable[NetworkEvent]
    ) -> list[NetworkEvent]:
        """Persist events (assigning ids) and apply retention."""
        stored = [replace(e, id=uow.events.add(e)) for e in events]
        if stored:
            uow.events.prune(self._settings(uow).event_retention)
        return stored

    def _publish(self, events: Iterable[NetworkEvent]) -> None:
        """Publish after commit (DEC-013)."""
        for event in events:
            self._bus.publish(event)


# ------------------------------------------------------------- DTO mapping
def peer_label(topo: NetworkTopology, ref: InterfaceRef) -> str | None:
    """``host:iface`` of the peer, if linked."""
    peer = topo.peer(ref)
    if peer is None:
        return None
    return f"{topo.get_device(peer.device_id).hostname}:{peer.interface}"


def device_dto(topo: NetworkTopology, device: NetworkDevice) -> DeviceDTO:
    """Entity → DTO."""
    ifaces = tuple(
        InterfaceDTO(
            name=i.name,
            mac=i.mac.value,
            address=str(i.address) if i.address else None,
            admin_up=i.admin_up,
            link_id=i.link_id,
            peer=peer_label(topo, InterfaceRef(device.id, i.name)),
            operational=topo.is_operational(InterfaceRef(device.id, i.name)),
        )
        for i in device.interfaces()
    )
    gateway = None
    if isinstance(device, Server) and device.default_gateway is not None:
        gateway = str(device.default_gateway)
    return DeviceDTO(
        id=device.id,
        hostname=device.hostname,
        device_type=device.device_type,
        status=device.status,
        location=device.location,
        description=device.description,
        interfaces=ifaces,
        default_gateway=gateway,
    )


def link_dto(topo: NetworkTopology, link: Link) -> LinkDTO:
    """Entity → DTO."""
    a, b = link.endpoint_a, link.endpoint_b
    return LinkDTO(
        id=link.id,
        a_device_id=a.device_id,
        a_device=topo.get_device(a.device_id).hostname,
        a_interface=a.interface,
        b_device_id=b.device_id,
        b_device=topo.get_device(b.device_id).hostname,
        b_interface=b.interface,
        capacity_mbps=link.capacity_mbps,
        latency_ms=link.latency_ms,
        admin_up=link.admin_up,
        operational=topo.is_operational(a) and topo.is_operational(b),
    )


def route_dto(router_id: int, entry: RoutingEntry) -> RouteDTO:
    """Entity → DTO."""
    return RouteDTO(
        id=entry.id,
        router_id=router_id,
        route_type=entry.route_type,
        destination=str(entry.destination),
        next_hop=str(entry.next_hop) if entry.next_hop else None,
        interface=entry.interface,
        admin_distance=entry.admin_distance,
        metric=entry.metric,
    )


def result_dto(
    topo: NetworkTopology | None, result: SimulationResult
) -> SimulationResultDTO:
    """Result → DTO with a human summary."""
    hops = tuple(
        HopDTO(
            index=h.index,
            kind=h.kind,
            device_id=h.device_id,
            device_name=h.device_name,
            device_type=h.device_type,
            ingress=h.ingress,
            egress=h.egress,
            ttl_in=h.ttl_in,
            ttl_out=h.ttl_out,
            matched_route=h.matched_route,
            reason=h.reason,
        )
        for h in result.hops
    )

    def name(device_id: int) -> str:
        if topo is not None:
            try:
                return topo.get_device(DeviceId(device_id)).hostname
            except NetCoreError:  # device may have been deleted since
                pass
        for h in result.hops:
            if h.device_id == device_id:
                return h.device_name
        return f"#{device_id}"

    ttl_start = result.request.ttl if result.request else 0
    ttl_values = [h.ttl_out for h in result.hops if h.ttl_out is not None]
    ttl_values += [h.ttl_in for h in result.hops[-1:] if h.ttl_in is not None]
    ttl_end = min(ttl_values) if ttl_values else None
    drop_device = None
    if not result.delivered and result.hops:
        drop_device = result.hops[-1].device_name
    if result.delivered:
        summary = (
            f"✔ DELIVERED  hops {len(result.path) - 1}  TTL {ttl_start}→{ttl_end}  "
            f"latency {result.total_latency_ms:.2f} ms (sim)"
        )
    else:
        reason = result.drop_reason.value if result.drop_reason else "DROPPED"
        detail = result.hops[-1].reason if result.hops else ""
        summary = f"✖ DROPPED — {reason} at {drop_device} ({detail})"
    return SimulationResultDTO(
        run_id=result.run_id,
        status=result.status,
        drop_reason=result.drop_reason,
        hops=hops,
        path_ids=tuple(result.path),
        path_names=tuple(name(d) for d in result.path),
        total_latency_ms=result.total_latency_ms,
        ttl_start=ttl_start,
        ttl_end=ttl_end,
        drop_device=drop_device,
        summary=summary,
    )


def event_dto(topo: NetworkTopology | None, event: NetworkEvent) -> EventDTO:
    """Event → DTO (device name resolved when possible)."""
    device_name = None
    if event.device_id is not None and topo is not None:
        try:
            device_name = topo.get_device(event.device_id).hostname
        except NetCoreError:  # device deleted since the event
            device_name = None
    return EventDTO(
        id=event.id or 0,
        timestamp=event.timestamp,
        severity=event.severity,
        category=event.category,
        device_id=event.device_id,
        device_name=device_name,
        message=event.message,
        payload=dict(event.payload),
    )


def hop_event_category(kind: HopKind) -> EventCategory:
    """Category for a hop-derived event."""
    return EventCategory.ARP if kind is HopKind.ARP else EventCategory.FORWARD
