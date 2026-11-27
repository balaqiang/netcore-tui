"""DeviceService — US-DEV-1..5, ARP table view/clear (§7.3)."""

from __future__ import annotations

from netcore.application.dto import (
    ArpEntryDTO,
    CreateDeviceRequest,
    DeviceDTO,
    DeviceFilter,
    DeviceStatus,
    RemovalReportDTO,
    UpdateDeviceRequest,
)
from netcore.application.errors import ApplicationError, translate_errors
from netcore.application.services._common import BaseService, device_dto, seeded_rng
from netcore.domain.addressing import parse_ipv4_address
from netcore.domain.devices.server import Server
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.ids import DeviceId
from netcore.domain.labs import build_device


class DeviceService(BaseService):
    """Create/edit/delete devices and change their status."""

    def list_devices(self, flt: DeviceFilter | None = None) -> list[DeviceDTO]:
        """Devices matching ``flt``."""
        flt = flt or DeviceFilter()
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
        text = flt.text.lower().strip()
        result = []
        for device in topo.devices():
            if (
                flt.device_type is not None
                and device.device_type is not flt.device_type
            ):
                continue
            if flt.status is not None and device.status is not flt.status:
                continue
            haystack = f"{device.hostname} {device.location} {device.description}"
            if text and text not in haystack.lower():
                continue
            result.append(device_dto(topo, device))
        return result

    def get_device(self, device_id: int) -> DeviceDTO:
        """One device."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            return device_dto(topo, topo.get_device(DeviceId(device_id)))

    def create_device(self, req: CreateDeviceRequest) -> DeviceDTO:
        """Add a device with generated unique MACs."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            settings = self._settings(uow)
            rng = seeded_rng(settings.seed, topo.next_device_id())
            device = build_device(
                topo,
                rng,
                req.device_type,
                req.hostname.strip(),
                req.interface_count,
                req.location.strip(),
                req.description.strip(),
            )
            topo.add_device(device)
            uow.topology.save(topo)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO,
                        EventCategory.CONFIG,
                        f"{device.device_type.value.lower()} {device.hostname} added "
                        f"({len(device.interfaces())} interfaces)",
                        device.id,
                        action="device_added",
                    )
                ],
            )
            dto = device_dto(topo, device)
        self._publish(events)
        return dto

    def update_device(self, req: UpdateDeviceRequest) -> DeviceDTO:
        """Edit hostname/location/description/gateway."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            device = topo.get_device(DeviceId(req.device_id))
            changes: list[str] = []
            if req.hostname is not None and req.hostname.strip() != device.hostname:
                old = device.hostname
                topo.rename_device(device.id, req.hostname.strip())
                changes.append(f"hostname {old}→{device.hostname}")
            if req.location is not None and req.location != device.location:
                device.location = req.location.strip()
                changes.append("location")
            if req.description is not None and req.description != device.description:
                device.description = req.description.strip()
                changes.append("description")
            if req.default_gateway is not None:
                if not isinstance(device, Server):
                    raise ApplicationError(
                        "APP003", "Only servers have a default gateway."
                    )
                text = req.default_gateway.strip()
                gateway = parse_ipv4_address(text) if text else None
                if gateway != device.default_gateway:
                    device.set_default_gateway(gateway)
                    changes.append(f"gateway {gateway or 'none'}")
            events = []
            if changes:
                uow.topology.save(topo)
                events = self._store(
                    uow,
                    [
                        self._event(
                            Severity.INFO,
                            EventCategory.CONFIG,
                            f"{device.hostname} updated: {', '.join(changes)}",
                            device.id,
                            action="device_updated",
                        )
                    ],
                )
            dto = device_dto(topo, device)
        self._publish(events)
        return dto

    def delete_device(self, device_id: int) -> RemovalReportDTO:
        """Delete a device and everything referencing it (FR-DEV-04)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            links = [
                f"link {lk.id}"
                for lk in topo.links()
                if lk.involves(DeviceId(device_id))
            ]
            report = topo.remove_device(DeviceId(device_id))
            uow.topology.save(topo)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO,
                        EventCategory.CONFIG,
                        f"{report.hostname} deleted "
                        f"({len(report.removed_links)} links, "
                        f"{len(report.removed_routes)} routes removed)",
                        None,
                        action="device_deleted",
                        device=report.hostname,
                    )
                ],
            )
        self._publish(events)
        return RemovalReportDTO(
            report.hostname,
            tuple(links),
            report.removed_routes,
            report.released_addresses,
        )

    def removal_preview(self, device_id: int) -> RemovalReportDTO:
        """What ``delete_device`` would remove (for the confirm modal)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            links = [
                f"{topo.get_device(lk.endpoint_a.device_id).hostname}:"
                f"{lk.endpoint_a.interface} ↔ "
                f"{topo.get_device(lk.endpoint_b.device_id).hostname}:"
                f"{lk.endpoint_b.interface}"
                for lk in topo.links()
                if lk.involves(DeviceId(device_id))
            ]
            report = topo.remove_device(DeviceId(device_id))
            uow.rollback()
        return RemovalReportDTO(
            report.hostname,
            tuple(links),
            report.removed_routes,
            report.released_addresses,
        )

    def set_status(self, device_id: int, status: DeviceStatus) -> DeviceDTO:
        """Failure injection / maintenance (US-DEV-4)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            device = topo.get_device(DeviceId(device_id))
            old = device.status
            device.set_status(status)
            uow.topology.save(topo)
            sev = Severity.INFO if status is DeviceStatus.ONLINE else Severity.WARNING
            events = self._store(
                uow,
                [
                    self._event(
                        sev,
                        EventCategory.STATE,
                        f"{device.hostname} {old.value.lower()} → "
                        f"{status.value.lower()}",
                        device.id,
                        old=old.value,
                        new=status.value,
                    )
                ],
            )
            dto = device_dto(topo, device)
        self._publish(events)
        return dto

    def cycle_status(self, device_id: int) -> DeviceDTO:
        """ONLINE → OFFLINE → MAINTENANCE → ONLINE (UI ``s`` key)."""
        order = [DeviceStatus.ONLINE, DeviceStatus.OFFLINE, DeviceStatus.MAINTENANCE]
        current = self.get_device(device_id).status
        return self.set_status(device_id, order[(order.index(current) + 1) % 3])

    def set_interface_admin(
        self, device_id: int, interface: str, up: bool
    ) -> DeviceDTO:
        """Admin up/down an interface (router/server)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            device = topo.get_device(DeviceId(device_id))
            device.get_interface(interface).set_admin(up)
            uow.topology.save(topo)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO if up else Severity.WARNING,
                        EventCategory.STATE,
                        f"{device.hostname} {interface} admin {'up' if up else 'down'}",
                        device.id,
                    )
                ],
            )
            dto = device_dto(topo, device)
        self._publish(events)
        return dto

    def arp_table(self, device_id: int) -> list[ArpEntryDTO]:
        """Valid ARP entries of a router/server."""
        now = self._now()
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            cache = topo.get_device(DeviceId(device_id)).arp_cache()
        if cache is None:
            return []
        return [
            ArpEntryDTO(
                str(e.ip),
                e.mac.value,
                e.interface,
                e.entry_type.value,
                int((e.expires_at - now).total_seconds()) if e.expires_at else None,
            )
            for e in cache.entries(now)
        ]

    def clear_arp(self, device_id: int) -> None:
        """Clear a device ARP table (emits INFO, §7.3)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            device = topo.get_device(DeviceId(device_id))
            cache = device.arp_cache()
            if cache is None:
                raise ApplicationError("APP004", f"{device.hostname} has no ARP table.")
            cache.clear()
            uow.topology.save(topo)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO,
                        EventCategory.ARP,
                        f"ARP table cleared on {device.hostname}",
                        device.id,
                    )
                ],
            )
        self._publish(events)
