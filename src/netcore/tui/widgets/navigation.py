"""NavigationSidebar and the global status header."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Click
from textual.message import Message
from textual.widgets import Static

from netcore.tui.bindings import SCREENS


class NavItem(Static):
    """One sidebar entry."""

    def __init__(self, key: str, screen_id: str, title: str) -> None:
        super().__init__(f"{key} {title}", id=f"nav-{screen_id}")
        self.key = key
        self.screen_id = screen_id
        self.title = title

    def set_narrow(self, narrow: bool) -> None:
        """Numbers only below 120 columns."""
        self.update(f"{self.key}" if narrow else f"{self.key} {self.title}")

    def on_click(self, event: Click) -> None:
        """Mouse is optional; keyboard uses number keys."""
        event.stop()
        self.post_message(NavigationSidebar.NavigateRequested(self.screen_id))


class NavigationSidebar(Vertical):
    """Screen list with number keys (UI_SPEC §2)."""

    class NavigateRequested(Message):
        """User clicked a navigation entry."""

        def __init__(self, screen_id: str) -> None:
            super().__init__()
            self.screen_id = screen_id

    def __init__(self, active: str) -> None:
        super().__init__()
        self._active = active
        self.border_title = "Navigation"

    def compose(self) -> ComposeResult:
        for key, screen_id, title in SCREENS:
            item = NavItem(key, screen_id, title)
            if screen_id == self._active:
                item.add_class("-active")
            yield item

    def set_narrow(self, narrow: bool) -> None:
        """Collapse to numbers only."""
        self.set_class(narrow, "-narrow")
        self.border_title = "Nav" if narrow else "Navigation"
        for item in self.query(NavItem):
            item.set_narrow(narrow)


class AppHeader(Static):
    """Top line: app, lab, online/offline counts, UTC clock."""

    def __init__(self) -> None:
        super().__init__("NetCore TUI", id="app-header")
