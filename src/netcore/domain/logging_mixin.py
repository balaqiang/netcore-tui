"""LoggerMixin (DEC-003): stdlib logger bound to ``netcore.<ClassName>``."""

from __future__ import annotations

import logging


class LoggerMixin:
    """Provide ``self.logger`` for diagnostic (not audit) logging."""

    @property
    def logger(self) -> logging.Logger:
        """Logger named after the concrete class."""
        return logging.getLogger(f"netcore.{type(self).__name__}")
