"""Clock implementations (DEC-012)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class SystemClock:
    """Wall-clock UTC time."""

    def now(self) -> datetime:
        """Current UTC time."""
        return datetime.now(UTC)


class FixedClock:
    """Deterministic clock for tests; can be advanced."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        """The fixed time."""
        return self._now

    def advance(self, seconds: float) -> None:
        """Move time forward."""
        self._now += timedelta(seconds=seconds)
