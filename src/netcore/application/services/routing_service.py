"""RoutingService — US-RT-1..5."""

from __future__ import annotations

from netcore.application.dto import AddRouteRequest, RouteDTO, RouteLookupDTO
from netcore.application.errors import translate_errors
from netcore.application.services._common import BaseService, route_dto
from netcore.domain.addressing import parse_ipv4_address, parse_ipv4_network
from netcore.domain.devices.router import STATIC_AD, RoutingEntry
from netcore.domain.enums import EventCategory, RouteType, Severity
from netcore.domain.errors import InvalidNextHopError
from netcore.domain.ids import DeviceId


class RoutingService(BaseService):
    """Routing tables and the lookup tool."""

    def routers(self) -> list[tuple[int, str]]:
        """(id, hostname) of all routers."""
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
        return [
            (d.id, d.hostname)
            for d in topo.devices()
            if d.device_type.value == "ROUTER"
        ]

    def routes(self, router_id: int) -> list[RouteDTO]:
        """Routing table rows (connected + static)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            router = uow.topology.load().get_router(DeviceId(router_id))
        return [route_dto(router.id, e) for e in router.routing_table.entries()]

    def add_static_route(self, req: AddRouteRequest) -> RouteDTO:
        """Add a static/default route; next hop must be connected (FR-RT-04)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            router = topo.get_router(DeviceId(req.router_id))
            destination = parse_ipv4_network(req.destination.strip())
            next_hop = parse_ipv4_address(req.next_hop.strip())
            interface = (req.interface or "").strip()
            if not interface:
                connected = router.connected_interface_for(next_hop)
                if connected is None:
                    raise InvalidNextHopError(
                        f"Next hop {next_hop} is not on a connected subnet of "
                        f"{router.hostname}."
                    )
                interface = connected.name
            entry = router.add_static_route(
                RoutingEntry(
                    0,
                    destination,
                    next_hop,
                    interface,
                    RouteType.STATIC,
                    STATIC_AD,
                    req.metric,
                )
            )
            uow.topology.save(topo)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO,
                        EventCategory.CONFIG,
                        f"route {entry.describe()} added on {router.hostname}",
                        router.id,
                        route=entry.describe(),
                    )
                ],
            )
        self._publish(events)
        return route_dto(router.id, entry)

    def remove_route(self, router_id: int, route_id: int) -> None:
        """Remove a static/default route."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            router = topo.get_router(DeviceId(router_id))
            entry = router.remove_route(route_id)
            uow.topology.save(topo)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO,
                        EventCategory.CONFIG,
                        f"route {entry.describe()} removed from {router.hostname}",
                        router.id,
                    )
                ],
            )
        self._publish(events)

    def lookup(self, router_id: int, dst_ip: str) -> RouteLookupDTO:
        """Which route would ``dst_ip`` use (US-RT-4)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            router = uow.topology.load().get_router(DeviceId(router_id))
            ip = parse_ipv4_address(dst_ip.strip())
        entry = router.lookup(ip)
        if entry is None:
            return RouteLookupDTO(str(ip), None, f"No route to {ip}")
        via = f"via {entry.next_hop}" if entry.next_hop else "directly connected"
        return RouteLookupDTO(
            str(ip),
            route_dto(router.id, entry),
            f"Matched {entry.destination} (prefix /{entry.destination.prefixlen}) "
            f"{via} {entry.interface}",
        )
