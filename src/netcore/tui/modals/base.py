"""FormModal, ConfirmModal, info modals."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from netcore.application.errors import ApplicationError
from netcore.tui.widgets.form import FormField, select_value

Submit = Callable[[dict[str, Any]], Any]


class FormModal(ModalScreen[Any]):
    """Form with inline errors; ``submit`` may raise ApplicationError."""

    BINDINGS = [  # noqa: RUF012 - Textual class attribute
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Save"),
    ]

    def __init__(
        self,
        title: str,
        fields: Sequence[FormField],
        submit: Submit,
        modal_id: str,
        error_fields: Mapping[str, str] | None = None,
        wide: bool = False,
        submit_label: str = "Save",
    ) -> None:
        super().__init__(id=modal_id)
        self._title = title
        self._fields = list(fields)
        self._submit = submit
        self._error_fields = dict(error_fields or {})
        self._wide = wide
        self._submit_label = submit_label

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal -wide" if self._wide else "modal") as box:
            box.border_title = self._title
            yield from self._fields
            yield Static("", id="form-error", classes="error-text")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel (esc)", id="cancel")
                yield Button(
                    f"{self._submit_label} (ctrl+s)", id="submit", variant="primary"
                )

    def on_mount(self) -> None:
        """First field focused on open."""
        if self._fields:
            self._fields[0].control.focus()

    def field(self, key: str) -> FormField:
        """Field by key."""
        return self.query_one(f"#field-{key}", FormField)

    def values(self) -> dict[str, Any]:
        """Collected control values keyed by field key."""
        out: dict[str, Any] = {}
        for f in self._fields:
            key = (f.id or "").removeprefix("field-")
            control = f.control
            if isinstance(control, Input):
                out[key] = control.value
            elif isinstance(control, Select):
                out[key] = select_value(control)
        return out

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter on the last field submits; otherwise moves on."""
        event.stop()
        controls = [f.control for f in self._fields]
        if event.input is controls[-1] or event.input not in controls:
            self.action_submit()
        else:
            self.focus_next()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Buttons."""
        event.stop()
        if event.button.id == "submit":
            self.action_submit()
        else:
            self.action_cancel()

    def action_cancel(self) -> None:
        """Close without result."""
        self.dismiss(None)

    def _clear_errors(self) -> None:
        for f in self._fields:
            f.set_error(None)
        self.query_one("#form-error", Static).update("")

    def show_error(self, message: str, field_key: str | None = None) -> None:
        """Inline error under a field (or the form) + error toast."""
        target = None
        if field_key is not None:
            try:
                target = self.field(field_key)
            except Exception:
                target = None
        if target is not None:
            target.set_error(message)
            target.control.focus()
        else:
            self.query_one("#form-error", Static).update(message)
        self.app.notify(message, severity="error", timeout=8)

    def action_submit(self) -> None:
        """Validate shape, call the service, show errors inline."""
        self._clear_errors()
        try:
            result = self._submit(self.values())
        except ApplicationError as exc:
            self.show_error(exc.message, self._error_fields.get(exc.code))
            return
        self.dismiss(result if result is not None else True)


class ConfirmModal(ModalScreen[bool]):
    """Yes/no confirmation; optional typed confirmation text."""

    BINDINGS = [  # noqa: RUF012 - Textual class attribute
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Yes", show=False),
        Binding("n", "cancel", "No", show=False),
    ]

    def __init__(
        self,
        title: str,
        lines: Sequence[str],
        require_text: str | None = None,
        confirm_label: str = "Confirm",
    ) -> None:
        super().__init__(id="confirm")
        self._title = title
        self._lines = list(lines)
        self._require = require_text
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal") as box:
            box.border_title = self._title
            for line in self._lines:
                yield Label(line)
            if self._require is not None:
                yield Label(f'Type "{self._require}" to confirm:')
                yield Input(id="confirm-input")
                yield Static("", id="confirm-error", classes="error-text")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel (esc)", id="cancel")
                yield Button(self._confirm_label, id="ok", variant="error")

    def on_mount(self) -> None:
        """Focus the input or the cancel button (safe default)."""
        if self._require is not None:
            self.query_one("#confirm-input", Input).focus()
        else:
            self.query_one("#cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Buttons."""
        event.stop()
        if event.button.id == "ok":
            self.action_confirm()
        else:
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter confirms."""
        event.stop()
        self.action_confirm()

    def action_confirm(self) -> None:
        """Confirm (checks typed text when required)."""
        if self._require is not None:
            typed = self.query_one("#confirm-input", Input).value.strip()
            if typed != self._require:
                self.query_one("#confirm-error", Static).update(
                    f'Text does not match "{self._require}".'
                )
                return
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel."""
        self.dismiss(False)


class InfoModal(ModalScreen[None]):
    """Read-only text (help, event detail)."""

    BINDINGS = [  # noqa: RUF012 - Textual class attribute
        Binding("escape", "close", "Close"),
        Binding("enter", "close", "Close", show=False),
        Binding("question_mark", "close", "Close", show=False),
    ]

    def __init__(self, title: str, body: Text | str, modal_id: str) -> None:
        super().__init__(id=modal_id)
        self._title = title
        self._body = body

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal -wide") as box:
            box.border_title = self._title
            yield Static(self._body)
            with Horizontal(classes="modal-buttons"):
                yield Button("Close (esc)", id="close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close."""
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        """Close."""
        self.dismiss(None)


class HelpModal(InfoModal):
    """Key bindings of the current screen + global keys."""

    def __init__(self, screen_title: str, rows: Sequence[tuple[str, str]]) -> None:
        text = Text()
        text.append(f"{screen_title}\n\n", style="bold")
        for key, desc in rows:
            text.append(f"  {key:<14}", style="bold")
            text.append(f"{desc}\n")
        super().__init__("Help", text, "help")


class EventDetailModal(InfoModal):
    """Event with its JSON payload."""

    def __init__(self, header: str, payload: Mapping[str, object]) -> None:
        body = Text(header + "\n\n", style="bold")
        body.append(json.dumps(dict(payload), indent=2, default=str, sort_keys=True))
        super().__init__("Event detail", body, "event-detail")
