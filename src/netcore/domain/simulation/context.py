"""ForwardingContext and ForwardDecision shared by devices and engine."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Address
from typing import TYPE_CHECKING

from netcore.domain.addressing import MacAddress
from netcore.domain.enums import (
    ArpOp,
    DropReason,
    ForwardAction,
    HopKind,
)
from netcore.domain.interface import InterfaceRef
from netcore.domain.packet import ArpMessage, Frame, Packet
from netcore.domain.simulation.constants import SimulationSettings
from netcore.domain.simulation.result import HopRecord

if TYPE_CHECKING:
    from netcore.domain.devices.base import NetworkDevice
    from netcore.domain.topology import NetworkTopology


@dataclass(frozen=True, slots=True)
class ForwardDecision:
    """What a device decided to do with a frame/packet."""

    action: ForwardAction
    egress: tuple[str, ...] = ()
    frame: Frame | None = None
    drop_reason: DropReason | None = None

    @classmethod
    def drop(cls, reason: DropReason) -> ForwardDecision:
        """Drop with ``reason``."""
        return cls(ForwardAction.DROP, drop_reason=reason)

    @classmethod
    def deliver(cls) -> ForwardDecision:
        """Deliver locally."""
        return cls(ForwardAction.DELIVER)

    @classmethod
    def forward(cls, egress: str, frame: Frame) -> ForwardDecision:
        """Forward ``frame`` out of ``egress``."""
        return cls(ForwardAction.FORWARD, (egress,), frame)

    @classmethod
    def flood(cls, egress: tuple[str, ...], frame: Frame) -> ForwardDecision:
        """Flood ``frame`` out of ``egress`` ports."""
        return cls(ForwardAction.FLOOD, egress, frame)


@dataclass(frozen=True, slots=True)
class ArpOutcome:
    """Result of an ARP resolution attempt."""

    mac: MacAddress | None
    failure: DropReason | None = None


class ForwardingContext:
    """Per-run mutable state: trace, clock, frame ids, ARP helper."""

    def __init__(
        self,
        topology: NetworkTopology,
        now: datetime,
        settings: SimulationSettings,
    ) -> None:
        self.topology = topology
        self.now = now
        self.settings = settings
        self.hops: list[HopRecord] = []
        self.arp_exchanges = 0
        self._next_frame = 1

    def next_frame_id(self) -> int:
        """Monotonic frame id within the run."""
        value = self._next_frame
        self._next_frame += 1
        return value

    def record(self, hop: HopRecord) -> None:
        """Append a hop record."""
        self.hops.append(hop)

    def hop(
        self,
        device: NetworkDevice,
        kind: HopKind,
        reason: str,
        *,
        ingress: str | None = None,
        egress: str | None = None,
        ttl_in: int | None = None,
        ttl_out: int | None = None,
        matched_route: str | None = None,
    ) -> None:
        """Convenience to build and record a ``HopRecord``."""
        self.record(
            HopRecord(
                index=len(self.hops),
                device_id=device.id,
                device_name=device.hostname,
                device_type=device.device_type,
                kind=kind,
                ingress=ingress,
                egress=egress,
                ttl_in=ttl_in,
                ttl_out=ttl_out,
                matched_route=matched_route,
                reason=reason,
            )
        )

    def make_frame(
        self, src: MacAddress, dst: MacAddress, payload: Packet | ArpMessage
    ) -> Frame:
        """Build a frame with a fresh id."""
        return Frame(self.next_frame_id(), src, dst, payload)

    def resolve_arp(
        self, device: NetworkDevice, egress: str, ip: IPv4Address
    ) -> ArpOutcome:
        """Resolve ``ip`` out of ``egress`` (NETWORK_SPEC §7.2)."""
        table = device.arp_cache()
        if table is None:
            return ArpOutcome(None, DropReason.ARP_FAILED)
        cached = table.get(ip, self.now)
        if cached is not None:
            self.hop(
                device,
                HopKind.ARP,
                f"ARP cache hit: {ip} is-at {cached}",
                egress=egress,
            )
            return ArpOutcome(cached)
        topo = self.topology
        src_ref = InterfaceRef(device.id, egress)
        src_iface = device.get_interface(egress)
        if src_iface.address is None:
            return ArpOutcome(None, DropReason.NO_INTERFACE)
        path = topo.l2_path_to_owner(src_ref, ip)
        if path is None:
            self.hop(
                device,
                HopKind.ARP,
                f"ARP request who-has {ip} tell {src_iface.address.ip} "
                f"broadcast via {egress}: no reply (no owner on segment)",
                egress=egress,
            )
            return ArpOutcome(None, DropReason.ARP_FAILED)
        failure = topo.path_failure(path)
        if failure is not None:
            reason, where = failure
            self.hop(
                device,
                HopKind.ARP,
                f"ARP request who-has {ip} broadcast via {egress}: no reply ({where})",
                egress=egress,
            )
            return ArpOutcome(None, reason)
        owner_ref = path[-1][1]
        owner = topo.get_device(owner_ref.device_id)
        owner_iface = owner.get_interface(owner_ref.interface)
        request = ArpMessage(ArpOp.REQUEST, src_iface.address.ip, src_iface.mac, ip)
        self.make_frame(src_iface.mac, MacAddress.broadcast(), request)
        timeout = self.settings.mac_timeout_s
        flooded: list[str] = []
        for out_ref, in_ref in path:
            # Request: switches learn the requester's MAC on the ingress port.
            if topo.switch_learn(in_ref, src_iface.mac, self.now, timeout):
                flooded.append(topo.get_device(in_ref.device_id).hostname)
            # Reply travels back: switches learn the owner's MAC on the port
            # facing the owner.
            topo.switch_learn(out_ref, owner_iface.mac, self.now, timeout)
        owner_table = owner.arp_cache()
        if owner_table is not None:
            owner_table.learn(
                src_iface.address.ip,
                src_iface.mac,
                owner_ref.interface,
                self.now,
                self.settings.arp_timeout_s,
            )
        table.learn(ip, owner_iface.mac, egress, self.now, self.settings.arp_timeout_s)
        self.arp_exchanges += 1
        via = f" (flooded via {', '.join(flooded)})" if flooded else ""
        self.hop(
            owner,
            HopKind.ARP,
            f"ARP reply: {ip} is-at {owner_iface.mac} to {device.hostname}{via}",
            ingress=owner_ref.interface,
        )
        return ArpOutcome(owner_iface.mac)

    def iter_hops(self) -> Iterator[HopRecord]:
        """Iterate recorded hops."""
        return iter(self.hops)
