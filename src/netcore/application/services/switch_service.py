"""SwitchService — US-SW-1..4."""

from __future__ import annotations

from netcore.application.dto import MacEntryDTO, SwitchPortDTO, UpdatePortRequest
from netcore.application.errors import translate_errors
from netcore.application.services._common import BaseService, peer_label
from netcore.domain.devices.switch import Switch
from netcore.domain.enums import Direction, EventCategory, Severity
from netcore.domain.ids import DeviceId
from netcore.domain.interface import InterfaceRef
from netcore.domain.topology import NetworkTopology


class SwitchService(BaseService):
    """Ports and MAC tables."""

    def switches(self) -> list[tuple[int, str]]:
        """(id, hostname) of all switches."""
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
        return [(d.id, d.hostname) for d in topo.devices() if isinstance(d, Switch)]

    def _port_dtos(
        self, topo: NetworkTopology, switch: Switch, counters: dict
    ) -> list[SwitchPortDTO]:
        result = []
        for port in switch.ports():
            ref = InterfaceRef(switch.id, port.interface.name)
            link = topo.link_for(ref)
            tx = rx = 0
            if link is not None:
                a_side = link.endpoint_a == ref
                out_dir = Direction.A_TO_B if a_side else Direction.B_TO_A
                in_dir = Direction.B_TO_A if a_side else Direction.A_TO_B
                tx = counters.get((None, link.id, out_dir), 0)
                rx = counters.get((None, link.id, in_dir), 0)
            result.append(
                SwitchPortDTO(
                    switch_id=switch.id,
                    number=port.number,
                    admin_up=port.admin_up,
                    speed_mbps=port.speed_mbps,
                    description=port.description,
                    peer=peer_label(topo, ref),
                    operational=topo.is_operational(ref),
                    tx_packets=tx,
                    rx_packets=rx,
                )
            )
        return result

    def ports(self, switch_id: int) -> list[SwitchPortDTO]:
        """All ports with peer and simulated counters."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            switch = topo.get_switch(DeviceId(switch_id))
            counters = {k: v.packets for k, v in uow.traffic.counters().items()}
        return self._port_dtos(topo, switch, counters)

    def set_port_admin(self, switch_id: int, port: int, up: bool) -> SwitchPortDTO:
        """Enable/disable a port (US-SW-2)."""
        return self.update_port(UpdatePortRequest(switch_id, port, admin_up=up))

    def update_port(self, req: UpdatePortRequest) -> SwitchPortDTO:
        """Edit speed/description/admin state."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            switch = topo.get_switch(DeviceId(req.switch_id))
            port = switch.get_port(req.port)
            changes = []
            if req.admin_up is not None and req.admin_up != port.admin_up:
                switch.set_port_admin(req.port, req.admin_up)
                changes.append(f"admin {'up' if req.admin_up else 'down'}")
            if req.speed_mbps is not None and req.speed_mbps != port.speed_mbps:
                port.set_speed(req.speed_mbps)
                changes.append(f"speed {req.speed_mbps} Mbps")
            if req.description is not None and req.description != port.description:
                port.interface.set_description(req.description.strip())
                changes.append("description")
            events = []
            if changes:
                uow.topology.save(topo)
                down = req.admin_up is False
                events = self._store(
                    uow,
                    [
                        self._event(
                            Severity.WARNING if down else Severity.INFO,
                            EventCategory.STATE
                            if req.admin_up is not None
                            else EventCategory.CONFIG,
                            f"{switch.hostname} port{req.port}: {', '.join(changes)}",
                            switch.id,
                            port=req.port,
                        )
                    ],
                )
            counters = {k: v.packets for k, v in uow.traffic.counters().items()}
            dto = self._port_dtos(topo, switch, counters)[req.port - 1]
        self._publish(events)
        return dto

    def mac_table(self, switch_id: int) -> list[MacEntryDTO]:
        """Valid MAC entries with age in simulated seconds."""
        now = self._now()
        with translate_errors(), self._ctx.uow_factory() as uow:
            switch = uow.topology.load().get_switch(DeviceId(switch_id))
        return [
            MacEntryDTO(
                e.mac.value, e.port, max(0, int((now - e.learned_at).total_seconds()))
            )
            for e in switch.mac_table.entries(now)
        ]

    def clear_mac_table(self, switch_id: int) -> None:
        """Clear the MAC table (US-SW-3)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            switch = topo.get_switch(DeviceId(switch_id))
            switch.mac_table.clear()
            uow.topology.save(topo)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO,
                        EventCategory.CONFIG,
                        f"MAC table cleared on {switch.hostname}",
                        switch.id,
                    )
                ],
            )
        self._publish(events)
