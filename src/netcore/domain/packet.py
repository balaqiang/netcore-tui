"""Packet (L3), ARP message and Frame (L2) — NETWORK_SPEC §5."""

from __future__ import annotations

from dataclasses import dataclass, replace
from ipaddress import IPv4Address

from netcore.domain.addressing import MacAddress
from netcore.domain.enums import ArpOp, Protocol
from netcore.domain.errors import InvalidValueError

MIN_TTL = 1
MAX_TTL = 255
MIN_SIZE = 64
MAX_SIZE = 9000
MAX_PAYLOAD = 128


@dataclass(frozen=True, slots=True)
class Packet:
    """Immutable IPv4 packet."""

    packet_id: int
    src_ip: IPv4Address
    dst_ip: IPv4Address
    protocol: Protocol = Protocol.ICMP
    ttl: int = 64
    size_bytes: int = 64
    payload: str = ""

    def __post_init__(self) -> None:
        if not MIN_TTL <= self.ttl <= MAX_TTL:
            raise InvalidValueError(f"TTL {self.ttl} must be between 1 and 255.")
        if not MIN_SIZE <= self.size_bytes <= MAX_SIZE:
            raise InvalidValueError(
                f"Packet size {self.size_bytes} must be between 64 and 9000 bytes."
            )
        if len(self.payload) > MAX_PAYLOAD:
            raise InvalidValueError("Payload label must be at most 128 characters.")

    def with_ttl(self, ttl: int) -> Packet:
        """Return a copy with a new TTL."""
        return replace(self, ttl=ttl)


@dataclass(frozen=True, slots=True)
class ArpMessage:
    """Simulated ARP request/reply."""

    op: ArpOp
    sender_ip: IPv4Address
    sender_mac: MacAddress
    target_ip: IPv4Address
    target_mac: MacAddress | None = None


@dataclass(frozen=True, slots=True)
class Frame:
    """Immutable Ethernet frame."""

    frame_id: int
    src_mac: MacAddress
    dst_mac: MacAddress
    payload: Packet | ArpMessage

    def is_broadcast(self) -> bool:
        """True if destined to ``ff:ff:ff:ff:ff:ff``."""
        return self.dst_mac.is_broadcast
