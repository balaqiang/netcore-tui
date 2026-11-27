"""Synchronous in-process publish/subscribe (DEC-013)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from netcore.domain.enums import EventCategory
from netcore.domain.events import NetworkEvent

Handler = Callable[[NetworkEvent], None]
Unsubscribe = Callable[[], None]

_log = logging.getLogger("netcore.event_bus")


class EventBus:
    """Handlers must be fast; their exceptions are logged, never propagated."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: list[tuple[EventCategory | None, Handler]] = []

    def subscribe(
        self, category: EventCategory | None, handler: Handler
    ) -> Unsubscribe:
        """Subscribe to one category (or all with ``None``)."""
        entry = (category, handler)
        with self._lock:
            self._subs.append(entry)

        def unsubscribe() -> None:
            with self._lock:
                if entry in self._subs:
                    self._subs.remove(entry)

        return unsubscribe

    def publish(self, event: NetworkEvent) -> None:
        """Deliver ``event`` to matching handlers."""
        with self._lock:
            targets = [h for c, h in self._subs if c is None or c is event.category]
        for handler in targets:
            try:
                handler(event)
            except Exception:
                _log.exception("event handler failed")
