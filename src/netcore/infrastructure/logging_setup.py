"""Diagnostic logging to a file (events are the user-visible audit trail)."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_path: str | None, level: int = logging.INFO) -> None:
    """Attach a file handler to the ``netcore`` logger."""
    logger = logging.getLogger("netcore")
    logger.setLevel(level)
    if log_path is None or any(
        isinstance(h, logging.FileHandler) for h in logger.handlers
    ):
        return
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
