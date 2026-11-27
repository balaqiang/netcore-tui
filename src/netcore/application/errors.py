"""ApplicationError — user-safe errors carrying the domain code."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from netcore.domain.errors import (
    ConflictError,
    NetCoreError,
    NotFoundError,
    ValidationError,
)

_log = logging.getLogger("netcore.application")


class ApplicationError(Exception):
    """Error the TUI can show verbatim (``message``) with a stable ``code``."""

    def __init__(self, code: str, message: str, kind: str = "validation") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.kind = kind

    @classmethod
    def from_domain(cls, error: NetCoreError) -> ApplicationError:
        """Wrap a domain error keeping its code."""
        if isinstance(error, NotFoundError):
            kind = "not_found"
        elif isinstance(error, ConflictError):
            kind = "conflict"
        elif isinstance(error, ValidationError):
            kind = "validation"
        else:
            kind = "error"
        return cls(error.code, error.message, kind)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


@contextmanager
def translate_errors() -> Generator[None]:
    """Convert domain errors to ``ApplicationError`` (never swallows)."""
    try:
        yield
    except ApplicationError:
        raise
    except NetCoreError as exc:
        raise ApplicationError.from_domain(exc) from exc
    except ValueError as exc:
        _log.debug("value error translated", exc_info=True)
        raise ApplicationError("APP001", str(exc), "validation") from exc
