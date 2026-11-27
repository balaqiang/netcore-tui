"""Simulation constants (NETWORK_SPEC §9, §10.3). Values are *simulated*."""

from __future__ import annotations

from dataclasses import dataclass

SWITCH_PROCESSING_MS = 0.01
ROUTER_PROCESSING_MS = 0.05
ARP_FRAME_BYTES = 64
ARP_FRAMES_PER_EXCHANGE = 2

DEFAULT_TTL = 64
DEFAULT_MAX_HOPS = 64
MIN_MAX_HOPS = 8
MAX_MAX_HOPS = 255
DEFAULT_ARP_TIMEOUT_S = 300
DEFAULT_MAC_TIMEOUT_S = 300
MIN_TABLE_TIMEOUT_S = 10
MAX_TABLE_TIMEOUT_S = 3600


@dataclass(frozen=True, slots=True)
class SimulationSettings:
    """Tunables injected into the engine."""

    default_ttl: int = DEFAULT_TTL
    max_hops: int = DEFAULT_MAX_HOPS
    arp_timeout_s: int = DEFAULT_ARP_TIMEOUT_S
    mac_timeout_s: int = DEFAULT_MAC_TIMEOUT_S
