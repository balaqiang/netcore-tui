"""Textual Pilot tests (UI_SPEC §10), incl. AT-12."""

from __future__ import annotations

import pytest
from textual.widgets import DataTable, Input, Static

from netcore.application.dto import DeviceStatus
from netcore.tui.widgets.port_grid import PortGrid
from tests.tui.conftest import settle

SIZE = (130, 40)
SCREEN_KEYS = [
    ("1", "dashboard"),
    ("2", "devices"),
    ("3", "ipam"),
    ("4", "routing"),
    ("5", "switch-ports"),
    ("6", "topology"),
    ("7", "packet-lab"),
    ("8", "traffic"),
    ("9", "events"),
    ("0", "settings"),
]


async def test_at12_keyboard_navigation(app_factory):
    """AT-12 — all 10 screens reachable with number keys, no mouse."""
    app = app_factory()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert app.screen.id == "dashboard"
        for key, screen_id in [*SCREEN_KEYS, *reversed(SCREEN_KEYS)]:
            await pilot.press(key)
            await settle(app, pilot, 1)
            assert app.screen.id == screen_id


async def test_too_small_terminal(app_factory):
    app = app_factory()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(app, pilot)
        warning = app.screen.query_one("#too-small", Static)
        assert warning.display
        assert "need 100×30, have 80×24" in str(warning.render())  # noqa: RUF001
        assert not app.screen.query_one("#body").display


async def test_min_size_layout_is_shown(app_factory):
    app = app_factory()
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        assert not app.screen.query_one("#too-small", Static).display
        assert app.screen.has_class("-stacked")


@pytest.mark.parametrize(
    ("screen_key", "action_key", "modal_id"),
    [
        ("2", "n", "device-form"),
        ("3", "n", "subnet-form"),
        ("3", "a", "assign-form"),
        ("4", "n", "route-form"),
        ("6", "l", "link-form"),
        ("8", "f", "flow-form"),
        ("9", "E", "export"),
        ("1", "question_mark", "help"),
    ],
)
async def test_modals_open_and_escape(app_factory, screen_key, action_key, modal_id):
    app = app_factory()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press(screen_key)
        await settle(app, pilot)
        current = app.screen.id
        await pilot.press(action_key)
        await settle(app, pilot, 1)
        assert app.screen.id == modal_id
        await pilot.press("3")  # number keys do not navigate under a modal
        assert app.screen.id == modal_id
        await pilot.press("escape")
        await settle(app, pilot, 1)
        assert app.screen.id == current


async def test_device_add_flow_end_to_end(app_factory):
    app = app_factory(seed=None)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("2")
        await settle(app, pilot)
        assert app.screen.query_one("#devices-empty").display
        await pilot.press("n")
        await settle(app, pilot, 1)
        await pilot.press(*"core-r1")
        await pilot.press("ctrl+s")
        await settle(app, pilot)
        assert app.screen.id == "devices"
        table = app.screen.query_one("#device-table", DataTable)
        assert table.row_count == 1
        assert not app.screen.query_one("#devices-empty").display
        names = [d.hostname for d in app.services.devices.list_devices()]
        assert names == ["core-r1"]


async def test_device_form_inline_error(app_factory):
    app = app_factory()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("2", "n")
        await settle(app, pilot, 1)
        await pilot.press(*"srv-a", "ctrl+s")
        await settle(app, pilot, 1)
        assert app.screen.id == "device-form"
        err = app.screen.query_one("#field-hostname .field-error", Static)
        assert "already exists" in str(err.render())
        assert app.screen.query_one("#in-hostname", Input).has_class("-invalid")


async def test_status_cycle_and_delete(app_factory):
    app = app_factory()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("2")
        await settle(app, pilot)
        await pilot.press("s")
        await settle(app, pilot)
        first = app.services.devices.list_devices()[0]
        assert first.status is DeviceStatus.OFFLINE
        await pilot.press("d")
        await settle(app, pilot, 1)
        assert app.screen.id == "confirm"
        await pilot.press("y")
        await settle(app, pilot)
        assert first.hostname not in [
            d.hostname for d in app.services.devices.list_devices()
        ]


async def test_packet_lab_delivers(app_factory):
    """UI_SPEC §10 — submit form, wait for worker, result shows DELIVERED."""
    app = app_factory()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("7")
        await settle(app, pilot)
        await pilot.click("#dst-input")
        await pilot.press(*"10.0.2.10", "enter")
        await settle(app, pilot)
        result = str(app.screen.query_one("#sim-result", Static).render())
        assert "DELIVERED" in result
        assert app.screen.query_one("#hop-table", DataTable).row_count >= 5
        await pilot.press("ctrl+h")
        await settle(app, pilot)
        assert app.screen.query_one("#history-table", DataTable).row_count == 1


async def test_packet_lab_ttl_validation(app_factory):
    app = app_factory()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("7")
        await settle(app, pilot)
        app.screen.query_one("#ttl-input", Input).value = "0"
        app.screen.query_one("#dst-input", Input).value = "10.0.2.10"
        app.screen.action_send()
        await settle(app, pilot)
        assert "TTL must be 1-255" in str(
            app.screen.query_one("#sim-result", Static).render()
        )


async def test_switch_port_toggle(app_factory):
    app = app_factory()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("5")
        await settle(app, pilot)
        grid = app.screen.query_one(PortGrid)
        grid.focus()
        await pilot.press("space")
        await settle(app, pilot)
        sw = app.services.switches.switches()[0][0]
        assert not app.services.switches.ports(sw)[0].admin_up


async def test_topology_link_toggle(app_factory):
    app = app_factory()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("6")
        await settle(app, pilot)
        app.screen.query_one("#link-table", DataTable).focus()
        await pilot.press("u")
        await settle(app, pilot)
        assert not app.services.topology.links()[0].admin_up


async def test_settings_load_lab_in_worker(app_factory):
    app = app_factory(seed=None)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("0")
        await settle(app, pilot)
        await pilot.press("ctrl+l")
        await settle(app, pilot, 1)
        assert app.screen.id == "confirm"
        await pilot.press("y")
        await settle(app, pilot, 5)
        assert len(app.services.devices.list_devices()) == 18


async def test_quit(app_factory):
    app = app_factory()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("q")
        await pilot.pause()
    assert app.return_code == 0 or app.return_code is None
