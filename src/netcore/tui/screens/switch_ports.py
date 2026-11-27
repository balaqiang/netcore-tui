"""Switch Port Management (5)."""

from __future__ import annotations

from typing import Any, ClassVar

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.widgets import Select, Static, TabbedContent, TabPane

from netcore.application.dto import MacEntryDTO, SwitchPortDTO, UpdatePortRequest
from netcore.tui.formatting import muted, up_text
from netcore.tui.modals.base import ConfirmModal
from netcore.tui.modals.forms import PortEditModal
from netcore.tui.screens.base import BaseScreen
from netcore.tui.widgets.form import select_value
from netcore.tui.widgets.port_grid import PortGrid
from netcore.tui.widgets.tables import NetTable

SPEEDS = (10, 100, 1000, 10000, 25000, 40000, 100000)


class SwitchPortsScreen(BaseScreen):
    """Port grid, port detail, MAC table (UI_SPEC §5.5)."""

    SCREEN_ID: ClassVar[str] = "switch-ports"
    TITLE = "Switch Port Management"
    REFRESH_CATEGORIES: ClassVar[frozenset[str] | None] = frozenset(
        {"CONFIG", "STATE", "SYSTEM"}
    )

    BINDINGS: ClassVar[list[BindingType]] = [
        *BaseScreen.BINDINGS,
        Binding("e", "edit_port", "Edit port"),
        Binding("c", "clear_mac", "Clear MAC table"),
    ]

    def __init__(self, services: Any) -> None:
        super().__init__(services)
        self._switch_ids: list[int] = []

    def compose_content(self) -> ComposeResult:
        with Horizontal(classes="toolbar"):
            yield Select([], prompt="Switch", id="switch-select")
        yield Static(
            "No switches yet — add one in Devices (2).",
            id="switch-empty",
            classes="hint",
        )
        with TabbedContent(id="switch-tabs"):
            with TabPane("Ports", id="tab-ports"):
                yield PortGrid()
                detail = Static("", id="port-detail", classes="panel")
                detail.border_title = "Port detail (space toggles admin state)"
                yield detail
            with TabPane("MAC table", id="tab-mac"):
                yield NetTable("MAC", "Port", "Age (sim s)", table_id="mac-table")

    def _switch_id(self) -> int | None:
        return select_value(self.query_one("#switch-select", Select))

    def action_refresh(self) -> None:
        """Reload switches, ports and MAC table."""
        self.call_service(self.services.switches.switches, self._render_switches)

    def _render_switches(self, switches: list[tuple[int, str]]) -> None:
        select = self.query_one("#switch-select", Select)
        ids = [s[0] for s in switches]
        current = self._switch_id()
        if ids != self._switch_ids:
            self._switch_ids = ids
            select.set_options([(name, sid) for sid, name in switches])
        if switches and current not in ids:
            select.value = switches[0][0]
        self.query_one("#switch-empty").display = not switches
        self._load()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Switch changed."""
        if event.select.id == "switch-select":
            self._load()

    def _load(self) -> None:
        sid = self._switch_id()
        if sid is None:
            self.query_one(PortGrid).load([])
            return
        self.call_service(
            lambda: self.services.switches.ports(sid),
            self.query_one(PortGrid).load,
            "ports",
        )
        self.call_service(
            lambda: self.services.switches.mac_table(sid), self._render_mac, "mac"
        )

    def _render_mac(self, entries: list[MacEntryDTO]) -> None:
        table = self.query_one("#mac-table", NetTable)
        table.clear()
        for e in entries:
            table.add_row(e.mac, str(e.port), str(e.age_s), key=e.mac)

    def on_port_grid_port_selected(self, message: PortGrid.PortSelected) -> None:
        """Show port detail."""
        del message
        port = self.query_one(PortGrid).selected
        panel = self.query_one("#port-detail", Static)
        if port is None:
            panel.update(muted("No port selected."))
            return
        panel.update(
            Group(
                Text(f"Port {port.number}", style="bold"),
                Text("admin   ") + up_text(port.admin_up),
                Text("link    ")
                + up_text(port.operational, "operational", "not operational"),
                Text(f"speed   {port.speed_mbps} Mbps"),
                Text(f"descr   {port.description or '-'}"),
                Text(f"peer    {port.peer or '-'}"),
                Text(
                    f"tx/rx   {port.tx_packets}/{port.rx_packets} packets (simulated)"
                ),
            )
        )

    def on_port_grid_port_toggle_requested(
        self, message: PortGrid.PortToggleRequested
    ) -> None:
        """space → toggle admin state."""
        sid = self._switch_id()
        port = self.query_one(PortGrid).selected
        if sid is None or port is None:
            return
        up = not port.admin_up
        if self.do_command(
            lambda: self.services.switches.set_port_admin(sid, message.number, up),
            f"port{message.number} admin {'up' if up else 'down'}",
        ):
            self._load()

    def action_edit_port(self) -> None:
        """Edit speed/description."""
        sid = self._switch_id()
        port = self.query_one(PortGrid).selected
        if sid is None or port is None:
            return

        def submit(v: dict[str, Any]) -> SwitchPortDTO:
            return self.services.switches.update_port(
                UpdatePortRequest(sid, port.number, v["speed"], v["description"])
            )

        self.app.push_screen(
            PortEditModal(submit, port.speed_mbps, port.description, SPEEDS),
            lambda r: self._load() if r else None,
        )

    def action_clear_mac(self) -> None:
        """Clear MAC table after confirmation."""
        sid = self._switch_id()
        if sid is None:
            return

        def confirmed(ok: bool | None) -> None:
            if ok and self.do_command(
                lambda: self.services.switches.clear_mac_table(sid), "MAC table cleared"
            ):
                self._load()

        self.app.push_screen(
            ConfirmModal("Clear MAC table", ["Remove all learned MAC entries?"]),
            confirmed,
        )
