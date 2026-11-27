"""Per-device ARP cache (NETWORK_SPEC §7.1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from ipaddress import IPv4Address

from netcore.domain.addressing import MacAddress
from netcore.domain.enums import ArpEntryType

DEFAULT_ARP_TIMEOUT_S = 300


@dataclass(frozen=True, slots=True)
class ArpEntry:
    """One IP→MAC mapping."""

    ip: IPv4Address
    mac: MacAddress
    interface: str
    learned_at: datetime | None
    expires_at: datetime | None
    entry_type: ArpEntryType = ArpEntryType.DYNAMIC

    def is_valid(self, now: datetime) -> bool:
        """Static entries never expire; dynamic ones expire at ``expires_at``."""
        return self.expires_at is None or now < self.expires_at


class ArpTable:
    """ARP cache keyed by IP; expiry uses injected simulation time."""

    def __init__(self, timeout_s: int = DEFAULT_ARP_TIMEOUT_S) -> None:
        self._entries: dict[IPv4Address, ArpEntry] = {}
        self.timeout_s = timeout_s

    def get(self, ip: IPv4Address, now: datetime) -> MacAddress | None:
        """MAC for ``ip`` if a valid entry exists."""
        entry = self._entries.get(ip)
        if entry is None or not entry.is_valid(now):
            return None
        return entry.mac

    def learn(
        self,
        ip: IPv4Address,
        mac: MacAddress,
        interface: str,
        now: datetime,
        timeout_s: int | None = None,
    ) -> None:
        """Insert/refresh a dynamic entry (never overwrites a static one)."""
        current = self._entries.get(ip)
        if current is not None and current.entry_type is ArpEntryType.STATIC:
            return
        ttl = self.timeout_s if timeout_s is None else timeout_s
        self._entries[ip] = ArpEntry(
            ip, mac, interface, now, now + timedelta(seconds=ttl)
        )

    def add_static(self, ip: IPv4Address, mac: MacAddress, interface: str) -> None:
        """Insert a static entry that never expires."""
        self._entries[ip] = ArpEntry(
            ip, mac, interface, None, None, ArpEntryType.STATIC
        )

    def restore(self, entry: ArpEntry) -> None:
        """Re-insert a persisted entry verbatim."""
        self._entries[entry.ip] = entry

    def entries(self, now: datetime | None = None) -> tuple[ArpEntry, ...]:
        """Valid entries at ``now`` (all entries if ``now`` is None)."""
        items = sorted(self._entries.values(), key=lambda e: int(e.ip))
        if now is None:
            return tuple(items)
        return tuple(e for e in items if e.is_valid(now))

    def remove_interface(self, interface: str) -> None:
        """Drop entries learned on ``interface``."""
        self._entries = {
            ip: e for ip, e in self._entries.items() if e.interface != interface
        }

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
