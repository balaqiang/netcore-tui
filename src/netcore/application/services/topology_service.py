"""TopologyService — US-TOP-1..4."""

from __future__ import annotations

from netcore.application.dto import ConnectRequest, LinkDTO, NodeDTO, TopologyDTO
from netcore.application.errors import translate_errors
from netcore.application.services._common import BaseService, link_dto
from netcore.domain.devices.server import Server
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.ids import DeviceId, LinkId
from netcore.domain.interface import InterfaceRef
from netcore.domain.link import DEFAULT_LATENCY_MS


class TopologyService(BaseService):
    """Links and the topology snapshot."""

    def snapshot(self) -> TopologyDTO:
        """Nodes, links and the last simulated path."""
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            recent = uow.simulations.recent(1)
        nodes = tuple(
            NodeDTO(d.id, d.hostname, d.device_type, d.status) for d in topo.devices()
        )
        links = tuple(link_dto(topo, lk) for lk in topo.links())
        path = tuple(recent[0].path) if recent else ()
        return TopologyDTO(nodes, links, path)

    def links(self) -> list[LinkDTO]:
        """All links."""
        return list(self.snapshot().links)

    def free_interfaces(self, device_id: int) -> list[str]:
        """Interfaces without a link (for the link form)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            device = uow.topology.load().get_device(DeviceId(device_id))
        return [i.name for i in device.interfaces() if i.link_id is None]

    def connect(self, req: ConnectRequest) -> LinkDTO:
        """Create a link (US-TOP-1)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            settings = self._settings(uow)
            link = topo.connect(
                InterfaceRef(DeviceId(req.device_a), req.interface_a),
                InterfaceRef(DeviceId(req.device_b), req.interface_b),
                req.capacity_mbps or settings.default_capacity_mbps,
                DEFAULT_LATENCY_MS if req.latency_ms is None else req.latency_ms,
            )
            uow.topology.save(topo)
            dto = link_dto(topo, link)
            evs = [
                self._event(
                    Severity.INFO,
                    EventCategory.CONFIG,
                    f"link {dto.label} created ({link.capacity_mbps} Mbps)",
                    req.device_a,
                    link_id=link.id,
                )
            ]
            a = topo.get_device(DeviceId(req.device_a))
            b = topo.get_device(DeviceId(req.device_b))
            if isinstance(a, Server) and isinstance(b, Server):
                evs.append(
                    self._event(
                        Severity.INFO,
                        EventCategory.CONFIG,
                        f"back-to-back server link {dto.label}",
                        req.device_a,
                    )
                )
            if topo.has_switch_loop():
                evs.append(
                    self._event(
                        Severity.WARNING,
                        EventCategory.CONFIG,
                        "switch loop detected (STP is not simulated)",
                        req.device_a,
                        link_id=link.id,
                    )
                )
            events = self._store(uow, evs)
        self._publish(events)
        return dto

    def disconnect(self, link_id: int) -> None:
        """Remove a link."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            label = link_dto(topo, topo.get_link(LinkId(link_id))).label
            topo.disconnect(LinkId(link_id))
            uow.topology.save(topo)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO, EventCategory.CONFIG, f"link {label} removed"
                    )
                ],
            )
        self._publish(events)

    def set_link_admin(self, link_id: int, up: bool) -> LinkDTO:
        """Cable failure injection (US-TOP-2)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            link = topo.get_link(LinkId(link_id))
            link.set_admin(up)
            uow.topology.save(topo)
            dto = link_dto(topo, link)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO if up else Severity.WARNING,
                        EventCategory.STATE,
                        f"link {dto.label} {'up' if up else 'down'}",
                        link.endpoint_a.device_id,
                        link_id=link.id,
                    )
                ],
            )
        self._publish(events)
        return dto
