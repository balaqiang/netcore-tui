"""StatCard, EventFeed and UtilizationPanel."""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Group
from rich.text import Text
from textual.message import Message
from textual.widgets import Static

from netcore.application.dto import EventDTO, LinkStatsDTO
from netcore.tui.formatting import muted, severity_text, utilization_bar


class StatCard(Static):
    """Title + big value + breakdown lines."""

    def __init__(self, title: str, card_id: str) -> None:
        super().__init__("", id=card_id)
        self.border_title = title

    def show(self, value: str, breakdown: Sequence[Text | str]) -> None:
        """Render the card."""
        lines: list[Text] = [Text(value, style="bold")]
        lines += [b if isinstance(b, Text) else Text(b) for b in breakdown]
        self.update(Group(*lines))


class EventFeed(Static):
    """Compact list of recent events."""

    class EventSelected(Message):
        """An event was chosen."""

        def __init__(self, event_id: int) -> None:
            super().__init__()
            self.event_id = event_id

    def show(self, events: Sequence[EventDTO]) -> None:
        """Render up to 10 events."""
        if not events:
            self.update(muted("No events yet."))
            return
        lines = []
        for ev in events[:10]:
            line = Text(
                ev.timestamp.strftime("%H:%M:%S "), no_wrap=True, overflow="ellipsis"
            )
            line.append_text(severity_text(ev.severity))
            line.append(f" {ev.category.value:<8} ")
            line.append(ev.message)
            lines.append(line)
        self.update(Group(*lines))


class UtilizationPanel(Static):
    """Top link utilization bars (simulated)."""

    def show(self, links: Sequence[LinkStatsDTO]) -> None:
        """Render bars with values (never bars alone)."""
        if not links:
            self.update(muted("No links yet."))
            return
        lines = []
        for link in links:
            line = Text(f"{link.label[:30]:<30} ", no_wrap=True, overflow="ellipsis")
            line.append_text(utilization_bar(link.utilization_pct, 8))
            line.append(f" {link.load_mbps:.0f}/{link.capacity_mbps} Mbps")
            lines.append(line)
        self.update(Group(*lines))
