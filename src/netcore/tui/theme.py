"""NetCore dark theme registered with Textual (UI_SPEC §3)."""

from __future__ import annotations

from textual.theme import Theme

from netcore.tui.formatting import PALETTE

NETCORE_THEME = Theme(
    name="netcore-dark",
    primary=PALETTE["primary"],
    secondary=PALETTE["secondary"],
    accent=PALETTE["accent"],
    warning=PALETTE["warning"],
    error=PALETTE["error"],
    success=PALETTE["success"],
    foreground=PALETTE["foreground"],
    background=PALETTE["background"],
    surface=PALETTE["surface"],
    panel=PALETTE["panel"],
    dark=True,
)
