"""Shared fixtures (QA_ENGINEER)."""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import UTC, datetime
from ipaddress import IPv4Address

import pytest

from netcore.domain.enums import Protocol
from netcore.domain.simulation.constants import SimulationSettings
from netcore.domain.simulation.engine import ForwardingEngine
from netcore.domain.simulation.result import PacketRequest
from netcore.domain.topology import NetworkTopology
from tests.fixtures.two_router_lab import make_two_router_lab

FIXED_NOW = datetime(2026, 11, 27, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def fixed_now() -> datetime:
    return FIXED_NOW


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


@pytest.fixture
def two_router_lab() -> NetworkTopology:
    return make_two_router_lab()


@pytest.fixture
def engine_factory(fixed_now: datetime) -> Callable[..., ForwardingEngine]:
    def factory(
        topology: NetworkTopology, settings: SimulationSettings | None = None
    ) -> ForwardingEngine:
        return ForwardingEngine(
            topology, settings or SimulationSettings(), random.Random(7), fixed_now
        )

    return factory


@pytest.fixture
def request_for() -> Callable[..., PacketRequest]:
    def make(
        topology: NetworkTopology,
        src: str,
        dst_ip: str,
        ttl: int = 64,
        protocol: Protocol = Protocol.ICMP,
        size: int = 64,
    ) -> PacketRequest:
        return PacketRequest(
            topology.require(src).id, IPv4Address(dst_ip), protocol, ttl, size
        )

    return make
