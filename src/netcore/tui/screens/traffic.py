"""Traffic Monitor (8)."""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Static

from netcore.application.dto import (
    DeviceStatsDTO,
    DeviceType,
    FlowDTO,
    LinkStatsDTO,
    StartFlowRequest,
)
from netcore.application.errors import ApplicationError
from netcore.tui.formatting import utilization_bar
from netcore.tui.modals.base import ConfirmModal
from netcore.tui.modals.forms import FlowFormModal
from netcore.tui.screens.base import BaseScreen
from netcore.tui.widgets.tables import NetTable

CAPTION = "All values are simulated by NetCore — not real measurements."


def as_int(text: str, label: str) -> int:
    """Input-shape check."""
    text = text.strip()
    if not text.isdigit():
        raise ApplicationError("NET022", f"{label} must be a whole number.")
    return int(text)


class TrafficScreen(BaseScreen):
    """Link/device counters and flows; 1 s refresh (UI_SPEC §5.8)."""

    SCREEN_ID: ClassVar[str] = "traffic"
    TITLE = "Traffic Monitor (simulated)"
    REFRESH_CATEGORIES: ClassVar[frozenset[str] | None] = frozenset(
        {"TRAFFIC", "SYSTEM"}
    )

    BINDINGS: ClassVar[list[BindingType]] = [
        *BaseScreen.BINDINGS,
        Binding("f", "start_flow", "Start flow"),
        Binding("x", "stop_flow", "Stop flow"),
        Binding("z", "reset", "Reset counters"),
    ]

    def __init__(self, services: Any) -> None:
        super().__init__(services)
        self._flows: list[FlowDTO] = []

    def compose_content(self) -> ComposeResult:
        yield Static(CAPTION, classes="caption", id="traffic-caption")
        yield NetTable(
            "Link",
            "Capacity (Mbps)",
            "Load (Mbps, sim)",
            "Utilization",
            "A→B pkts",
            "B→A pkts",
            "Drops",
            table_id="link-stats",
        )
        yield NetTable(
            "Device",
            "Tx pkts",
            "Rx pkts",
            "Tx bytes",
            "Rx bytes",
            "Drops (top)",
            table_id="device-stats",
        )
        yield NetTable(
            "Flow",
            "Source → Dest",
            "Proto",
            "Rate",
            "Load (Mbps)",
            "Remaining",
            "Congestion drops",
            table_id="flow-table",
        )

    def on_mount(self) -> None:
        """1 s refresh tick while visible."""
        super().on_mount()
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        stack = self.app.screen_stack
        if stack and stack[-1] is self:
            self.action_refresh()

    def action_refresh(self) -> None:
        """Reload all three tables in one worker."""

        def load() -> tuple[list[LinkStatsDTO], list[DeviceStatsDTO], list[FlowDTO]]:
            m = self.services.monitoring
            return m.link_stats(), m.device_stats(), m.flows()

        self.call_service(load, self._populate)

    def _populate(
        self, data: tuple[list[LinkStatsDTO], list[DeviceStatsDTO], list[FlowDTO]]
    ) -> None:
        links, devices, flows = data
        self._flows = flows
        lt = self.query_one("#link-stats", NetTable)
        keep = lt.selected_key()
        lt.clear()
        for s in links:
            lt.add_row(
                s.label,
                str(s.capacity_mbps),
                f"{s.load_mbps:.1f}",
                utilization_bar(s.utilization_pct),
                str(s.tx_packets),
                str(s.rx_packets),
                str(s.dropped),
                key=str(s.link_id),
            )
        lt.select_key(keep)
        dt = self.query_one("#device-stats", NetTable)
        keep = dt.selected_key()
        dt.clear()
        for d in devices:
            drops = f"{d.dropped}" + (
                f" ({d.top_drop_reason})" if d.top_drop_reason else ""
            )
            dt.add_row(
                d.hostname,
                str(d.tx_packets),
                str(d.rx_packets),
                str(d.tx_bytes),
                str(d.rx_bytes),
                drops,
                key=str(d.device_id),
            )
        dt.select_key(keep)
        ft = self.query_one("#flow-table", NetTable)
        keep = ft.selected_key()
        ft.clear()
        for f in flows:
            ft.add_row(
                str(f.flow_id),
                f"{f.src_name} → {f.dst_ip}",
                f.protocol.value,
                f"{f.packets_per_second} pps x {f.packet_size} B",
                f"{f.load_mbps:.2f}",
                f"{f.remaining_s} s",
                str(f.congestion_drops),
                key=str(f.flow_id),
            )
        ft.select_key(keep)

    def action_start_flow(self) -> None:
        """Open flow form."""
        devices = self.do_command(self.services.devices.list_devices) or []
        sources = [
            (d.hostname, d.id)
            for d in devices
            if d.device_type is not DeviceType.SWITCH
        ]
        if not sources:
            self.notify("Add a server or router first.", severity="warning", timeout=4)
            return

        def submit(v: dict[str, Any]) -> FlowDTO:
            return self.services.monitoring.start_flow(
                StartFlowRequest(
                    v["src"],
                    v["dst"],
                    v["proto"],
                    as_int(v["size"], "Size"),
                    as_int(v["pps"], "Packets per second"),
                    as_int(v["duration"], "Duration"),
                )
            )

        self.app.push_screen(FlowFormModal(submit, sources), self._after_flow)

    def _after_flow(self, result: object) -> None:
        if isinstance(result, FlowDTO):
            if result.delivered:
                self.notify(
                    f"Flow {result.flow_id} started ({result.load_mbps:.2f} Mbps sim)",
                    timeout=4,
                )
            else:
                reason = result.drop_reason.value if result.drop_reason else "DROPPED"
                self.notify(
                    f"Flow undeliverable: {reason}", severity="warning", timeout=4
                )
            self.action_refresh()

    def action_stop_flow(self) -> None:
        """Stop selected flow."""
        key = self.query_one("#flow-table", NetTable).selected_key()
        if key is None:
            self.notify(
                "Select a flow in the flow table.", severity="warning", timeout=4
            )
            return
        if self.do_command(
            lambda: self.services.monitoring.stop_flow(int(key)), "Flow stopped"
        ):
            self.action_refresh()

    def action_reset(self) -> None:
        """Reset counters after confirmation."""

        def confirmed(ok: bool | None) -> None:
            if ok and self.do_command(
                self.services.monitoring.reset_counters, "Counters reset"
            ):
                self.action_refresh()

        self.app.push_screen(
            ConfirmModal(
                "Reset counters",
                ["Zero all simulated counters?"],
                confirm_label="Reset",
            ),
            confirmed,
        )
