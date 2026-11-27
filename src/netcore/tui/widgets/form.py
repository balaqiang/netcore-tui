"""FormField and FilterBar."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, Select, Static


def select_value(widget: Select) -> Any | None:
    """Selected value or None when blank."""
    value = widget.value
    return None if value is Select.NULL or value is Select.BLANK else value


class FormField(Vertical):
    """Label + input widget + inline error text."""

    def __init__(self, label: str, control: Widget, field_id: str) -> None:
        super().__init__(id=f"field-{field_id}")
        self._label = label
        self.control = control

    def compose(self) -> ComposeResult:
        yield Label(self._label)
        yield self.control
        error = Static("", classes="field-error")
        error.display = False
        yield error

    def set_error(self, message: str | None) -> None:
        """Show/clear the inline error."""
        error = self.query_one(".field-error", Static)
        error.update(message or "")
        error.display = bool(message)
        self.control.set_class(bool(message), "-invalid")


class FilterBar(Horizontal):
    """Search text + optional selects; emits FilterChanged."""

    class FilterChanged(Message):
        """Any filter control changed."""

        def __init__(self, values: dict[str, Any]) -> None:
            super().__init__()
            self.values = values

    def __init__(self, *controls: Widget, bar_id: str) -> None:
        super().__init__(id=bar_id, classes="toolbar")
        self._controls = controls

    def compose(self) -> ComposeResult:
        yield from self._controls

    def values(self) -> dict[str, Any]:
        """Current filter values keyed by control id."""
        out: dict[str, Any] = {}
        for control in self._controls:
            if isinstance(control, Input):
                out[control.id or ""] = control.value
            elif isinstance(control, Select):
                out[control.id or ""] = select_value(control)
        return out

    def on_input_changed(self, event: Input.Changed) -> None:
        """Text changed."""
        event.stop()
        self.post_message(self.FilterChanged(self.values()))

    def on_select_changed(self, event: Select.Changed) -> None:
        """Select changed."""
        event.stop()
        self.post_message(self.FilterChanged(self.values()))
