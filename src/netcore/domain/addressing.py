"""Addressing value objects and validators (NETWORK_SPEC §2)."""

from __future__ import annotations

import ipaddress
import random
import re
from collections.abc import Iterable
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Interface, IPv4Network

from netcore.domain.errors import (
    InvalidAddressError,
    InvalidSubnetError,
    InvalidValueError,
)

_DOTTED_QUAD = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_HOSTNAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$")
_HOSTNAME_MAX = 63
_MAX_PREFIX = 32

LAB_RANGES: tuple[IPv4Network, ...] = tuple(
    IPv4Network(n)
    for n in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",
        "192.0.2.0/24",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "127.0.0.0/8",
    )
)


def _check_dotted(text: str, original: str) -> None:
    if not _DOTTED_QUAD.match(text):
        raise InvalidAddressError(f'"{original}" is not a valid IPv4 address.')
    for octet in text.split("."):
        if len(octet) > 1 and octet.startswith("0"):
            raise InvalidAddressError(
                f'"{original}" is not a valid IPv4 address (leading zeros).'
            )
        if int(octet) > 255:
            raise InvalidAddressError(f'"{original}" is not a valid IPv4 address.')


def _split_prefix(text: str, original: str) -> tuple[str, int]:
    if text.count("/") != 1:
        raise InvalidAddressError(f'"{original}" must be in CIDR form a.b.c.d/nn.')
    addr, prefix = text.split("/")
    if not prefix.isdigit() or (len(prefix) > 1 and prefix.startswith("0")):
        raise InvalidAddressError(f'"{original}" has an invalid prefix length.')
    value = int(prefix)
    if value > _MAX_PREFIX:
        raise InvalidAddressError(f'"{original}" prefix must be between 0 and 32.')
    _check_dotted(addr, original)
    return addr, value


def parse_ipv4_address(text: str) -> IPv4Address:
    """Parse a dotted-quad IPv4 address strictly (no spaces/leading zeros)."""
    if not isinstance(text, str) or text == "":
        raise InvalidAddressError('"" is not a valid IPv4 address.')
    _check_dotted(text, text)
    return IPv4Address(text)


def parse_ipv4_interface(text: str) -> IPv4Interface:
    """Parse an interface address ``a.b.c.d/nn``."""
    if not isinstance(text, str) or text == "":
        raise InvalidAddressError('"" is not a valid interface address.')
    addr, prefix = _split_prefix(text, text)
    return IPv4Interface(f"{addr}/{prefix}")


def parse_ipv4_network(text: str) -> IPv4Network:
    """Parse a subnet strictly; host bits set raises ``InvalidSubnetError``."""
    if not isinstance(text, str) or text == "":
        raise InvalidSubnetError('"" is not a valid subnet.')
    addr, prefix = _split_prefix(text, text)
    try:
        return IPv4Network(f"{addr}/{prefix}", strict=True)
    except ValueError:
        suggestion = IPv4Network(f"{addr}/{prefix}", strict=False)
        raise InvalidSubnetError(
            f'"{text}" has host bits set; did you mean {suggestion}?'
        ) from None


def is_lab_range(ip: IPv4Address) -> bool:
    """True if ``ip`` lies in a range recommended for labs (§2.1)."""
    return any(ip in net for net in LAB_RANGES)


def validate_hostname(name: str) -> str:
    """Validate a hostname per FR-DEV-02 and return it unchanged."""
    if not name or len(name) > _HOSTNAME_MAX or not _HOSTNAME.match(name):
        raise InvalidValueError(
            f'Hostname "{name}" is invalid (1-63 chars, letters, digits, '
            "hyphens; must not start or end with a hyphen)."
        )
    return name


@dataclass(frozen=True, slots=True, order=True)
class MacAddress:
    """Canonical MAC address ``aa:bb:cc:dd:ee:ff`` (lowercase)."""

    value: str

    BROADCAST_TEXT = "ff:ff:ff:ff:ff:ff"

    @classmethod
    def parse(cls, text: str) -> MacAddress:
        """Parse ``:``, ``-`` or Cisco ``.`` separated MAC, any case."""
        raw = text.strip().lower() if isinstance(text, str) else ""
        if re.fullmatch(r"[0-9a-f]{2}([:-])[0-9a-f]{2}(\1[0-9a-f]{2}){4}", raw):
            digits = re.sub(r"[:-]", "", raw)
        elif re.fullmatch(r"[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}", raw):
            digits = raw.replace(".", "")
        else:
            raise InvalidAddressError(f'"{text}" is not a valid MAC address.')
        return cls(":".join(digits[i : i + 2] for i in range(0, 12, 2)))

    @classmethod
    def broadcast(cls) -> MacAddress:
        """The broadcast MAC ``ff:ff:ff:ff:ff:ff``."""
        return cls(cls.BROADCAST_TEXT)

    @property
    def is_broadcast(self) -> bool:
        """True for ``ff:ff:ff:ff:ff:ff``."""
        return self.value == self.BROADCAST_TEXT

    @property
    def is_multicast(self) -> bool:
        """True if the I/G bit (LSB of first octet) is set."""
        return bool(int(self.value[:2], 16) & 1)

    def ensure_assignable(self) -> MacAddress:
        """Raise if this MAC is broadcast or multicast."""
        if self.is_broadcast or self.is_multicast:
            raise InvalidAddressError(
                f"{self.value} is a broadcast/multicast MAC and cannot be assigned."
            )
        return self

    def __str__(self) -> str:
        return self.value


class MacGenerator:
    """Deterministic locally administered unicast MACs (``02:xx:..``)."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def generate(self, existing: Iterable[MacAddress]) -> MacAddress:
        """Return a MAC not contained in ``existing``."""
        taken = set(existing)
        while True:
            octets = [0x02, *(self._rng.randrange(256) for _ in range(5))]
            mac = MacAddress(":".join(f"{o:02x}" for o in octets))
            if mac not in taken:
                return mac


def network_of(addr: IPv4Interface) -> IPv4Network:
    """Network part of an interface address."""
    return addr.network


def ip_in(ip: IPv4Address, network: IPv4Network) -> bool:
    """Integer membership test (never string prefix comparison)."""
    return ip in network


__all__ = [
    "LAB_RANGES",
    "IPv4Address",
    "IPv4Interface",
    "IPv4Network",
    "MacAddress",
    "MacGenerator",
    "ip_in",
    "ipaddress",
    "is_lab_range",
    "network_of",
    "parse_ipv4_address",
    "parse_ipv4_interface",
    "parse_ipv4_network",
    "validate_hostname",
]
