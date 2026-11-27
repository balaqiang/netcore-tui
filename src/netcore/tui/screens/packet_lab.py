"""Packet Simulation Lab (7)."""

from __future__ import annotations

from typing import Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Input,
    Label,
    LoadingIndicator,
    Select,
    Static,
)

from netcore.application.dto import (
    DeviceType,
    Protocol,
    SendPacketRequest,
    SimulationResultDTO,
    SimulationSummaryDTO,
    TracerouteDTO,
)
from netcore.tui.formatting import color, result_text
from netcore.tui.screens.base import BaseScreen
from netcore.tui.widgets.form import select_value
from netcore.tui.widgets.tables import HopTraceTable, NetTable


class PacketLabScreen(BaseScreen):
    """Send packets / traceroute and read the hop trace (UI_SPEC §5.7)."""

    SCREEN_ID: ClassVar[str] = "packet-lab"
    TITLE = "Packet Lab"
    REFRESH_CATEGORIES: ClassVar[frozenset[str] | None] = frozenset(
        {"CONFIG", "SYSTEM"}
    )

    BINDINGS: ClassVar[list[BindingType]] = [
        *BaseScreen.BINDINGS,
        Binding("ctrl+enter", "send", "Send", priority=True),
        Binding("ctrl+t", "send", "Send", show=False, priority=True),
        Binding("ctrl+h", "toggle_history", "History", priority=True),
    ]

    def __init__(self, services: Any) -> None:
        super().__init__(services)
        self._sim_busy = False
        self._source_ids: list[int] = []

    def compose_content(self) -> ComposeResult:
        with Horizontal(id="lab-form"):
            with Vertical(classes="lab-field -grow"):
                yield Label("Source")
                yield Select([], prompt="Source", id="src-select")
            with Vertical(classes="lab-field -grow"):
                yield Label("Destination IP")
                yield Input(placeholder="e.g. 10.0.2.10", id="dst-input")
            with Vertical(classes="lab-field"):
                yield Label("Proto")
                yield Select(
                    [(p.value, p) for p in Protocol],
                    value=Protocol.ICMP,
                    allow_blank=False,
                    id="proto-select",
                )
            with Vertical(classes="lab-field"):
                yield Label("TTL")
                yield Input("64", id="ttl-input", restrict=r"\d*", max_length=3)
            with Vertical(classes="lab-field"):
                yield Label("Size (B)")
                yield Input("64", id="size-input", restrict=r"\d*", max_length=4)
            with Vertical(classes="lab-field"):
                yield Label("Mode")
                yield Select(
                    [("Single", "single"), ("Traceroute", "trace")],
                    value="single",
                    allow_blank=False,
                    id="mode-select",
                )
            with Vertical(classes="lab-field", id="send-field"):
                yield Label(" ")
                yield Button("Send ⏎", id="send", variant="primary")
        yield Static(
            Text(
                "Fill the form and press enter (or ctrl+t) to send a simulated packet.",
                style=color("secondary"),
            ),
            id="sim-result",
        )
        loading = LoadingIndicator(id="sim-loading")
        loading.display = False
        yield loading
        yield HopTraceTable()
        yield Static("", id="hop-detail", classes="panel")
        history = NetTable(
            "Run",
            "Time",
            "Source",
            "Destination",
            "Result",
            "Hops",
            table_id="history-table",
        )
        history.display = False
        yield history

    def action_refresh(self) -> None:
        """Reload source list and settings default TTL."""
        self.call_service(self._load_form_data, self._render_form)

    def _load_form_data(self) -> tuple[list[tuple[int, str]], int]:
        devices = self.services.devices.list_devices()
        sources = [
            (d.id, d.hostname)
            for d in devices
            if d.device_type is not DeviceType.SWITCH
        ]
        return sources, self.services.settings.get().default_ttl

    def _render_form(self, data: tuple[list[tuple[int, str]], int]) -> None:
        sources, ttl = data
        select = self.query_one("#src-select", Select)
        ids = [s[0] for s in sources]
        current = select_value(select)
        if ids != self._source_ids:
            self._source_ids = ids
            select.set_options([(name, sid) for sid, name in sources])
            self.query_one("#ttl-input", Input).value = str(ttl)
        if sources and current not in ids:
            select.value = sources[0][0]

    # ------------------------------------------------------------- send
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in any form input sends."""
        event.stop()
        self.action_send()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Send button."""
        if event.button.id == "send":
            self.action_send()

    def _form_error(self, message: str, input_id: str) -> None:
        widget = self.query_one(f"#{input_id}")
        widget.add_class("-invalid")
        self.query_one("#sim-result", Static).update(
            Text(f"✖ {message}", style=color("error"))
        )
        self.notify(message, severity="error", timeout=8)

    def action_send(self) -> None:
        """Validate shape, run the simulation in a worker."""
        if self._sim_busy:
            return
        for widget_id in ("src-select", "dst-input", "ttl-input", "size-input"):
            self.query_one(f"#{widget_id}").remove_class("-invalid")
        src = select_value(self.query_one("#src-select", Select))
        dst = self.query_one("#dst-input", Input).value.strip()
        ttl_text = self.query_one("#ttl-input", Input).value.strip()
        size_text = self.query_one("#size-input", Input).value.strip()
        if src is None:
            self._form_error("Choose a source device.", "src-select")
            return
        if not dst:
            self._form_error("Destination IP is required.", "dst-input")
            return
        if not ttl_text or not 1 <= int(ttl_text) <= 255:
            self._form_error("TTL must be 1-255.", "ttl-input")
            return
        if not size_text or not 64 <= int(size_text) <= 9000:
            self._form_error("Size must be 64-9000 bytes.", "size-input")
            return
        proto = select_value(self.query_one("#proto-select", Select)) or Protocol.ICMP
        req = SendPacketRequest(int(src), dst, proto, int(ttl_text), int(size_text))
        trace = select_value(self.query_one("#mode-select", Select)) == "trace"
        self._set_running(True)
        if trace:
            self.call_service(
                lambda: self.services.simulation.traceroute(req),
                self._show_trace,
                "sim",
                failed=lambda: self._set_running(False),
            )
        else:
            self.call_service(
                lambda: self.services.simulation.send_packet(req),
                self._show_result,
                "sim",
                failed=lambda: self._set_running(False),
            )

    def _set_running(self, running: bool) -> None:
        self._sim_busy = running
        self.query_one("#sim-loading").display = running
        self.query_one(HopTraceTable).display = not running
        for widget_id in (
            "#src-select",
            "#mode-select",
            "#proto-select",
            "#dst-input",
            "#ttl-input",
            "#size-input",
            "#send",
        ):
            self.query_one(widget_id).disabled = running

    def _show_result(self, result: SimulationResultDTO) -> None:
        self._set_running(False)
        label = result_text(result.status)
        label.append("  ")
        summary = (
            result.summary.split("  ", 1)[-1]
            if result.summary.startswith("✔")
            else (result.summary.removeprefix("✖ DROPPED — "))
        )
        label.append(
            summary, style="" if result.drop_reason is None else color("error")
        )
        label.append(
            f"\npath: {' → '.join(result.path_names)}", style=color("secondary")
        )
        self.query_one("#sim-result", Static).update(label)
        self.query_one(HopTraceTable).load(result)

    def _show_trace(self, trace: TracerouteDTO) -> None:
        self._show_result(trace.final)
        lines = Text("traceroute: ", style="bold")
        for hop in trace.hops:
            lines.append(f"\n  {hop.ttl:>2}  {hop.device_name:<14} {hop.status}")
        current = self.query_one("#sim-result", Static)
        current.update(
            Text.assemble(
                result_text(trace.final.status),
                "  ",
                "reached" if trace.reached else "not reached",
                lines,
            )
        )

    def on_hop_trace_table_hop_selected(
        self, message: HopTraceTable.HopSelected
    ) -> None:
        """Full reason in the detail strip."""
        table = self.query_one(HopTraceTable)
        if table.result is None:
            return
        hop = next((h for h in table.result.hops if h.index == message.index), None)
        if hop is not None:
            text = Text(
                f"#{hop.index} {hop.kind.value} at {hop.device_name}: ", style="bold"
            )
            text.append(hop.reason)
            if hop.matched_route:
                text.append(
                    f"\nmatched route: {hop.matched_route}", style=color("accent")
                )
            self.query_one("#hop-detail", Static).update(text)

    # ---------------------------------------------------------- history
    def action_toggle_history(self) -> None:
        """Show/hide last 20 runs."""
        table = self.query_one("#history-table", NetTable)
        table.display = not table.display
        if table.display:
            self.call_service(
                lambda: self.services.simulation.history(20),
                self._render_history,
                "history",
            )
            table.focus()

    def _render_history(self, runs: list[SimulationSummaryDTO]) -> None:
        table = self.query_one("#history-table", NetTable)
        table.clear()
        for r in runs:
            res = result_text(r.status)
            if r.drop_reason:
                res.append(f" {r.drop_reason.value}")
            table.add_row(
                str(r.run_id),
                r.started_at.strftime("%H:%M:%S"),
                r.src_name,
                r.dst_ip,
                res,
                str(r.hop_count),
                key=str(r.run_id),
            )

    def on_data_table_row_selected(self, event: NetTable.RowSelected) -> None:
        """Replay a run from history (US-SIM-5)."""
        if event.data_table.id != "history-table" or event.row_key.value is None:
            return
        run_id = int(event.row_key.value)
        result = self.do_command(lambda: self.services.simulation.replay(run_id))
        if isinstance(result, SimulationResultDTO):
            self._show_result(result)
