"""IpamService — US-IP-1..5."""

from __future__ import annotations

from netcore.application.dto import (
    AddressDTO,
    AssignAddressRequest,
    CreateSubnetRequest,
    InterfaceDTO,
    SubnetDTO,
)
from netcore.application.errors import translate_errors
from netcore.application.services._common import BaseService, device_dto
from netcore.domain.addressing import (
    is_lab_range,
    parse_ipv4_address,
    parse_ipv4_interface,
    parse_ipv4_network,
)
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.errors import AddressNotInSubnetError
from netcore.domain.ids import DeviceId, SubnetId
from netcore.domain.subnet import Subnet
from netcore.domain.topology import NetworkTopology


def _subnet_dto(topo: NetworkTopology, subnet: Subnet) -> SubnetDTO:
    total = subnet.usable_hosts()
    used = len(topo.addresses_in(subnet))
    return SubnetDTO(
        id=subnet.id,
        cidr=str(subnet.network),
        name=subnet.name,
        gateway=str(subnet.gateway) if subnet.gateway else None,
        parent_id=subnet.parent_id,
        total=total,
        used=used,
        free=max(0, total - used),
        utilization_pct=round(used / total * 100, 1) if total else 0.0,
    )


class IpamService(BaseService):
    """Subnets and interface addresses."""

    def list_subnets(self) -> list[SubnetDTO]:
        """All subnets with usage (FR-IP-06)."""
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
        return [_subnet_dto(topo, s) for s in topo.subnets()]

    def addresses(self, subnet_id: int) -> list[AddressDTO]:
        """Addresses assigned inside a subnet."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            subnet = topo.get_subnet(SubnetId(subnet_id))
            return [
                AddressDTO(
                    str(i.address.ip),
                    i.address.network.prefixlen,
                    d.id,
                    d.hostname,
                    i.name,
                    i.mac.value,
                )
                for d, i in topo.addresses_in(subnet)
                if i.address is not None
            ]

    def create_subnet(self, req: CreateSubnetRequest) -> SubnetDTO:
        """Define a subnet (strict CIDR, overlap rules)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            network = parse_ipv4_network(req.cidr.strip())
            gateway = (
                parse_ipv4_address(req.gateway.strip())
                if req.gateway and req.gateway.strip()
                else None
            )
            subnet = topo.add_subnet(
                Subnet(
                    topo.next_subnet_id(),
                    network,
                    req.name.strip(),
                    gateway,
                    SubnetId(req.parent_id) if req.parent_id is not None else None,
                )
            )
            uow.topology.save(topo)
            evs = [
                self._event(
                    Severity.INFO,
                    EventCategory.CONFIG,
                    f"subnet {network} ({subnet.name or 'unnamed'}) created",
                    subnet_id=subnet.id,
                )
            ]
            if not is_lab_range(network.network_address):
                evs.append(
                    self._event(
                        Severity.WARNING,
                        EventCategory.CONFIG,
                        f"public range used in lab: {network}",
                        subnet_id=subnet.id,
                    )
                )
            events = self._store(uow, evs)
            dto = _subnet_dto(topo, subnet)
        self._publish(events)
        return dto

    def delete_subnet(self, subnet_id: int) -> None:
        """Delete an unused subnet."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            subnet = topo.remove_subnet(SubnetId(subnet_id))
            uow.topology.save(topo)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO,
                        EventCategory.CONFIG,
                        f"subnet {subnet.network} deleted",
                    )
                ],
            )
        self._publish(events)

    def assign_address(self, req: AssignAddressRequest) -> InterfaceDTO:
        """Validate and assign an address (US-IP-2/3)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            text = req.address.strip()
            if "/" not in text:
                ip = parse_ipv4_address(text)
                subnet = topo.subnet_for(ip)
                if subnet is None:
                    raise AddressNotInSubnetError(
                        f"{ip} is not inside any defined subnet."
                    )
                text = f"{ip}/{subnet.network.prefixlen}"
            addr = parse_ipv4_interface(text)
            device = topo.get_device(DeviceId(req.device_id))
            topo.assign_address(device.id, req.interface, addr)
            uow.topology.save(topo)
            evs = [
                self._event(
                    Severity.INFO,
                    EventCategory.CONFIG,
                    f"{addr} assigned to {device.hostname} {req.interface}",
                    device.id,
                    address=str(addr),
                    interface=req.interface,
                )
            ]
            if not is_lab_range(addr.ip):
                evs.append(
                    self._event(
                        Severity.WARNING,
                        EventCategory.CONFIG,
                        f"public range used in lab: {addr.ip}",
                        device.id,
                    )
                )
            events = self._store(uow, evs)
            dto = next(
                i
                for i in device_dto(topo, device).interfaces
                if i.name == req.interface
            )
        self._publish(events)
        return dto

    def release_address(self, device_id: int, if_name: str) -> None:
        """Release an address back to the pool (US-IP-5)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            device = topo.get_device(DeviceId(device_id))
            old = device.get_interface(if_name).address
            topo.release_address(device.id, if_name)
            uow.topology.save(topo)
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO,
                        EventCategory.CONFIG,
                        f"{old or 'address'} released from {device.hostname} {if_name}",
                        device.id,
                    )
                ],
            )
        self._publish(events)

    def next_free_address(self, subnet_id: int) -> str | None:
        """Suggested next free address with prefix (US-IP-4)."""
        with translate_errors(), self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            subnet = topo.get_subnet(SubnetId(subnet_id))
            ip = topo.next_free_address(subnet)
        return None if ip is None else f"{ip}/{subnet.network.prefixlen}"
