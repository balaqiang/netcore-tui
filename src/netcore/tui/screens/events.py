"""Event Logs (9)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import DataTable, Input, Select, Static

from netcore.application.dto import (
    EventCategory,
    EventDTO,
    EventFilterDTO,
    ExportResultDTO,
    Severity,
)
from netcore.tui.formatting import severity_text
from netcore.tui.modals.base import EventDetailModal
from netcore.tui.modals.forms import ExportModal
from netcore.tui.screens.base import BaseScreen
from netcore.tui.widgets.form import FilterBar
from netcore.tui.widgets.tables import NetTable

SEVERITY_FILTERS: dict[str, frozenset[Severity] | None] = {
    "all": None,
    "info+": frozenset(
        {Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.CRITICAL}
    ),
    "warning+": frozenset({Severity.WARNING, Severity.ERROR, Severity.CRITICAL}),
    "error+": frozenset({Severity.ERROR, Severity.CRITICAL}),
    "debug": frozenset({Severity.DEBUG}),
}


class EventsScreen(BaseScreen):
    """Filterable audit trail with export and live tail (UI_SPEC §5.9)."""

    SCREEN_ID: ClassVar[str] = "events"
    TITLE = "Event Logs"

    BINDINGS: ClassVar[list[BindingType]] = [
        *BaseScreen.BINDINGS,
        Binding("enter", "detail", "Detail", show=False),
        Binding("E", "export", "Export"),
        Binding("t", "toggle_tail", "Live tail"),
        Binding("slash", "search", "Search"),
    ]

    def __init__(self, services: Any) -> None:
        super().__init__(services)
        self._events: list[EventDTO] = []
        self._tail = True
        self._device_ids: list[int] = []

    def compose_content(self) -> ComposeResult:
        yield FilterBar(
            Select(
                [(k, k) for k in SEVERITY_FILTERS],
                value="info+",
                allow_blank=False,
                id="ev-severity",
            ),
            Select(
                [(c.value.title(), c) for c in EventCategory],
                prompt="Category",
                id="ev-category",
            ),
            Select([], prompt="Device", id="ev-device"),
            Select(
                [
                    ("last 15 m", "15m"),
                    ("last 1 h", "1h"),
                    ("last 24 h", "24h"),
                    ("all", "all"),
                ],
                value="all",
                allow_blank=False,
                id="ev-window",
            ),
            Input(placeholder="/ search text", id="ev-search"),
            bar_id="event-filter",
        )
        yield Static("", id="ev-status", classes="caption")
        yield NetTable(
            "Time (UTC)",
            "Severity",
            "Category",
            "Device",
            "Message",
            table_id="event-table",
        )

    def on_mount(self) -> None:
        """Focus the table."""
        super().on_mount()
        self.query_one("#event-table", DataTable).focus()

    def _filter(self) -> EventFilterDTO:
        v = self.query_one(FilterBar).values()
        return EventFilterDTO(
            severities=SEVERITY_FILTERS[v.get("ev-severity") or "all"],
            category=v.get("ev-category"),
            device_id=v.get("ev-device"),
            text=v.get("ev-search") or "",
            window=v.get("ev-window") or "all",
        )

    def action_refresh(self) -> None:
        """Re-query events and device filter options."""
        flt = self._filter()

        def load() -> tuple[list[EventDTO], list[tuple[int, str]]]:
            devices = [(d.id, d.hostname) for d in self.services.devices.list_devices()]
            return self.services.events.query(flt), devices

        self.call_service(load, self._populate)

    def on_filter_bar_filter_changed(self, _message: FilterBar.FilterChanged) -> None:
        """Filters changed."""
        self.action_refresh()

    def _populate(self, data: tuple[list[EventDTO], list[tuple[int, str]]]) -> None:
        events, devices = data
        select = self.query_one("#ev-device", Select)
        ids = [d[0] for d in devices]
        if ids != self._device_ids:
            self._device_ids = ids
            select.set_options([(name, did) for did, name in devices])
        self._events = events
        table = self.query_one("#event-table", NetTable)
        keep = table.selected_key()
        table.clear()
        for e in events:
            table.add_row(
                e.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                severity_text(e.severity),
                e.category.value,
                e.device_name or "-",
                e.message,
                key=str(e.id),
            )
        if self._tail:
            table.move_cursor(row=0)
        else:
            table.select_key(keep)
        tail = "live tail on (t)" if self._tail else "live tail off (t)"
        self.query_one("#ev-status", Static).update(f"{len(events)} events · {tail}")

    def on_domain_event(self, event: EventDTO) -> None:
        """Only auto-refresh while tailing."""
        if self._tail:
            super().on_domain_event(event)

    def action_toggle_tail(self) -> None:
        """Toggle auto-scroll on new events."""
        self._tail = not self._tail
        self.action_refresh()

    def action_search(self) -> None:
        """Focus search."""
        self.query_one("#ev-search", Input).focus()

    def _selected(self) -> EventDTO | None:
        key = self.query_one("#event-table", NetTable).selected_key()
        return next((e for e in self._events if str(e.id) == key), None)

    def on_data_table_row_selected(self, _event: DataTable.RowSelected) -> None:
        """enter on a row opens detail."""
        self.action_detail()

    def action_detail(self) -> None:
        """Event detail modal with JSON payload."""
        e = self._selected()
        if e is None:
            return
        header = (
            f"{e.timestamp.isoformat()}  {e.severity.value}  {e.category.value}  "
            f"{e.device_name or '-'}\n{e.message}"
        )
        self.app.push_screen(EventDetailModal(header, e.payload))

    def action_export(self) -> None:
        """Export filtered events."""
        flt = self._filter()

        def submit(v: dict[str, Any]) -> ExportResultDTO:
            return self.services.events.export(
                flt, v["fmt"] or "csv", v["path"], bool(v["overwrite"])
            )

        default = str(Path.home() / "netcore-events.csv")
        self.app.push_screen(ExportModal(submit, default), self._after_export)

    def _after_export(self, result: object) -> None:
        if isinstance(result, ExportResultDTO):
            self.notify(f"Exported {result.count} events to {result.path}", timeout=4)
