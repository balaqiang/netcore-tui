"""Shared L3 transmit helper for routers and servers (§6.3 steps 6-8)."""

from __future__ import annotations

from ipaddress import IPv4Address
from typing import TYPE_CHECKING

from netcore.domain.enums import DropReason, HopKind
from netcore.domain.interface import InterfaceRef
from netcore.domain.simulation.context import ForwardDecision

if TYPE_CHECKING:
    from netcore.domain.devices.base import NetworkDevice
    from netcore.domain.packet import Packet
    from netcore.domain.simulation.context import ForwardingContext


def transmit(
    device: NetworkDevice,
    packet: Packet,
    egress: str,
    next_hop: IPv4Address,
    ctx: ForwardingContext,
) -> ForwardDecision:
    """Check egress state, resolve ARP, emit the frame."""
    failure = ctx.topology.egress_failure(InterfaceRef(device.id, egress))
    if failure is not None:
        ctx.hop(
            device,
            HopKind.DROP,
            f"egress {egress} cannot transmit: "
            f"{ctx.topology.describe_failure(InterfaceRef(device.id, egress))}",
            egress=egress,
            ttl_in=packet.ttl,
        )
        return ForwardDecision.drop(failure)
    outcome = ctx.resolve_arp(device, egress, next_hop)
    if outcome.mac is None:
        reason = outcome.failure or DropReason.ARP_FAILED
        ctx.hop(
            device,
            HopKind.DROP,
            f"cannot resolve {next_hop} on {egress} ({reason.value})",
            egress=egress,
            ttl_in=packet.ttl,
        )
        return ForwardDecision.drop(reason)
    iface = device.get_interface(egress)
    frame = ctx.make_frame(iface.mac, outcome.mac, packet)
    return ForwardDecision.forward(egress, frame)
