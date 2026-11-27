"""Configuration resolution: CLI flag > env var > default (FR-DB-01)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _xdg(var: str, fallback: str) -> Path:
    base = os.environ.get(var)
    return Path(base) if base else Path.home() / fallback


def default_db_path() -> Path:
    """``$XDG_DATA_HOME/netcore/netcore.db`` (fallback ``~/.local/share``)."""
    return _xdg("XDG_DATA_HOME", ".local/share") / "netcore" / "netcore.db"


def default_log_path() -> Path:
    """``$XDG_STATE_HOME/netcore/netcore.log`` (fallback ``~/.local/state``)."""
    return _xdg("XDG_STATE_HOME", ".local/state") / "netcore" / "netcore.log"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Resolved runtime configuration."""

    db_path: str
    log_path: str | None
    seed_lab: str | None = None

    @classmethod
    def resolve(
        cls,
        db_flag: str | None = None,
        seed_lab: str | None = None,
        log_path: str | None = None,
    ) -> AppConfig:
        """Apply precedence rules."""
        db = db_flag or os.environ.get("NETCORE_DB") or str(default_db_path())
        log = log_path if log_path is not None else str(default_log_path())
        return cls(db_path=db, log_path=log, seed_lab=seed_lab)
