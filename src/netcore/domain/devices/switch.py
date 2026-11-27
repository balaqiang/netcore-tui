"""Switch, SwitchPort and MacTable (NETWORK_SPEC §8)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

from netcore.domain.addressing import MacAddress
from netcore.domain.devices.base import NetworkDevice
from netcore.domain.enums import DeviceStatus, DeviceType, DropReason, HopKind
from netcore.domain.errors import InvalidPortError, InvalidValueError
from netcore.domain.ids import DeviceId
from netcore.domain.interface import InterfaceRef, NetworkInterface
from netcore.domain.simulation.context import ForwardDecision

if TYPE_CHECKING:
    from netcore.domain.packet import Frame
    from netcore.domain.simulation.context import ForwardingContext

VALID_SPEEDS = (10, 100, 1000, 10000, 25000, 40000, 100000)
DEFAULT_MAC_TIMEOUT_S = 300


def port_name(number: int) -> str:
    """Interface name backing port ``number``."""
    return f"port{number}"


def port_number(name: str) -> int | None:
    """Port number from ``portN`` interface name."""
    if name.startswith("port") and name[4:].isdigit():
        return int(name[4:])
    return None


@dataclass(frozen=True, slots=True)
class MacTableEntry:
    """Learned MAC → port mapping."""

    mac: MacAddress
    port: int
    learned_at: datetime
    expires_at: datetime


class MacTable:
    """Switch MAC address table with simulation-time expiry."""

    def __init__(self, timeout_s: int = DEFAULT_MAC_TIMEOUT_S) -> None:
        self._entries: dict[MacAddress, MacTableEntry] = {}
        self.timeout_s = timeout_s

    def learn(
        self,
        mac: MacAddress,
        port: int,
        now: datetime,
        timeout_s: int | None = None,
    ) -> None:
        """Learn/refresh ``mac`` on ``port``."""
        ttl = self.timeout_s if timeout_s is None else timeout_s
        self._entries[mac] = MacTableEntry(mac, port, now, now + timedelta(seconds=ttl))

    def restore(self, entry: MacTableEntry) -> None:
        """Re-insert a persisted entry."""
        self._entries[entry.mac] = entry

    def lookup(self, mac: MacAddress, now: datetime) -> int | None:
        """Port for ``mac`` if a non-expired entry exists."""
        entry = self._entries.get(mac)
        if entry is None or now >= entry.expires_at:
            return None
        return entry.port

    def entries(self, now: datetime | None = None) -> tuple[MacTableEntry, ...]:
        """Non-expired entries at ``now`` (all if ``now`` is None)."""
        items = sorted(self._entries.values(), key=lambda e: (e.port, e.mac))
        if now is None:
            return tuple(items)
        return tuple(e for e in items if now < e.expires_at)

    def forget_port(self, port: int) -> None:
        """Remove entries for ``port``."""
        self._entries = {m: e for m, e in self._entries.items() if e.port != port}

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()


class SwitchPort:
    """A switch port backed by a ``portN`` interface."""

    def __init__(
        self,
        number: int,
        interface: NetworkInterface,
        speed_mbps: int = 1000,
    ) -> None:
        if speed_mbps not in VALID_SPEEDS:
            raise InvalidValueError(
                f"Port speed {speed_mbps} must be one of {VALID_SPEEDS}."
            )
        self._number = number
        self._interface = interface
        self._speed = speed_mbps

    @property
    def number(self) -> int:
        """Port number (1..N)."""
        return self._number

    @property
    def interface(self) -> NetworkInterface:
        """Backing interface."""
        return self._interface

    @property
    def speed_mbps(self) -> int:
        """Configured speed."""
        return self._speed

    @property
    def description(self) -> str:
        """Port description."""
        return self._interface.description

    @property
    def admin_up(self) -> bool:
        """Administrative state."""
        return self._interface.admin_up

    def set_speed(self, speed_mbps: int) -> None:
        """Change port speed."""
        if speed_mbps not in VALID_SPEEDS:
            raise InvalidValueError(
                f"Port speed {speed_mbps} must be one of {VALID_SPEEDS}."
            )
        self._speed = speed_mbps


class Switch(NetworkDevice):
    """L2 switch: forwards frames by destination MAC only."""

    device_type: ClassVar[DeviceType] = DeviceType.SWITCH
    MIN_INTERFACES: ClassVar[int] = 1
    MAX_INTERFACES: ClassVar[int] = 96
    DEFAULT_INTERFACES: ClassVar[int] = 24

    def __init__(
        self,
        device_id: DeviceId,
        hostname: str,
        interfaces: Iterable[NetworkInterface],
        status: DeviceStatus = DeviceStatus.ONLINE,
        location: str = "",
        description: str = "",
        speeds: dict[int, int] | None = None,
    ) -> None:
        ifaces = list(interfaces)
        for idx, iface in enumerate(ifaces, start=1):
            if iface.name != port_name(idx):
                raise InvalidValueError(
                    f"Switch interfaces must be named port1..portN (got {iface.name})."
                )
        super().__init__(device_id, hostname, ifaces, status, location, description)
        speeds = speeds or {}
        self._ports = {
            idx: SwitchPort(idx, iface, speeds.get(idx, 1000))
            for idx, iface in enumerate(ifaces, start=1)
        }
        self.mac_table = MacTable()

    @property
    def port_count(self) -> int:
        """Number of ports."""
        return len(self._ports)

    def ports(self) -> tuple[SwitchPort, ...]:
        """All ports in order."""
        return tuple(self._ports.values())

    def get_port(self, number: int) -> SwitchPort:
        """Port ``number`` or ``InvalidPortError`` with the valid range."""
        port = self._ports.get(number)
        if port is None:
            raise InvalidPortError(
                f"Port {number} does not exist on {self.hostname} "
                f"(valid: 1-{self.port_count})."
            )
        return port

    def set_port_admin(self, number: int, up: bool) -> None:
        """Enable/disable a port."""
        self.get_port(number).interface.set_admin(up)
        if not up:
            self.mac_table.forget_port(number)

    def learn(self, mac: MacAddress, ingress: str, now: datetime, timeout: int) -> None:
        """Learn ``mac`` on the port backing interface ``ingress``."""
        number = port_number(ingress)
        if number is not None:
            self.mac_table.learn(mac, number, now, timeout)

    def receive(
        self, frame: Frame, ingress: str, ctx: ForwardingContext
    ) -> ForwardDecision:
        """NETWORK_SPEC §8.3 — decisions use ``frame.dst_mac`` only."""
        if not self.is_online():
            ctx.hop(
                self,
                HopKind.DROP,
                f"{self.hostname} is {self.status.value.lower()}",
                ingress=ingress,
            )
            return ForwardDecision.drop(DropReason.DEVICE_OFFLINE)
        in_port = self.get_interface(ingress)
        if not in_port.admin_up:
            ctx.hop(
                self, HopKind.DROP, f"ingress {ingress} is admin down", ingress=ingress
            )
            return ForwardDecision.drop(DropReason.PORT_DOWN)
        self.learn(frame.src_mac, ingress, ctx.now, ctx.settings.mac_timeout_s)
        topo = ctx.topology
        known = (
            None
            if frame.is_broadcast()
            else self.mac_table.lookup(frame.dst_mac, ctx.now)
        )
        if known is None:
            ports = tuple(
                i.name
                for i in self.interfaces()
                if i.name != ingress
                and topo.egress_failure(InterfaceRef(self.id, i.name)) is None
            )
            what = "broadcast" if frame.is_broadcast() else "unknown unicast"
            ctx.hop(
                self,
                HopKind.FLOOD,
                f"{what} dst_mac {frame.dst_mac}: flood to "
                f"{', '.join(ports) if ports else 'no up ports'}",
                ingress=ingress,
            )
            return ForwardDecision.flood(ports, frame)
        egress = port_name(known)
        if egress == ingress:
            ctx.hop(
                self,
                HopKind.DROP,
                f"dst_mac {frame.dst_mac} is on ingress {ingress}: filtered",
                ingress=ingress,
            )
            return ForwardDecision.drop(DropReason.FILTERED)
        failure = topo.egress_failure(InterfaceRef(self.id, egress))
        if failure is not None:
            ctx.hop(
                self,
                HopKind.DROP,
                f"dst_mac {frame.dst_mac} → {egress}, but {egress} cannot transmit "
                f"({failure.value})",
                ingress=ingress,
                egress=egress,
            )
            return ForwardDecision.drop(failure)
        ctx.hop(
            self,
            HopKind.SWITCH,
            f"MAC table: {frame.dst_mac} on {egress}",
            ingress=ingress,
            egress=egress,
        )
        return ForwardDecision.forward(egress, frame)
