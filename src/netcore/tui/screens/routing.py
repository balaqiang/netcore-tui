"""Routing Table (4)."""

from __future__ import annotations

from typing import Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.widgets import Input, Select, Static

from netcore.application.dto import AddRouteRequest, RouteDTO, RouteLookupDTO
from netcore.application.errors import ApplicationError
from netcore.tui.formatting import color
from netcore.tui.modals.base import ConfirmModal
from netcore.tui.modals.forms import RouteFormModal
from netcore.tui.screens.base import BaseScreen
from netcore.tui.widgets.form import select_value
from netcore.tui.widgets.tables import NetTable


def parse_metric(text: str) -> int:
    """Input-shape check for the metric field."""
    text = text.strip() or "0"
    if not text.isdigit():
        raise ApplicationError("NET022", "Metric must be a whole number 0-65535.")
    return int(text)


class RoutingScreen(BaseScreen):
    """Routing table + lookup tool (UI_SPEC §5.4)."""

    SCREEN_ID: ClassVar[str] = "routing"
    TITLE = "Routing Table"
    REFRESH_CATEGORIES: ClassVar[frozenset[str] | None] = frozenset(
        {"CONFIG", "SYSTEM"}
    )

    BINDINGS: ClassVar[list[BindingType]] = [
        *BaseScreen.BINDINGS,
        Binding("n", "add_route", "Add route"),
        Binding("d", "delete_route", "Delete"),
        Binding("delete", "delete_route", "Delete", show=False),
        Binding("slash", "lookup", "Lookup"),
    ]

    def __init__(self, services: Any) -> None:
        super().__init__(services)
        self._routes: list[RouteDTO] = []
        self._router_ids: list[int] = []

    def compose_content(self) -> ComposeResult:
        with Horizontal(classes="toolbar"):
            yield Select([], prompt="Router", id="router-select")
        yield Static(
            "No routers yet — add one in Devices (2).",
            id="routing-empty",
            classes="hint",
        )
        yield NetTable(
            "Type",
            "Destination",
            "Next Hop",
            "Interface",
            "AD",
            "Metric",
            table_id="route-table",
        )
        with Horizontal(classes="toolbar"):
            yield Input(placeholder="/ lookup dst IP, e.g. 10.1.2.5", id="lookup-input")
            yield Static("", id="lookup-result")

    def _router_id(self) -> int | None:
        return select_value(self.query_one("#router-select", Select))

    def action_refresh(self) -> None:
        """Reload routers, then routes."""
        self.call_service(self.services.routing.routers, self._render_routers)

    def _render_routers(self, routers: list[tuple[int, str]]) -> None:
        select = self.query_one("#router-select", Select)
        ids = [r[0] for r in routers]
        current = self._router_id()
        if ids != self._router_ids:
            self._router_ids = ids
            select.set_options([(name, rid) for rid, name in routers])
        if routers and current not in ids:
            select.value = routers[0][0]
        self.query_one("#routing-empty").display = not routers
        self._load_routes()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Router changed."""
        if event.select.id == "router-select":
            self._load_routes()

    def _load_routes(self) -> None:
        rid = self._router_id()
        if rid is None:
            self._render_routes([])
            return
        self.call_service(
            lambda: self.services.routing.routes(rid), self._render_routes, "routes"
        )

    def _render_routes(self, routes: list[RouteDTO]) -> None:
        self._routes = routes
        table = self.query_one("#route-table", NetTable)
        keep = table.selected_key()
        table.clear()
        for r in routes:
            dim = "" if r.removable else color("secondary")
            cells = [
                r.type_code,
                r.destination,
                r.next_hop or "connected",
                r.interface,
                str(r.admin_distance),
                str(r.metric),
            ]
            table.add_row(*(Text(c, style=dim) for c in cells), key=str(r.id))
        table.select_key(keep)

    def action_lookup(self) -> None:
        """Focus lookup input."""
        self.query_one("#lookup-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Run route lookup."""
        if event.input.id != "lookup-input":
            return
        rid = self._router_id()
        if rid is None:
            return
        result = self.do_command(lambda: self.services.routing.lookup(rid, event.value))
        if isinstance(result, RouteLookupDTO):
            out = self.query_one("#lookup-result", Static)
            if result.matched is None:
                out.update(Text(f"✖ {result.message}", style=color("error")))
            else:
                out.update(Text(f"✔ {result.message}", style=color("success")))
                self.query_one("#route-table", NetTable).select_key(
                    str(result.matched.id)
                )

    def action_add_route(self) -> None:
        """Open route form."""
        rid = self._router_id()
        if rid is None:
            self.notify("Select a router first.", severity="warning", timeout=4)
            return
        device = self.do_command(lambda: self.services.devices.get_device(rid))
        if device is None:
            return
        interfaces = [i.name for i in device.interfaces]

        def submit(v: dict[str, Any]) -> RouteDTO:
            return self.services.routing.add_static_route(
                AddRouteRequest(
                    rid,
                    v["destination"],
                    v["next_hop"],
                    v["interface"],
                    parse_metric(v["metric"]),
                )
            )

        self.app.push_screen(RouteFormModal(submit, interfaces), self._after)

    def action_delete_route(self) -> None:
        """Delete selected static route (connected are read-only)."""
        rid = self._router_id()
        key = self.query_one("#route-table", NetTable).selected_key()
        route = next((r for r in self._routes if str(r.id) == key), None)
        if rid is None or route is None:
            return
        if not route.removable:
            self.notify(
                "Connected routes are derived from interface addresses.",
                severity="warning",
                timeout=4,
            )
            return

        def confirmed(ok: bool | None) -> None:
            if ok and self.do_command(
                lambda: self.services.routing.remove_route(rid, route.id),
                "Route removed",
            ):
                self.action_refresh()

        self.app.push_screen(
            ConfirmModal(
                "Delete route",
                [f"Delete {route.destination} via {route.next_hop}?"],
                confirm_label="Delete",
            ),
            confirmed,
        )

    def _after(self, result: object) -> None:
        if result:
            self.notify("Route added", timeout=4)
            self._load_routes()
