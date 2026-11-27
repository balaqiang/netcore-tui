"""NetCoreApp — Textual application shell (UI_SPEC §2, §4, §8)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.screen import ModalScreen

from netcore.application.dto import DeviceStatus, EventDTO
from netcore.application.services import Services
from netcore.tui.bindings import GLOBAL_BINDINGS, SCREENS
from netcore.tui.modals.base import ConfirmModal, HelpModal
from netcore.tui.screens.base import BaseScreen
from netcore.tui.screens.dashboard import DashboardScreen
from netcore.tui.screens.devices import DevicesScreen
from netcore.tui.screens.events import EventsScreen
from netcore.tui.screens.ipam import IpamScreen
from netcore.tui.screens.packet_lab import PacketLabScreen
from netcore.tui.screens.routing import RoutingScreen
from netcore.tui.screens.settings import SettingsScreen
from netcore.tui.screens.switch_ports import SwitchPortsScreen
from netcore.tui.screens.topology import TopologyScreen
from netcore.tui.screens.traffic import TrafficScreen
from netcore.tui.theme import NETCORE_THEME

_log = logging.getLogger("netcore.tui")

SCREEN_CLASSES: tuple[type[BaseScreen], ...] = (
    DashboardScreen,
    DevicesScreen,
    IpamScreen,
    RoutingScreen,
    SwitchPortsScreen,
    TopologyScreen,
    PacketLabScreen,
    TrafficScreen,
    EventsScreen,
    SettingsScreen,
)


class DomainEventReceived(Message):
    """An application event arrived via the EventBus bridge."""

    def __init__(self, event: EventDTO) -> None:
        super().__init__()
        self.event = event


class TuiEventBridge:
    """Subscribes to the bus and posts messages to the app (thread-safe)."""

    def __init__(self, app: NetCoreApp, services: Services) -> None:
        self._app = app
        self._unsubscribe = services.events.subscribe(self._on_event)

    def _on_event(self, event: EventDTO) -> None:
        self._app.post_message(DomainEventReceived(event))

    def close(self) -> None:
        """Stop receiving events."""
        self._unsubscribe()


class NetCoreApp(App[None]):
    """Ten screens, global bindings, header and event bridge."""

    CSS_PATH = "theme.tcss"
    TITLE = "NetCore TUI"
    BINDINGS: ClassVar[list[BindingType]] = GLOBAL_BINDINGS

    def __init__(self, services: Services) -> None:
        super().__init__()
        self.services = services
        self.header_text = "NetCore TUI"
        self.sidebar_hidden = False
        self._bridge: TuiEventBridge | None = None
        self._header_counts = ""

    def on_mount(self) -> None:
        """Theme, screens, bridge, header clock."""
        self.register_theme(NETCORE_THEME)
        self.theme = NETCORE_THEME.name
        for cls in SCREEN_CLASSES:
            self.install_screen(cls(self.services), cls.SCREEN_ID)
        self.push_screen(DashboardScreen.SCREEN_ID)
        self._bridge = TuiEventBridge(self, self.services)
        self.refresh_header()
        self.set_interval(1.0, self._render_header)

    def on_unmount(self) -> None:
        """Detach the bridge."""
        if self._bridge is not None:
            self._bridge.close()

    def active_screen(self) -> BaseScreen | None:
        """Current main screen, or None during startup/shutdown/modals."""
        if not self.screen_stack:
            return None
        screen = self.screen_stack[-1]
        return screen if isinstance(screen, BaseScreen) else None

    # ------------------------------------------------------------ header
    def refresh_header(self) -> None:
        """Fetch counts in a worker."""

        def job() -> None:
            try:
                devices = self.services.devices.list_devices()
                lab = self.services.settings.get().lab_name
            except Exception:
                _log.exception("header refresh failed")
                return
            online = sum(d.status is DeviceStatus.ONLINE for d in devices)
            offline = len(devices) - online
            counts = f"lab: {lab}  ·  ● {online} online  ○ {offline} offline/maint"
            self.call_from_thread(self._set_counts, counts)

        self.run_worker(job, thread=True, exclusive=True, group="header")

    def _set_counts(self, counts: str) -> None:
        self._header_counts = counts
        self._render_header()

    def _render_header(self) -> None:
        clock = datetime.now(UTC).strftime("%H:%M:%S UTC")
        self.header_text = f"NetCore TUI  ─  {self._header_counts}  ─  {clock}"
        screen = self.active_screen()
        if screen is not None:
            screen.set_header(self.header_text)

    def on_domain_event_received(self, message: DomainEventReceived) -> None:
        """Bridge → header + current screen (debounced there)."""
        if message.event.category.value in {"CONFIG", "STATE", "SYSTEM"}:
            self.refresh_header()
        screen = self.active_screen()
        if screen is not None:
            screen.on_domain_event(message.event)

    # ----------------------------------------------------------- actions
    def action_go(self, screen_id: str) -> None:
        """Switch to a screen (ignored while a modal is open)."""
        if isinstance(self.screen, ModalScreen):
            return
        if isinstance(self.screen, BaseScreen) and self.screen.id == screen_id:
            return
        self.switch_screen(screen_id)

    def action_toggle_sidebar(self) -> None:
        """ctrl+b."""
        self.sidebar_hidden = not self.sidebar_hidden
        screen = self.active_screen()
        if screen is not None:
            screen.apply_size(self.size)

    def action_help(self) -> None:
        """Help overlay listing current screen + global keys."""
        if isinstance(self.screen, ModalScreen):
            return
        rows: list[tuple[str, str]] = []
        screen = self.screen
        for binding in getattr(screen, "BINDINGS", []):
            if isinstance(binding, Binding) and binding.description:
                rows.append((binding.key, binding.description))
        rows.append(
            ("1-9, 0", "Switch screen (" + ", ".join(t for _k, _i, t in SCREENS) + ")")
        )
        rows += [
            ("tab/shift+tab", "Move focus"),
            ("ctrl+p", "Command palette"),
            ("ctrl+b", "Toggle sidebar"),
            ("j/k g/G", "Table down/up, first/last"),
            ("escape", "Close modal / leave input"),
            ("q / ctrl+q", "Quit"),
        ]
        title = (
            (screen.TITLE or "NetCore") if isinstance(screen, BaseScreen) else "NetCore"
        )
        self.push_screen(HelpModal(title, rows))

    def action_quit_app(self) -> None:
        """Quit, confirming if a worker is running."""
        busy = [w for w in self.workers if w.is_running and w.group != "header"]
        if not busy:
            self.exit()
            return

        def confirmed(ok: bool | None) -> None:
            if ok:
                self.exit()

        self.push_screen(
            ConfirmModal(
                "Quit",
                ["A background task is still running. Quit anyway?"],
                confirm_label="Quit",
            ),
            confirmed,
        )
