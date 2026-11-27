"""BaseScreen: global layout, size guard, service-call helpers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

if TYPE_CHECKING:
    from netcore.tui.app import NetCoreApp

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.geometry import Size
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import DataTable, Footer, Input, Static

from netcore.application.dto import EventDTO
from netcore.application.errors import ApplicationError
from netcore.application.services import Services
from netcore.tui.widgets.navigation import AppHeader, NavigationSidebar

T = TypeVar("T")
MIN_W, MIN_H = 100, 30
WIDE = 120
_log = logging.getLogger("netcore.tui")


class BaseScreen(Screen[None]):
    """Header + sidebar + titled content + footer; too-small guard."""

    SCREEN_ID: ClassVar[str] = ""
    TITLE = ""
    REFRESH_CATEGORIES: ClassVar[frozenset[str] | None] = None  # None = all
    # Focus a table/grid first so number keys navigate instead of typing.
    AUTO_FOCUS = "DataTable, PortGrid, TopologyCanvas, Button"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "leave_input", "Back", show=False),
    ]

    def __init__(self, services: Services) -> None:
        super().__init__(id=self.SCREEN_ID)
        self.services = services
        self._debounce: Timer | None = None

    @property
    def netcore_app(self) -> NetCoreApp:
        """Typed app accessor."""
        from netcore.tui.app import NetCoreApp  # noqa: PLC0415 - avoid import cycle

        app = self.app
        assert isinstance(app, NetCoreApp)
        return app

    # ------------------------------------------------------------- layout
    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Horizontal(id="body"):
            yield NavigationSidebar(self.SCREEN_ID)
            with Vertical(id="content") as content:
                content.border_title = self.TITLE
                yield from self.compose_content()
        yield Static("", id="too-small")
        yield Footer()

    def compose_content(self) -> ComposeResult:
        """Screen-specific widgets."""
        yield from ()

    def on_mount(self) -> None:
        """Apply size rules."""
        self.apply_size(self.app.size)

    def on_screen_resume(self) -> None:
        """Re-query services when shown (UI_SPEC §8)."""
        self.apply_size(self.app.size)
        self.set_header(self.netcore_app.header_text)
        self.action_refresh()

    def on_resize(self, event: Resize) -> None:
        """Breakpoints (UI_SPEC §7)."""
        self.apply_size(event.size)

    def apply_size(self, size: Size) -> None:
        """Toggle too-small / narrow / stacked classes."""
        width, height = size.width, size.height
        small = width < MIN_W or height < MIN_H
        self.set_class(small, "-too-small")
        self.query_one("#too-small", Static).update(
            f"Terminal too small (need {MIN_W}×{MIN_H}, have {width}×{height})"  # noqa: RUF001 - spec text
        )
        self.set_class(width < WIDE, "-stacked")
        sidebar = self.query_one(NavigationSidebar)
        sidebar.set_narrow(width < WIDE)
        sidebar.set_class(self.netcore_app.sidebar_hidden, "-hidden")

    def set_header(self, text: str) -> None:
        """Update the global header line."""
        self.query_one(AppHeader).update(text)

    # ----------------------------------------------------------- actions
    def action_refresh(self) -> None:
        """Reload data from services (override)."""

    def action_leave_input(self) -> None:
        """Escape from an input back to the main table."""
        if isinstance(self.focused, Input):
            tables = list(self.query(DataTable))
            if tables:
                tables[0].focus()
            else:
                self.set_focus(None)

    def on_navigation_sidebar_navigate_requested(
        self, message: NavigationSidebar.NavigateRequested
    ) -> None:
        """Mouse navigation."""
        self.netcore_app.action_go(message.screen_id)

    # ----------------------------------------------------- service calls
    def call_service(
        self,
        fn: Callable[[], T],
        done: Callable[[T], None],
        group: str = "refresh",
        failed: Callable[[], None] | None = None,
    ) -> None:
        """Run ``fn`` in a thread worker; marshal result/error to the UI."""

        def job() -> None:
            try:
                result = fn()
            except ApplicationError as exc:
                self.app.call_from_thread(self.show_error, exc)
                if failed is not None:
                    self.app.call_from_thread(failed)
            except Exception:
                _log.exception("unexpected error in worker")
                self.app.call_from_thread(self.show_unexpected)
                if failed is not None:
                    self.app.call_from_thread(failed)
            else:
                self.app.call_from_thread(done, result)

        self.run_worker(
            job, thread=True, exclusive=True, group=f"{self.SCREEN_ID}-{group}"
        )

    def do_command(
        self, fn: Callable[[], Any], success: str | None = None
    ) -> Any | None:
        """Synchronous fast command with readable error handling."""
        try:
            result = fn()
        except ApplicationError as exc:
            self.show_error(exc)
            return None
        except Exception:
            _log.exception("unexpected error in action")
            self.show_unexpected()
            return None
        if success:
            self.notify(success, timeout=4)
        return result if result is not None else True

    def show_error(self, exc: ApplicationError) -> None:
        """Validation → error toast; not found → warning + refresh."""
        if exc.kind == "not_found":
            self.notify(exc.message, severity="warning", timeout=4)
            self.action_refresh()
        else:
            self.notify(exc.message, severity="error", timeout=8)

    def show_unexpected(self) -> None:
        """Never show a traceback (NFR-05)."""
        self.notify(
            "Unexpected error — details in log file", severity="error", timeout=8
        )

    # ------------------------------------------------------------ events
    def on_domain_event(self, event: EventDTO) -> None:
        """Debounced refresh on relevant bus events (500 ms)."""
        cats = self.REFRESH_CATEGORIES
        if cats is not None and event.category.value not in cats:
            return
        if self._debounce is not None:
            self._debounce.stop()
        self._debounce = self.set_timer(0.5, self.action_refresh)
