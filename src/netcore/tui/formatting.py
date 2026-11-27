"""Glyphs, colors and small renderers shared by widgets (UI_SPEC §3)."""

from __future__ import annotations

from rich.text import Text

from netcore.application.dto import (
    DeviceStatus,
    DeviceType,
    Severity,
    SimulationStatus,
)

# Mirrors theme.tcss tokens for Rich renderables (DataTable cells, Statics).
PALETTE: dict[str, str] = {
    "background": "#0d1117",
    "surface": "#161b22",
    "panel": "#1f2630",
    "primary": "#2f81f7",
    "secondary": "#8b949e",
    "success": "#3fb950",
    "warning": "#d29922",
    "error": "#f85149",
    "accent": "#a371f7",
    "foreground": "#e6edf3",
}

_STATUS = {
    DeviceStatus.ONLINE: ("●", "online", "success"),
    DeviceStatus.OFFLINE: ("○", "offline", "error"),
    DeviceStatus.MAINTENANCE: ("◐", "maint", "warning"),
}

_SEVERITY = {
    Severity.DEBUG: ("·", "DEBUG", "secondary"),
    Severity.INFO: ("●", "INFO", "primary"),
    Severity.WARNING: ("▲", "WARN", "warning"),
    Severity.ERROR: ("✖", "ERROR", "error"),
    Severity.CRITICAL: ("✖", "CRIT", "error"),
}

TYPE_ICON = {DeviceType.ROUTER: "R", DeviceType.SWITCH: "S", DeviceType.SERVER: "H"}


def color(token: str) -> str:
    """Hex color for a theme token."""
    return PALETTE[token]


def status_text(status: DeviceStatus) -> Text:
    """``● online`` etc. — glyph + text + color (never color alone)."""
    glyph, label, token = _STATUS[status]
    return Text(f"{glyph} {label}", style=color(token))


def up_text(up: bool, up_label: str = "up", down_label: str = "down") -> Text:
    """``● up`` / ``○ down``."""
    if up:
        return Text(f"● {up_label}", style=color("success"))
    return Text(f"○ {down_label}", style=color("error"))


def severity_text(severity: Severity) -> Text:
    """Severity glyph + short label."""
    glyph, label, token = _SEVERITY[severity]
    return Text(f"{glyph} {label:<5}", style=color(token))


def result_text(status: SimulationStatus) -> Text:
    """``✔ delivered`` / ``✖ dropped``."""
    if status is SimulationStatus.DELIVERED:
        return Text("✔ DELIVERED", style=f"bold {color('success')}")
    return Text("✖ DROPPED", style=f"bold {color('error')}")


def utilization_bar(pct: float, width: int = 10) -> Text:
    """``███████░░░ 72.0 %`` colored by threshold (70/90)."""
    filled = round(max(0.0, min(100.0, pct)) / 100 * width)
    token = "success" if pct < 70 else "warning" if pct <= 90 else "error"
    text = Text("█" * filled, style=color(token))
    text.append("░" * (width - filled), style=color("secondary"))
    text.append(f" {pct:5.1f} %")
    return text


def muted(value: str) -> Text:
    """Secondary-colored text."""
    return Text(value, style=color("secondary"))
