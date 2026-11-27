"""Audit events (NETWORK_SPEC §11)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from netcore.domain.enums import Direction, DropReason, EventCategory, Severity
from netcore.domain.ids import DeviceId, LinkId


@dataclass(frozen=True, slots=True, kw_only=True)
class NetworkEvent:
    """User-visible audit trail entry."""

    timestamp: datetime
    severity: Severity
    category: EventCategory
    message: str
    device_id: DeviceId | None = None
    payload: Mapping[str, object] = field(default_factory=dict)
    id: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TrafficEvent(NetworkEvent):
    """Counter delta produced by simulated traffic."""

    link_id: LinkId | None = None
    direction: Direction = Direction.TX
    packets: int = 0
    bytes: int = 0
    dropped: int = 0
    drop_reason: DropReason | None = None
