"""Settings (0)."""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static

from netcore.application.dto import SettingsDTO, UpdateSettingsRequest
from netcore.application.errors import ApplicationError
from netcore.tui.modals.base import ConfirmModal
from netcore.tui.screens.base import BaseScreen
from netcore.tui.widgets.form import FormField, select_value

FIELDS: tuple[tuple[str, str], ...] = (
    ("default_ttl", "Default TTL (1-255)"),
    ("default_capacity_mbps", "Default link capacity Mbps (1-400000)"),
    ("arp_timeout_s", "ARP timeout s (10-3600)"),
    ("mac_timeout_s", "MAC table timeout s (10-3600)"),
    ("max_hops", "Max hops (8-255)"),
    ("event_retention", "Event retention rows (100+)"),
    ("seed", "Simulation seed"),
)


class SettingsScreen(BaseScreen):
    """Simulation settings and lab actions (UI_SPEC §5.10)."""

    SCREEN_ID: ClassVar[str] = "settings"
    TITLE = "Settings"
    REFRESH_CATEGORIES: ClassVar[frozenset[str] | None] = frozenset({"SYSTEM"})

    BINDINGS: ClassVar[list[BindingType]] = [
        *BaseScreen.BINDINGS,
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("ctrl+l", "load_lab", "Load lab", priority=True),
        Binding("ctrl+r", "reset_lab", "Reset lab", priority=True),
    ]

    def __init__(self, services: Any) -> None:
        super().__init__(services)
        self._settings: SettingsDTO | None = None

    def compose_content(self) -> ComposeResult:
        with VerticalScroll(id="settings-scroll"):
            yield from self._compose_body()

    def _compose_body(self) -> ComposeResult:
        with Horizontal(id="settings-form"):
            for column in (FIELDS[0::2], FIELDS[1::2]):
                with Vertical(classes="settings-col"):
                    for key, label in column:
                        yield FormField(
                            label, Input(id=f"set-{key}", restrict=r"\d*"), key
                        )
        yield Static("", id="settings-info")
        with Horizontal(id="settings-actions"):
            with Vertical(classes="lab-field"):
                yield Label(" ")
                yield Button("Save", id="save", variant="primary", tooltip="ctrl+s")
            with Vertical(classes="lab-field"):
                yield Label("Sample lab")
                yield Select(
                    [("spine-leaf", "spine-leaf"), ("two-router", "two-router")],
                    value="spine-leaf",
                    allow_blank=False,
                    id="lab-select",
                )
            with Vertical(classes="lab-field"):
                yield Label(" ")
                yield Button("Load lab", id="load-lab", tooltip="ctrl+l")
            with Vertical(classes="lab-field"):
                yield Label(" ")
                yield Button(
                    "Reset lab", id="reset-lab", variant="error", tooltip="ctrl+r"
                )

    def action_refresh(self) -> None:
        """Load settings."""
        self.call_service(self.services.settings.get, self._populate)

    def _populate(self, s: SettingsDTO) -> None:
        self._settings = s
        for key, _label in FIELDS:
            self.query_one(f"#set-{key}", Input).value = str(getattr(s, key))
            self.query_one(f"#field-{key}", FormField).set_error(None)
        self.query_one("#settings-info", Static).update(
            f"Lab: {s.lab_name}  ·  DB: {s.db_path} (read-only)  ·  Theme: {s.theme}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Buttons map to actions."""
        {
            "save": self.action_save,
            "load-lab": self.action_load_lab,
            "reset-lab": self.action_reset_lab,
        }.get(event.button.id or "", lambda: None)()

    def action_save(self) -> None:
        """Validate and save; invalid values highlighted inline."""
        values: dict[str, int] = {}
        for key, _label in FIELDS:
            field = self.query_one(f"#field-{key}", FormField)
            field.set_error(None)
            text = self.query_one(f"#set-{key}", Input).value.strip()
            if not text.isdigit():
                field.set_error("Enter a whole number.")
                self.notify("Some settings are invalid.", severity="error", timeout=8)
                return
            values[key] = int(text)
        try:
            saved = self.services.settings.update(UpdateSettingsRequest(**values))
        except ApplicationError as exc:
            for key, label in FIELDS:
                if label.split(" (")[0].split()[0].lower() in exc.message.lower():
                    self.query_one(f"#field-{key}", FormField).set_error(exc.message)
            self.show_error(exc)
            return
        self._populate(saved)
        self.notify("Settings saved", timeout=4)

    def action_load_lab(self) -> None:
        """Load a sample lab in a worker (after confirmation)."""
        name = select_value(self.query_one("#lab-select", Select)) or "spine-leaf"

        def confirmed(ok: bool | None) -> None:
            if not ok:
                return
            self.notify(f"Loading {name}…", timeout=4)
            self.call_service(
                lambda: self.services.settings.load_sample_lab(name),
                lambda _r: self._loaded(name),
                "lab",
            )

        self.app.push_screen(
            ConfirmModal(
                "Load sample lab",
                [
                    f"Replace the current lab with '{name}'?",
                    "Devices, links, subnets and history will be replaced.",
                ],
            ),
            confirmed,
        )

    def _loaded(self, name: str) -> None:
        self.notify(f"Lab {name} loaded", timeout=4)
        self.netcore_app.refresh_header()
        self.action_refresh()

    def action_reset_lab(self) -> None:
        """Double confirmation: type the lab name."""
        lab = self._settings.lab_name if self._settings else "empty-lab"

        def confirmed(ok: bool | None) -> None:
            if ok and self.do_command(self.services.settings.reset_lab, "Lab reset"):
                self.netcore_app.refresh_header()
                self.action_refresh()

        self.app.push_screen(
            ConfirmModal(
                "Reset lab",
                ["Delete every device, link and subnet?", "This cannot be undone."],
                require_text=lab,
                confirm_label="Reset",
            ),
            confirmed,
        )
