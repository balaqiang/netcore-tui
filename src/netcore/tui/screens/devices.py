"""Device Management (2)."""

from __future__ import annotations

from typing import Any, ClassVar

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.widgets import DataTable, Input, Select, Static

from netcore.application.dto import (
    CreateDeviceRequest,
    DeviceDTO,
    DeviceFilter,
    DeviceStatus,
    DeviceType,
    UpdateDeviceRequest,
)
from netcore.application.errors import ApplicationError
from netcore.tui.formatting import TYPE_ICON, muted, status_text, up_text
from netcore.tui.modals.base import ConfirmModal
from netcore.tui.modals.forms import DeviceFormModal
from netcore.tui.screens.base import BaseScreen
from netcore.tui.widgets.form import FilterBar
from netcore.tui.widgets.tables import NetTable

EMPTY = "No devices yet — press n to add one or load a sample lab in Settings (0)."


def parse_count(text: str) -> int | None:
    """Input-shape check only; range validation is done by the service."""
    text = text.strip()
    if not text:
        return None
    if not text.isdigit():
        raise ApplicationError("UI001", "Interface count must be a whole number.")
    return int(text)


class DevicesScreen(BaseScreen):
    """CRUD + status cycling (UI_SPEC §5.2)."""

    SCREEN_ID: ClassVar[str] = "devices"
    TITLE = "Device Management"
    REFRESH_CATEGORIES: ClassVar[frozenset[str] | None] = frozenset(
        {"CONFIG", "STATE", "SYSTEM"}
    )

    BINDINGS: ClassVar[list[BindingType]] = [
        *BaseScreen.BINDINGS,
        Binding("n", "add", "New"),
        Binding("e", "edit", "Edit"),
        Binding("d", "delete", "Delete"),
        Binding("delete", "delete", "Delete", show=False),
        Binding("s", "cycle_status", "Status"),
        Binding("c", "clear_arp", "Clear ARP"),
        Binding("slash", "search", "Search"),
    ]

    def __init__(self, services: Any) -> None:
        super().__init__(services)
        self._devices: list[DeviceDTO] = []

    def compose_content(self) -> ComposeResult:
        yield FilterBar(
            Input(placeholder="/ search hostname, location…", id="device-search"),
            Select(
                [(t.value.title(), t) for t in DeviceType],
                prompt="Any type",
                id="device-type",
            ),
            Select(
                [(s.value.title(), s) for s in DeviceStatus],
                prompt="Any status",
                id="device-status",
            ),
            bar_id="device-filter",
        )
        yield Static(EMPTY, id="devices-empty", classes="hint")
        with Horizontal(classes="split"):
            yield NetTable(
                "Hostname",
                "Type",
                "Status",
                "Ifaces",
                "Location",
                "Description",
                table_id="device-table",
            )
            detail = Static("", id="device-detail", classes="panel detail")
            detail.border_title = "Interfaces"
            yield detail

    def on_mount(self) -> None:
        """Focus the table."""
        super().on_mount()
        self.query_one("#device-table", DataTable).focus()

    def _filter(self) -> DeviceFilter:
        values = self.query_one(FilterBar).values()
        return DeviceFilter(
            text=values.get("device-search") or "",
            device_type=values.get("device-type"),
            status=values.get("device-status"),
        )

    def action_refresh(self) -> None:
        """Reload devices."""
        flt = self._filter()
        self.call_service(
            lambda: self.services.devices.list_devices(flt), self._populate
        )

    def on_filter_bar_filter_changed(self, _message: FilterBar.FilterChanged) -> None:
        """Re-query with the new filter."""
        self.action_refresh()

    def _populate(self, devices: list[DeviceDTO]) -> None:
        self._devices = devices
        table = self.query_one("#device-table", NetTable)
        keep = table.selected_key()
        table.clear()
        for d in devices:
            table.add_row(
                d.hostname,
                f"{TYPE_ICON[d.device_type]} {d.device_type.value.lower()}",
                status_text(d.status),
                str(d.interface_count),
                d.location,
                d.description,
                key=str(d.id),
            )
        table.select_key(keep)
        empty = not devices and not any(self.query_one(FilterBar).values().values())
        self.query_one("#devices-empty").display = empty
        self._show_detail()

    def _selected(self) -> DeviceDTO | None:
        key = self.query_one("#device-table", NetTable).selected_key()
        return next((d for d in self._devices if str(d.id) == key), None)

    def on_data_table_row_highlighted(self, _event: DataTable.RowHighlighted) -> None:
        """Update the detail panel."""
        self._show_detail()

    def _show_detail(self) -> None:
        panel = self.query_one("#device-detail", Static)
        d = self._selected()
        if d is None:
            panel.update(muted("Select a device."))
            return
        lines: list[Text] = [
            Text(f"{d.hostname}  ", style="bold") + status_text(d.status)
        ]
        if d.default_gateway:
            lines.append(Text(f"gateway {d.default_gateway}"))
        for i in d.interfaces:
            line = Text(f"{i.name:<8} ")
            line.append_text(up_text(i.operational))
            line.append(f"  {i.address or '-'}")
            if i.peer:
                line.append(f" ↔ {i.peer}")
            lines.append(line)
            line = muted(f"         {i.mac}")
            lines.append(line)
        panel.update(Group(*lines))

    def action_search(self) -> None:
        """Focus the search input."""
        self.query_one("#device-search", Input).focus()

    def action_add(self) -> None:
        """Open the add form."""

        def submit(v: dict[str, Any]) -> DeviceDTO:
            return self.services.devices.create_device(
                CreateDeviceRequest(
                    v["hostname"],
                    v["type"],
                    parse_count(v["count"]),
                    v["location"],
                    v["description"],
                )
            )

        self.app.push_screen(DeviceFormModal(submit), self._after_save)

    def action_edit(self) -> None:
        """Open the edit form for the selected device."""
        d = self._selected()
        if d is None:
            return
        is_server = d.device_type is DeviceType.SERVER

        def submit(v: dict[str, Any]) -> DeviceDTO:
            return self.services.devices.update_device(
                UpdateDeviceRequest(
                    d.id,
                    v["hostname"],
                    v["location"],
                    v["description"],
                    v.get("gateway") if is_server else None,
                )
            )

        edit = {
            "hostname": d.hostname,
            "location": d.location,
            "description": d.description,
            "gateway": d.default_gateway or "",
        }
        self.app.push_screen(DeviceFormModal(submit, edit, is_server), self._after_save)

    def _after_save(self, result: object) -> None:
        if isinstance(result, DeviceDTO):
            self.notify(f"Saved {result.hostname}", timeout=4)
            self.action_refresh()

    def action_delete(self) -> None:
        """Confirm, listing links/routes that will be removed."""
        d = self._selected()
        if d is None:
            return
        preview = self.do_command(lambda: self.services.devices.removal_preview(d.id))
        if preview is None:
            return
        lines = [f"Delete {d.hostname}? This cannot be undone."]
        lines += [f"  link: {x}" for x in preview.removed_links]
        lines += [f"  route: {x}" for x in preview.removed_routes]
        lines += [f"  address: {x}" for x in preview.released_addresses]

        def confirmed(ok: bool | None) -> None:
            if ok and self.do_command(
                lambda: self.services.devices.delete_device(d.id),
                f"Deleted {d.hostname}",
            ):
                self.action_refresh()

        self.app.push_screen(
            ConfirmModal("Delete device", lines, confirm_label="Delete"), confirmed
        )

    def action_cycle_status(self) -> None:
        """ONLINE → OFFLINE → MAINTENANCE."""
        d = self._selected()
        if d is None:
            return
        result = self.do_command(lambda: self.services.devices.cycle_status(d.id))
        if isinstance(result, DeviceDTO):
            self.notify(f"{d.hostname} is now {result.status.value.lower()}", timeout=4)
            self.action_refresh()

    def action_clear_arp(self) -> None:
        """Clear the ARP table of the selected router/server."""
        d = self._selected()
        if d is not None and self.do_command(
            lambda: self.services.devices.clear_arp(d.id),
            f"ARP table cleared on {d.hostname}",
        ):
            self.action_refresh()
