"""NetworkInterface and InterfaceRef."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Interface

from netcore.domain.addressing import MacAddress
from netcore.domain.ids import DeviceId, LinkId


@dataclass(frozen=True, slots=True, order=True)
class InterfaceRef:
    """Reference to an interface of a device: ``(device_id, name)``."""

    device_id: DeviceId
    interface: str


class NetworkInterface:
    """A device interface (router ``ge0/x``, server ``ethX``, switch ``portN``)."""

    def __init__(
        self,
        name: str,
        mac: MacAddress,
        address: IPv4Interface | None = None,
        admin_up: bool = True,
        link_id: LinkId | None = None,
        description: str = "",
    ) -> None:
        self._name = name
        self._mac = mac.ensure_assignable()
        self._address = address
        self._admin_up = admin_up
        self._link_id = link_id
        self._description = description

    @property
    def name(self) -> str:
        """Interface name, unique per device."""
        return self._name

    @property
    def mac(self) -> MacAddress:
        """Interface MAC address."""
        return self._mac

    @property
    def address(self) -> IPv4Interface | None:
        """Assigned IPv4 interface address, if any."""
        return self._address

    @property
    def admin_up(self) -> bool:
        """Administrative state."""
        return self._admin_up

    @property
    def link_id(self) -> LinkId | None:
        """Link attached to this interface, if any."""
        return self._link_id

    @property
    def description(self) -> str:
        """Free-form description."""
        return self._description

    @property
    def is_loopback(self) -> bool:
        """Loopback interfaces are named ``lo*``."""
        return self._name.startswith("lo")

    def assign_address(self, addr: IPv4Interface) -> None:
        """Set the interface address (validation is done by the topology)."""
        self._address = addr

    def clear_address(self) -> None:
        """Remove the interface address."""
        self._address = None

    def set_admin(self, up: bool) -> None:
        """Set administrative state."""
        self._admin_up = up

    def set_description(self, text: str) -> None:
        """Set description."""
        self._description = text

    def attach_link(self, link_id: LinkId) -> None:
        """Record the link attached to this interface (topology only)."""
        self._link_id = link_id

    def detach_link(self) -> None:
        """Forget the attached link (topology only)."""
        self._link_id = None

    def __repr__(self) -> str:
        return f"NetworkInterface({self._name!r}, {self._mac}, {self._address})"
