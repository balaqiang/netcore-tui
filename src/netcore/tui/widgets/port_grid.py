"""PortGrid — 12 ports per row, arrow-key navigation (UI_SPEC §5.5)."""

from __future__ import annotations

from collections.abc import Sequence

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget

from netcore.application.dto import SwitchPortDTO
from netcore.tui.formatting import color

PER_ROW = 12


class PortGrid(Widget, can_focus=True):
    """Grid of ``[ 7 ●]`` cells colored by state."""

    BINDINGS = [  # noqa: RUF012 - Textual class attribute
        Binding("left", "move(-1)", "←", show=False),
        Binding("right", "move(1)", "→", show=False),
        Binding("up", f"move(-{PER_ROW})", "↑", show=False),
        Binding("down", f"move({PER_ROW})", "↓", show=False),
        Binding("space", "toggle_port", "Toggle port"),
    ]

    class PortSelected(Message):
        """Cursor moved to a port."""

        def __init__(self, number: int) -> None:
            super().__init__()
            self.number = number

    class PortToggleRequested(Message):
        """User asked to toggle admin state."""

        def __init__(self, number: int) -> None:
            super().__init__()
            self.number = number

    def __init__(self, grid_id: str = "port-grid") -> None:
        super().__init__(id=grid_id)
        self._ports: list[SwitchPortDTO] = []
        self.cursor = 0

    def load(self, ports: Sequence[SwitchPortDTO]) -> None:
        """Replace ports and keep the cursor in range."""
        self._ports = list(ports)
        self.cursor = min(self.cursor, max(0, len(self._ports) - 1))
        self.refresh(layout=True)
        if self._ports:
            self.post_message(self.PortSelected(self._ports[self.cursor].number))

    @property
    def selected(self) -> SwitchPortDTO | None:
        """Port under the cursor."""
        return self._ports[self.cursor] if self._ports else None

    def get_content_height(
        self, container: object, viewport: object, width: int
    ) -> int:
        """One line per row of ports."""
        return max(1, -(-len(self._ports) // PER_ROW))

    def render(self) -> Text:
        """Render cells; ● up, ○ admin down, ◌ up but no link."""
        if not self._ports:
            return Text("Select a switch.", style=color("secondary"))
        text = Text()
        for idx, port in enumerate(self._ports):
            if idx and idx % PER_ROW == 0:
                text.append("\n")
            if not port.admin_up:
                glyph, token = "○", "error"
            elif port.operational:
                glyph, token = "●", "success"
            else:
                glyph, token = "◌", "secondary"
            cell = f"[{port.number:>2} {glyph}]"
            style = color(token)
            if idx == self.cursor:
                style += " bold reverse"
            text.append(cell, style=style)
            text.append(" ")
        return text

    def action_move(self, delta: int) -> None:
        """Move the cursor."""
        if not self._ports:
            return
        self.cursor = max(0, min(len(self._ports) - 1, self.cursor + delta))
        self.refresh()
        self.post_message(self.PortSelected(self._ports[self.cursor].number))

    def action_toggle_port(self) -> None:
        """Request admin toggle of the selected port."""
        if self.selected is not None:
            self.post_message(self.PortToggleRequested(self.selected.number))
