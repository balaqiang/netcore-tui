"""TUI fixtures: real service stack over a temporary SQLite file."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

from netcore.bootstrap import Container, build_container
from netcore.infrastructure.config import AppConfig
from netcore.tui.app import NetCoreApp


@pytest.fixture
def container_factory(tmp_path) -> Iterator[Callable[..., Container]]:
    made: list[Container] = []

    def make(seed: str | None = "two-router") -> Container:
        db = tmp_path / f"tui-{len(made)}.db"
        c = build_container(AppConfig(db_path=str(db), log_path=None, seed_lab=seed))
        made.append(c)
        return c

    yield make
    for c in made:
        c.close()


@pytest.fixture
def app_factory(container_factory) -> Callable[..., NetCoreApp]:
    def make(seed: str | None = "two-router") -> NetCoreApp:
        return NetCoreApp(container_factory(seed).services)

    return make


async def settle(app: NetCoreApp, pilot, rounds: int = 3) -> None:
    """Let workers finish and messages drain."""
    for _ in range(rounds):
        await pilot.pause()
        await app.workers.wait_for_complete()
    await pilot.pause()
