"""IP Address Management (3)."""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.widgets import DataTable, Static

from netcore.application.dto import (
    AddressDTO,
    AssignAddressRequest,
    CreateSubnetRequest,
    DeviceType,
    SubnetDTO,
)
from netcore.tui.formatting import utilization_bar
from netcore.tui.modals.base import ConfirmModal
from netcore.tui.modals.forms import AssignAddressModal, SubnetFormModal
from netcore.tui.screens.base import BaseScreen
from netcore.tui.widgets.tables import NetTable


class IpamScreen(BaseScreen):
    """Subnets and addresses (UI_SPEC §5.3)."""

    SCREEN_ID: ClassVar[str] = "ipam"
    TITLE = "IP Address Management"
    REFRESH_CATEGORIES: ClassVar[frozenset[str] | None] = frozenset(
        {"CONFIG", "SYSTEM"}
    )

    BINDINGS: ClassVar[list[BindingType]] = [
        *BaseScreen.BINDINGS,
        Binding("n", "add_subnet", "New subnet"),
        Binding("a", "assign", "Assign"),
        Binding("x", "release", "Release"),
        Binding("d", "delete_subnet", "Delete subnet"),
        Binding("delete", "delete_subnet", "Delete", show=False),
    ]

    def __init__(self, services: Any) -> None:
        super().__init__(services)
        self._subnets: list[SubnetDTO] = []
        self._addresses: list[AddressDTO] = []

    def compose_content(self) -> ComposeResult:
        yield Static(
            "No subnets yet — press n to define one (e.g. 10.0.1.0/24).",
            id="ipam-empty",
            classes="hint",
        )
        with Horizontal(classes="split"):
            yield NetTable(
                "CIDR",
                "Name",
                "Gateway",
                "Total",
                "Used",
                "Free",
                "Util %",
                table_id="subnet-table",
            )
            yield NetTable("IP", "Device", "Interface", "MAC", table_id="address-table")

    def on_mount(self) -> None:
        """Focus subnets."""
        super().on_mount()
        self.query_one("#subnet-table", DataTable).focus()

    def action_refresh(self) -> None:
        """Reload subnets (and addresses of the selection)."""
        self.call_service(self.services.ipam.list_subnets, self._render_subnets)

    def _render_subnets(self, subnets: list[SubnetDTO]) -> None:
        self._subnets = subnets
        table = self.query_one("#subnet-table", NetTable)
        keep = table.selected_key()
        table.clear()
        for s in subnets:
            table.add_row(
                s.cidr,
                s.name,
                s.gateway or "-",
                str(s.total),
                str(s.used),
                str(s.free),
                utilization_bar(s.utilization_pct, 8),
                key=str(s.id),
            )
        table.select_key(keep)
        self.query_one("#ipam-empty").display = not subnets
        self._load_addresses()

    def _selected_subnet(self) -> SubnetDTO | None:
        key = self.query_one("#subnet-table", NetTable).selected_key()
        return next((s for s in self._subnets if str(s.id) == key), None)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Selecting a subnet loads its addresses."""
        if event.data_table.id == "subnet-table":
            self._load_addresses()

    def _load_addresses(self) -> None:
        subnet = self._selected_subnet()
        if subnet is None:
            self._render_addresses([])
            return
        self.call_service(
            lambda: self.services.ipam.addresses(subnet.id),
            self._render_addresses,
            group="addr",
        )

    def _render_addresses(self, addresses: list[AddressDTO]) -> None:
        self._addresses = addresses
        table = self.query_one("#address-table", NetTable)
        table.clear()
        for a in addresses:
            table.add_row(
                f"{a.ip}/{a.prefix}",
                a.device_name,
                a.interface,
                a.mac,
                key=f"{a.device_id}:{a.interface}",
            )

    def action_add_subnet(self) -> None:
        """Open subnet form."""

        def submit(v: dict[str, Any]) -> SubnetDTO:
            return self.services.ipam.create_subnet(
                CreateSubnetRequest(
                    v["cidr"], v["name"], v["gateway"] or None, v["parent"]
                )
            )

        parents = [(f"{s.cidr} {s.name}", s.id) for s in self._subnets]
        self.app.push_screen(SubnetFormModal(submit, parents), self._after)

    def action_assign(self) -> None:
        """Open assign form pre-filled with the next free address."""
        devices = [
            d
            for d in self.do_command(self.services.devices.list_devices) or []
            if d.device_type is not DeviceType.SWITCH
        ]
        if not devices:
            self.notify("Add a router or server first.", severity="warning", timeout=4)
            return
        subnet = self._selected_subnet()
        suggestion = ""
        if subnet is not None:
            suggestion = (
                self.do_command(lambda: self.services.ipam.next_free_address(subnet.id))
                or ""
            )
            if suggestion is True:
                suggestion = ""
        options = [(d.hostname, d.id) for d in devices]
        interfaces = {d.id: [i.name for i in d.interfaces] for d in devices}

        def submit(v: dict[str, Any]) -> object:
            return self.services.ipam.assign_address(
                AssignAddressRequest(v["device"], v["interface"] or "", v["address"])
            )

        self.app.push_screen(
            AssignAddressModal(submit, options, interfaces, str(suggestion)),
            self._after,
        )

    def action_release(self) -> None:
        """Release the selected address."""
        key = self.query_one("#address-table", NetTable).selected_key()
        if key is None:
            self.notify(
                "Select an address in the right table.", severity="warning", timeout=4
            )
            return
        device_id, iface = key.split(":", 1)
        if self.do_command(
            lambda: self.services.ipam.release_address(int(device_id), iface),
            "Address released",
        ):
            self.action_refresh()

    def action_delete_subnet(self) -> None:
        """Delete the selected subnet (blocked if in use)."""
        subnet = self._selected_subnet()
        if subnet is None:
            return

        def confirmed(ok: bool | None) -> None:
            if ok and self.do_command(
                lambda: self.services.ipam.delete_subnet(subnet.id),
                f"Deleted {subnet.cidr}",
            ):
                self.action_refresh()

        self.app.push_screen(
            ConfirmModal(
                "Delete subnet", [f"Delete {subnet.cidr}?"], confirm_label="Delete"
            ),
            confirmed,
        )

    def _after(self, result: object) -> None:
        if result:
            self.notify("Saved", timeout=4)
            self.action_refresh()
