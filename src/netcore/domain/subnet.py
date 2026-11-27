"""Subnet value entity (NETWORK_SPEC §2.1)."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

from netcore.domain.errors import (
    AddressNotInSubnetError,
    InvalidNextHopError,
    ReservedAddressError,
)
from netcore.domain.ids import SubnetId

_P2P = 31
_HOST = 32


@dataclass(slots=True)
class Subnet:
    """An IPv4 subnet managed by IPAM."""

    id: SubnetId
    network: IPv4Network
    name: str = ""
    gateway: IPv4Address | None = None
    parent_id: SubnetId | None = None

    def __post_init__(self) -> None:
        if self.gateway is not None:
            if self.gateway not in self.network:
                raise InvalidNextHopError(
                    f"Gateway {self.gateway} is outside subnet {self.network}."
                )
            self.is_reserved(self.gateway, raise_error=True)

    def contains(self, ip: IPv4Address) -> bool:
        """Integer membership test."""
        return ip in self.network

    def usable_hosts(self) -> int:
        """Number of assignable host addresses."""
        prefix = self.network.prefixlen
        if prefix == _HOST:
            return 1
        if prefix == _P2P:
            return 2
        return self.network.num_addresses - 2

    def is_reserved(self, ip: IPv4Address, raise_error: bool = False) -> bool:
        """True if ``ip`` is the network or broadcast address (prefix ≤ 30)."""
        if self.network.prefixlen >= _P2P:
            return False
        if ip == self.network.network_address:
            if raise_error:
                raise ReservedAddressError(
                    f"{ip} is the network address of {self.network}."
                )
            return True
        if ip == self.network.broadcast_address:
            if raise_error:
                raise ReservedAddressError(
                    f"{ip} is the broadcast address of {self.network}."
                )
            return True
        return False

    def validate_host(self, ip: IPv4Address, loopback: bool = False) -> None:
        """Raise if ``ip`` cannot be assigned to a host in this subnet."""
        if ip not in self.network:
            raise AddressNotInSubnetError(f"{ip} is outside subnet {self.network}.")
        if self.network.prefixlen == _HOST and not loopback:
            raise ReservedAddressError(
                f"/32 subnet {self.network} may only be used on loopback interfaces."
            )
        self.is_reserved(ip, raise_error=True)

    def hosts(self) -> list[IPv4Address]:
        """All assignable host addresses in order."""
        if self.network.prefixlen >= _P2P:
            return list(self.network)
        return list(self.network.hosts())
