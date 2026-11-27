"""Server (end host) — NETWORK_SPEC §6.4."""

from __future__ import annotations

from collections.abc import Iterable
from ipaddress import IPv4Address
from typing import TYPE_CHECKING, ClassVar

from netcore.domain.arp import ArpTable
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.l3 import transmit
from netcore.domain.enums import DeviceStatus, DeviceType, DropReason, HopKind
from netcore.domain.errors import InvalidNextHopError
from netcore.domain.ids import DeviceId
from netcore.domain.interface import NetworkInterface
from netcore.domain.packet import Packet
from netcore.domain.simulation.context import ForwardDecision

if TYPE_CHECKING:
    from netcore.domain.packet import Frame
    from netcore.domain.simulation.context import ForwardingContext


class Server(NetworkDevice):
    """End host: sources and sinks packets, never forwards."""

    device_type: ClassVar[DeviceType] = DeviceType.SERVER
    MIN_INTERFACES: ClassVar[int] = 1
    MAX_INTERFACES: ClassVar[int] = 8
    DEFAULT_INTERFACES: ClassVar[int] = 2

    def __init__(
        self,
        device_id: DeviceId,
        hostname: str,
        interfaces: Iterable[NetworkInterface],
        status: DeviceStatus = DeviceStatus.ONLINE,
        location: str = "",
        description: str = "",
        default_gateway: IPv4Address | None = None,
    ) -> None:
        super().__init__(device_id, hostname, interfaces, status, location, description)
        self._gateway = default_gateway
        self.arp_table = ArpTable()

    @property
    def default_gateway(self) -> IPv4Address | None:
        """Configured default gateway."""
        return self._gateway

    def arp_cache(self) -> ArpTable:
        """Server ARP table."""
        return self.arp_table

    def set_default_gateway(self, ip: IPv4Address | None) -> None:
        """Set gateway; it must be on a connected subnet."""
        if ip is not None and self._interface_on_subnet(ip) is None:
            raise InvalidNextHopError(
                f"Gateway {ip} is not on a connected subnet of {self.hostname}."
            )
        self._gateway = ip

    def restore_gateway(self, ip: IPv4Address | None) -> None:
        """Set gateway without validation (persistence restore)."""
        self._gateway = ip

    def _interface_on_subnet(
        self, ip: IPv4Address, up_only: bool = False
    ) -> NetworkInterface | None:
        for iface in self.addressed_interfaces():
            assert iface.address is not None
            if up_only and not iface.admin_up:
                continue
            if ip in iface.address.network:
                return iface
        return None

    def originate(self, packet: Packet, ctx: ForwardingContext) -> ForwardDecision:
        """Choose egress (direct or via gateway), ARP, send."""
        if self.owns_ip(packet.dst_ip):
            ctx.hop(self, HopKind.DELIVER, "destination is local", ttl_in=packet.ttl)
            return ForwardDecision.deliver()
        if not any(i.admin_up for i in self.addressed_interfaces()):
            ctx.hop(self, HopKind.DROP, "no addressed interface is admin up")
            return ForwardDecision.drop(DropReason.NO_INTERFACE)
        direct = self._interface_on_subnet(packet.dst_ip)
        if direct is not None:
            next_hop = packet.dst_ip
            egress = direct
            why = f"{packet.dst_ip} is on-subnet {egress.address}"
        elif self._gateway is not None:
            gw_iface = self._interface_on_subnet(self._gateway)
            if gw_iface is None:
                ctx.hop(
                    self,
                    HopKind.DROP,
                    f"gateway {self._gateway} is not on a connected subnet",
                    ttl_in=packet.ttl,
                )
                return ForwardDecision.drop(DropReason.NO_ROUTE)
            next_hop = self._gateway
            egress = gw_iface
            why = f"off-subnet, via gateway {self._gateway}"
        else:
            ctx.hop(
                self,
                HopKind.DROP,
                f"{packet.dst_ip} is off-subnet and no default gateway is set",
                ttl_in=packet.ttl,
            )
            return ForwardDecision.drop(DropReason.NO_ROUTE)
        ctx.hop(
            self,
            HopKind.SEND,
            f"send {packet.protocol.value} to {packet.dst_ip}: {why}",
            egress=egress.name,
            ttl_in=packet.ttl,
            ttl_out=packet.ttl,
        )
        return transmit(self, packet, egress.name, next_hop, ctx)

    def receive(
        self, frame: Frame, ingress: str, ctx: ForwardingContext
    ) -> ForwardDecision:
        """Deliver if addressed to us, else ``NOT_FOR_ME``."""
        packet = frame.payload
        ttl = packet.ttl if isinstance(packet, Packet) else None
        if not self.is_online():
            ctx.hop(
                self,
                HopKind.DROP,
                f"{self.hostname} is {self.status.value.lower()}",
                ingress=ingress,
                ttl_in=ttl,
            )
            return ForwardDecision.drop(DropReason.DEVICE_OFFLINE)
        if not self.get_interface(ingress).admin_up:
            ctx.hop(
                self,
                HopKind.DROP,
                f"ingress {ingress} is admin down",
                ingress=ingress,
                ttl_in=ttl,
            )
            return ForwardDecision.drop(DropReason.INTERFACE_DOWN)
        if isinstance(packet, Packet) and self.owns_ip(packet.dst_ip):
            ctx.hop(
                self,
                HopKind.DELIVER,
                f"delivered to {self.hostname} ({packet.dst_ip})",
                ingress=ingress,
                ttl_in=ttl,
            )
            return ForwardDecision.deliver()
        ctx.hop(
            self,
            HopKind.DROP,
            "packet not addressed to this host (servers do not forward)",
            ingress=ingress,
            ttl_in=ttl,
        )
        return ForwardDecision.drop(DropReason.NOT_FOR_ME)
