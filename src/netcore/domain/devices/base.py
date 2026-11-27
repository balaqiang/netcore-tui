"""Abstract NetworkDevice (UML.md §2)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from ipaddress import IPv4Address
from typing import TYPE_CHECKING, ClassVar

from netcore.domain.addressing import validate_hostname
from netcore.domain.arp import ArpTable
from netcore.domain.enums import DeviceStatus, DeviceType
from netcore.domain.errors import (
    DuplicateInterfaceError,
    InterfaceNotFoundError,
    InvalidValueError,
)
from netcore.domain.ids import DeviceId
from netcore.domain.interface import NetworkInterface
from netcore.domain.logging_mixin import LoggerMixin

if TYPE_CHECKING:
    from netcore.domain.packet import Frame, Packet
    from netcore.domain.simulation.context import ForwardDecision, ForwardingContext


class NetworkDevice(LoggerMixin, ABC):
    """Common behaviour of routers, switches and servers."""

    device_type: ClassVar[DeviceType]
    MIN_INTERFACES: ClassVar[int] = 1
    MAX_INTERFACES: ClassVar[int] = 1
    DEFAULT_INTERFACES: ClassVar[int] = 1

    def __init__(
        self,
        device_id: DeviceId,
        hostname: str,
        interfaces: Iterable[NetworkInterface],
        status: DeviceStatus = DeviceStatus.ONLINE,
        location: str = "",
        description: str = "",
    ) -> None:
        self._id = device_id
        self._hostname = validate_hostname(hostname)
        self._status = status
        self._interfaces: dict[str, NetworkInterface] = {}
        for iface in interfaces:
            if iface.name in self._interfaces:
                raise DuplicateInterfaceError(
                    f"Interface {iface.name} is defined twice on {hostname}."
                )
            self._interfaces[iface.name] = iface
        count = len(self._interfaces)
        if not self.MIN_INTERFACES <= count <= self.MAX_INTERFACES:
            raise InvalidValueError(
                f"{self.device_type.value.title()} interface count {count} must be "
                f"between {self.MIN_INTERFACES} and {self.MAX_INTERFACES}."
            )
        self.location = location
        self.description = description

    @property
    def id(self) -> DeviceId:
        """Device identifier."""
        return self._id

    @property
    def hostname(self) -> str:
        """Hostname, unique per lab (case-insensitive)."""
        return self._hostname

    @property
    def status(self) -> DeviceStatus:
        """Current status."""
        return self._status

    def rename(self, hostname: str) -> None:
        """Change hostname (uniqueness checked by the topology)."""
        self._hostname = validate_hostname(hostname)

    def interfaces(self) -> tuple[NetworkInterface, ...]:
        """All interfaces in definition order."""
        return tuple(self._interfaces.values())

    def get_interface(self, name: str) -> NetworkInterface:
        """Interface by name or ``InterfaceNotFoundError``."""
        try:
            return self._interfaces[name]
        except KeyError:
            raise InterfaceNotFoundError(
                f"Interface {name} not found on {self._hostname}."
            ) from None

    def has_interface(self, name: str) -> bool:
        """True if interface ``name`` exists."""
        return name in self._interfaces

    def addressed_interfaces(self) -> tuple[NetworkInterface, ...]:
        """Interfaces that have an IPv4 address."""
        return tuple(i for i in self._interfaces.values() if i.address is not None)

    def is_online(self) -> bool:
        """True only for ``ONLINE`` (MAINTENANCE behaves as offline)."""
        return self._status is DeviceStatus.ONLINE

    def set_status(self, status: DeviceStatus) -> None:
        """Change status (all transitions allowed, UML §9.1)."""
        self._status = status

    def owns_ip(self, ip: IPv4Address) -> bool:
        """True if any interface has address ``ip``."""
        return any(
            i.address is not None and i.address.ip == ip
            for i in self._interfaces.values()
        )

    def interface_for_ip(self, ip: IPv4Address) -> NetworkInterface | None:
        """Interface holding address ``ip``."""
        for iface in self._interfaces.values():
            if iface.address is not None and iface.address.ip == ip:
                return iface
        return None

    def arp_cache(self) -> ArpTable | None:
        """ARP table for L3 devices; ``None`` for switches."""
        return None

    def on_address_changed(self) -> None:
        """Hook called by the topology after an interface address change."""

    @abstractmethod
    def receive(
        self, frame: Frame, ingress: str, ctx: ForwardingContext
    ) -> ForwardDecision:
        """Process a frame arriving on ``ingress``."""

    def originate(self, packet: Packet, ctx: ForwardingContext) -> ForwardDecision:
        """Send a locally generated packet (L3 devices override)."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._id}, {self._hostname!r})"
