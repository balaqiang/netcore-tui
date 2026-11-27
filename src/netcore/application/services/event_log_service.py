"""EventLogService — US-LOG-1..3."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from netcore.application.dto import EventDTO, EventFilterDTO, ExportResultDTO
from netcore.application.errors import ApplicationError
from netcore.application.event_bus import Unsubscribe
from netcore.application.ports import EventFilter
from netcore.application.services._common import BaseService, event_dto
from netcore.domain.events import NetworkEvent
from netcore.domain.ids import DeviceId

WINDOWS = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "all": None,
}


class EventLogService(BaseService):
    """Query and export the audit trail."""

    def subscribe(self, handler: Callable[[EventDTO], None]) -> Unsubscribe:
        """Receive every published event as a DTO (TUI bridge, DEC-013)."""

        def adapter(event: NetworkEvent) -> None:
            handler(event_dto(None, event))

        return self._bus.subscribe(None, adapter)

    def query(self, flt: EventFilterDTO | None = None) -> list[EventDTO]:
        """Events newest-first."""
        flt = flt or EventFilterDTO()
        if flt.window not in WINDOWS:
            raise ApplicationError("APP006", f"Unknown time window {flt.window!r}.")
        window = WINDOWS[flt.window]
        since = self._now() - window if window is not None else None
        with self._ctx.uow_factory() as uow:
            topo = uow.topology.load()
            events = uow.events.query(
                EventFilter(
                    severities=flt.severities,
                    category=flt.category,
                    device_id=DeviceId(flt.device_id)
                    if flt.device_id is not None
                    else None,
                    text=flt.text.strip(),
                    since=since,
                    limit=flt.limit,
                )
            )
        return [event_dto(topo, e) for e in events]

    def export(
        self, flt: EventFilterDTO, fmt: str, path: str, overwrite: bool = False
    ) -> ExportResultDTO:
        """Export filtered events to CSV/JSON (never overwrites silently)."""
        exporter = self._ctx.exporter
        if exporter is None:
            raise ApplicationError("APP007", "Export is not available.")
        fmt = fmt.lower()
        if fmt not in {"csv", "json"}:
            raise ApplicationError("APP008", "Format must be csv or json.")
        if not path.strip():
            raise ApplicationError("APP009", "Path must not be empty.")
        if exporter.exists(path) and not overwrite:
            raise ApplicationError(
                "APP010", f"{path} already exists; confirm to overwrite.", "conflict"
            )
        rows: list[dict[str, object]] = [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "severity": e.severity.value,
                "category": e.category.value,
                "device": e.device_name or "",
                "message": e.message,
                "payload": dict(e.payload),
            }
            for e in self.query(flt)
        ]
        try:
            exporter.write(path, rows, fmt)
        except (OSError, ValueError) as exc:
            raise ApplicationError("APP011", f"Export failed: {exc}") from exc
        return ExportResultDTO(path, len(rows), fmt)
