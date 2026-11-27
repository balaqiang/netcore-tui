"""Global key map (UI_SPEC §4)."""

from __future__ import annotations

from textual.binding import Binding, BindingType

SCREENS: tuple[tuple[str, str, str], ...] = (
    ("1", "dashboard", "Dashboard"),
    ("2", "devices", "Devices"),
    ("3", "ipam", "IPAM"),
    ("4", "routing", "Routing"),
    ("5", "switch-ports", "Switch Ports"),
    ("6", "topology", "Topology"),
    ("7", "packet-lab", "Packet Lab"),
    ("8", "traffic", "Traffic"),
    ("9", "events", "Event Logs"),
    ("0", "settings", "Settings"),
)

GLOBAL_BINDINGS: list[BindingType] = [
    *(
        Binding(key, f"go('{screen_id}')", title, show=False)
        for key, screen_id, title in SCREENS
    ),
    Binding("question_mark", "help", "Help"),
    Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=False),
    Binding("q", "quit_app", "Quit"),
    Binding("ctrl+q", "quit_app", "Quit", show=False, priority=True),
]

TABLE_BINDINGS: list[BindingType] = [
    Binding("j", "cursor_down", "Down", show=False),
    Binding("k", "cursor_up", "Up", show=False),
    Binding("g", "scroll_top", "First", show=False),
    Binding("G", "scroll_bottom", "Last", show=False),
]
