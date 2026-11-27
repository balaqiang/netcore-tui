"""Reference topology of NETWORK_SPEC §13 (srv-a ↔ sw-a ↔ r1 ↔ r2 ↔ sw-b ↔ srv-b)."""

from __future__ import annotations

import random

from netcore.domain.labs import build_two_router_lab
from netcore.domain.topology import NetworkTopology

LAB_SEED = 1234


def make_two_router_lab(seed: int = LAB_SEED) -> NetworkTopology:
    """Fresh copy of the reference lab."""
    return build_two_router_lab(random.Random(seed))
