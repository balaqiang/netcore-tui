"""DataTable variants: vim keys, hop trace."""

from __future__ import annotations

from rich.text import Text
from textual.message import Message
from textual.widgets import DataTable

from netcore.application.dto import HopKind, SimulationResultDTO
from netcore.tui.bindings import TABLE_BINDINGS
from netcore.tui.formatting import color

_KIND_TOKEN = {
    HopKind.DROP: "error",
    HopKind.DELIVER: "success",
    HopKind.ARP: "secondary",
    HopKind.FLOOD: "warning",
    HopKind.ROUTE: "accent",
}


class NetTable(DataTable):
    """Row-cursor table with j/k/g/G bindings."""

    BINDINGS = TABLE_BINDINGS

    def __init__(self, *columns: str, table_id: str) -> None:
        super().__init__(id=table_id, cursor_type="row", zebra_stripes=True)
        self._columns = columns

    def on_mount(self) -> None:
        """Create columns."""
        self.add_columns(*self._columns)

    def selected_key(self) -> str | None:
        """Key of the row under the cursor."""
        if self.row_count == 0:
            return None
        try:
            row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
        except Exception:
            return None
        return None if row_key.value is None else str(row_key.value)

    def select_key(self, key: str | None) -> None:
        """Move the cursor to the row with ``key`` if present."""
        if key is None:
            return
        try:
            index = self.get_row_index(key)
        except Exception:
            return
        self.move_cursor(row=index)


class HopTraceTable(NetTable):
    """Hop-by-hop trace of a SimulationResultDTO."""

    class HopSelected(Message):
        """A hop row was highlighted."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(self, table_id: str = "hop-table") -> None:
        super().__init__(
            "#", "Kind", "Device", "In→Out", "TTL", "Decision", table_id=table_id
        )
        self.result: SimulationResultDTO | None = None

    def load(self, result: SimulationResultDTO) -> None:
        """Render the trace."""
        self.result = result
        self.clear()
        for hop in result.hops:
            kind = Text(hop.kind.value)
            token = _KIND_TOKEN.get(hop.kind)
            if token:
                kind.stylize(color(token))
            ttl = "-"
            if (
                hop.ttl_in is not None
                and hop.ttl_out is not None
                and hop.ttl_in != hop.ttl_out
            ):
                ttl = f"{hop.ttl_in}→{hop.ttl_out}"
            elif hop.ttl_in is not None:
                ttl = str(hop.ttl_in)
            self.add_row(
                str(hop.index),
                kind,
                hop.device_name,
                f"{hop.ingress or '-'}→{hop.egress or '-'}",
                ttl,
                hop.matched_route or hop.reason,
                key=str(hop.index),
            )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Forward as HopSelected."""
        if event.row_key.value is not None:
            self.post_message(self.HopSelected(int(event.row_key.value)))
