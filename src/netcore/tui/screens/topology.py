"""Network Topology (6)."""

from __future__ import annotations

from typing import Any, ClassVar

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static

from netcore.application.dto import ConnectRequest, DeviceDTO, LinkDTO, TopologyDTO
from netcore.application.errors import ApplicationError
from netcore.tui.formatting import muted, status_text, up_text
from netcore.tui.modals.forms import LinkFormModal
from netcore.tui.screens.base import BaseScreen
from netcore.tui.widgets.tables import NetTable
from netcore.tui.widgets.topology_canvas import TopologyCanvas


def parse_capacity(text: str) -> int | None:
    """Input-shape check for capacity."""
    text = text.strip()
    if not text:
        return None
    if not text.isdigit():
        raise ApplicationError("NET013", "Capacity must be a whole number of Mbps.")
    return int(text)


class TopologyScreen(BaseScreen):
    """Layered topology view, links, failure injection (UI_SPEC §5.6)."""

    SCREEN_ID: ClassVar[str] = "topology"
    TITLE = "Network Topology"

    BINDINGS: ClassVar[list[BindingType]] = [
        *BaseScreen.BINDINGS,
        Binding("l", "add_link", "Add link"),
        Binding("u", "toggle_link", "Link up/down"),
        Binding("h", "toggle_highlight", "Path highlight"),
        Binding("t", "toggle_view", "Canvas/list"),
    ]

    def __init__(self, services: Any) -> None:
        super().__init__(services)
        self._topo = TopologyDTO((), ())

    def compose_content(self) -> ComposeResult:
        with Horizontal(classes="split"):
            with Vertical():
                yield TopologyCanvas()
                yield NetTable("Link", "Capacity", "State", table_id="link-table")
            detail = Static("", id="topology-detail", classes="panel detail")
            detail.border_title = "Device"
            yield detail

    def on_mount(self) -> None:
        """Focus the canvas."""
        super().on_mount()
        self.query_one(TopologyCanvas).focus()

    def action_refresh(self) -> None:
        """Reload the snapshot."""
        self.call_service(self.services.topology.snapshot, self._populate)

    def _populate(self, topo: TopologyDTO) -> None:
        self._topo = topo
        self.query_one(TopologyCanvas).load(topo)
        table = self.query_one("#link-table", NetTable)
        keep = table.selected_key()
        table.clear()
        for link in topo.links:
            state = up_text(
                link.operational, "up", "down" if not link.admin_up else "inactive"
            )
            table.add_row(
                link.label, f"{link.capacity_mbps} Mbps", state, key=str(link.id)
            )
        table.select_key(keep)
        self._show_node()

    def on_topology_canvas_node_selected(
        self, message: TopologyCanvas.NodeSelected
    ) -> None:
        """Show device detail; enter loads full detail."""
        if message.opened:
            self.call_service(
                lambda: self.services.devices.get_device(message.node_id),
                self._show_device,
                "device",
            )
        else:
            self._show_node()

    def _show_node(self) -> None:
        node = self.query_one(TopologyCanvas).selected
        panel = self.query_one("#topology-detail", Static)
        if node is None:
            panel.update(muted("No device selected."))
            return
        links = [
            lk for lk in self._topo.links if node.id in (lk.a_device_id, lk.b_device_id)
        ]
        lines = [
            Text(f"{node.hostname}  ", style="bold") + status_text(node.status),
            Text(node.device_type.value.lower()),
        ]
        lines += [Text(f"  {lk.label}") for lk in links] or [muted("  no links")]
        lines.append(muted("enter: interfaces · l: add link · u: toggle link"))
        panel.update(Group(*lines))

    def _show_device(self, d: DeviceDTO) -> None:
        lines = [Text(f"{d.hostname}  ", style="bold") + status_text(d.status)]
        for i in d.interfaces:
            line = Text(f"{i.name:<8} ") + up_text(i.operational)
            line.append(f"  {i.address or '-'}")
            if i.peer:
                line.append(f" ↔ {i.peer}")
            lines.append(line)
        self.query_one("#topology-detail", Static).update(Group(*lines))

    def _selected_link(self) -> LinkDTO | None:
        key = self.query_one("#link-table", NetTable).selected_key()
        return next((lk for lk in self._topo.links if str(lk.id) == key), None)

    def action_toggle_link(self) -> None:
        """Cable failure injection (US-TOP-2)."""
        link = self._selected_link()
        if link is None:
            self.notify(
                "Select a link in the table (tab to focus it).",
                severity="warning",
                timeout=4,
            )
            return
        up = not link.admin_up
        if self.do_command(
            lambda: self.services.topology.set_link_admin(link.id, up),
            f"Link {link.label} {'up' if up else 'down'}",
        ):
            self.action_refresh()

    def action_toggle_highlight(self) -> None:
        """Toggle last-path highlight."""
        canvas = self.query_one(TopologyCanvas)
        canvas.highlight_path = not canvas.highlight_path
        canvas.refresh()

    def action_toggle_view(self) -> None:
        """Canvas ↔ adjacency list."""
        canvas = self.query_one(TopologyCanvas)
        canvas.list_mode = not canvas.list_mode
        canvas.refresh(layout=True)

    def action_add_link(self) -> None:
        """Open link form with free interfaces."""
        devices = self.do_command(self.services.devices.list_devices)
        if not devices or devices is True or len(devices) < 2:
            self.notify("Need at least two devices.", severity="warning", timeout=4)
            return
        options = [(d.hostname, d.id) for d in devices]
        free = {
            d.id: [i.name for i in d.interfaces if i.link_id is None] for d in devices
        }
        settings = self.services.settings.get()

        def submit(v: dict[str, Any]) -> LinkDTO:
            if v["device_a"] is None or v["device_b"] is None:
                raise ApplicationError("NET013", "Choose both devices.")
            return self.services.topology.connect(
                ConnectRequest(
                    v["device_a"],
                    v["interface_a"] or "",
                    v["device_b"],
                    v["interface_b"] or "",
                    parse_capacity(v["capacity"]),
                )
            )

        self.app.push_screen(
            LinkFormModal(submit, options, free, settings.default_capacity_mbps),
            lambda r: self.action_refresh() if r else None,
        )

    def on_data_table_row_highlighted(self, _event: DataTable.RowHighlighted) -> None:
        """Nothing extra; link selection is read on demand."""
