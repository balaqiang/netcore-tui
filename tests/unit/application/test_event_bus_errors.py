"""EventBus and ApplicationError (T-301)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from netcore.application.errors import ApplicationError, translate_errors
from netcore.application.event_bus import EventBus
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.errors import (
    DeviceNotFoundError,
    DuplicateMacError,
    InvalidPortError,
)
from netcore.domain.events import NetworkEvent


def _ev(cat: EventCategory) -> NetworkEvent:
    return NetworkEvent(
        timestamp=datetime.now(UTC), severity=Severity.INFO, category=cat, message="m"
    )


def test_bus_subscribe_filter_unsubscribe():
    bus = EventBus()
    got, all_ = [], []
    unsub = bus.subscribe(EventCategory.DROP, got.append)
    bus.subscribe(None, all_.append)
    bus.publish(_ev(EventCategory.DROP))
    bus.publish(_ev(EventCategory.CONFIG))
    unsub()
    unsub()
    bus.publish(_ev(EventCategory.DROP))
    assert len(got) == 1 and len(all_) == 3


def test_bus_handler_errors_are_isolated(caplog):
    bus = EventBus()
    ok = []

    def boom(_e):
        raise RuntimeError("x")

    bus.subscribe(None, boom)
    bus.subscribe(None, ok.append)
    bus.publish(_ev(EventCategory.SYSTEM))
    assert ok and "event handler failed" in caplog.text


@pytest.mark.parametrize(
    ("err", "kind"),
    [
        (DeviceNotFoundError("x"), "not_found"),
        (DuplicateMacError("x"), "conflict"),
        (InvalidPortError("x"), "validation"),
    ],
)
def test_translate_errors_keeps_code(err, kind):
    with pytest.raises(ApplicationError) as exc, translate_errors():
        raise err
    assert exc.value.code == err.code and exc.value.kind == kind
    assert exc.value.__cause__ is err
    assert err.code in str(exc.value)


def test_translate_value_error():
    with pytest.raises(ApplicationError) as exc, translate_errors():
        raise ValueError("bad")
    assert exc.value.code == "APP001"
