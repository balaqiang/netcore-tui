"""Dashboard (1)."""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal

from netcore.application.dto import DashboardDTO
from netcore.tui.formatting import color, up_text
from netcore.tui.screens.base import BaseScreen
from netcore.tui.widgets.cards import EventFeed, StatCard, UtilizationPanel


class DashboardScreen(BaseScreen):
    """Health overview at a glance (UI_SPEC §5.1)."""

    SCREEN_ID: ClassVar[str] = "dashboard"
    TITLE = "Dashboard"

    def compose_content(self) -> ComposeResult:
        with Horizontal(id="dash-cards", classes="toolbar"):
            yield StatCard("Devices", "card-devices")
            yield StatCard("Links", "card-links")
            yield StatCard("Subnets", "card-subnets")
            yield StatCard("Events (1h)", "card-events")
        with Horizontal(id="dash-bottom"):
            util = UtilizationPanel(id="dash-util", classes="panel")
            util.border_title = "Top link utilization (simulated)"
            yield util
            feed = EventFeed(id="dash-events", classes="panel")
            feed.border_title = "Recent events"
            yield feed

    def action_refresh(self) -> None:
        """Load the summary in a worker."""
        self.call_service(self.services.monitoring.dashboard_summary, self._populate)

    def _populate(self, d: DashboardDTO) -> None:
        self.query_one("#card-devices", StatCard).show(
            f"{d.device_total} total",
            [
                Text(
                    f"● {d.online} online",
                    style=color("success"),
                ),
                Text(f"○ {d.offline} offline", style=color("error")),
                Text(f"◐ {d.maintenance} maint", style=color("warning")),
            ],
        )
        self.query_one("#card-links", StatCard).show(
            f"{d.link_total} total",
            [
                up_text(True, f"{d.links_up} up"),
                up_text(False, down_label=f"{d.links_down} down"),
            ],
        )
        self.query_one("#card-subnets", StatCard).show(
            f"{d.subnet_count} subnets", [f"{d.subnet_util_pct:.0f} % used"]
        )
        self.query_one("#card-events", StatCard).show(
            f"{d.warnings_1h} warnings",
            [
                Text(
                    f"{d.errors_1h} errors", style=color("error") if d.errors_1h else ""
                )
            ],
        )
        self.query_one("#dash-util", UtilizationPanel).show(d.top_links)
        self.query_one("#dash-events", EventFeed).show(d.recent_events)
