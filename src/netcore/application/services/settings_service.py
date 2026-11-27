"""SettingsService — US-SET-1..4."""

from __future__ import annotations

from netcore.application.dto import SettingsDTO, UpdateSettingsRequest
from netcore.application.errors import ApplicationError, translate_errors
from netcore.application.services._common import (
    SETTING_RANGES,
    BaseService,
    seeded_rng,
    validate_setting,
)
from netcore.domain.enums import EventCategory, Severity
from netcore.domain.labs import SAMPLE_LABS


class SettingsService(BaseService):
    """Settings, sample labs and lab reset."""

    def get(self) -> SettingsDTO:
        """Effective settings."""
        with self._ctx.uow_factory() as uow:
            return self._settings(uow)

    def update(self, req: UpdateSettingsRequest) -> SettingsDTO:
        """Validate and save changed settings."""
        values: dict[str, str] = {}
        for key in SETTING_RANGES:
            value = getattr(req, key)
            if value is not None:
                values[key] = str(validate_setting(key, int(value)))
        with self._ctx.uow_factory() as uow:
            if values:
                uow.settings.set_many(values)
                events = self._store(
                    uow,
                    [
                        self._event(
                            Severity.INFO,
                            EventCategory.CONFIG,
                            f"settings updated: {', '.join(sorted(values))}",
                            changes=values,
                        )
                    ],
                )
            else:
                events = []
            dto = self._settings(uow)
        self._publish(events)
        return dto

    def sample_labs(self) -> list[str]:
        """Names of bundled labs."""
        return sorted(SAMPLE_LABS)

    def load_sample_lab(self, name: str) -> None:
        """Replace the lab with a bundled one (US-SET-3)."""
        builder = SAMPLE_LABS.get(name)
        if builder is None:
            raise ApplicationError(
                "APP012", f"Unknown lab {name!r} (available: {', '.join(SAMPLE_LABS)})."
            )
        with translate_errors(), self._ctx.uow_factory() as uow:
            seed = self._settings(uow).seed
            topo = builder(seeded_rng(seed, 7))
            uow.topology.clear()
            uow.simulations.clear()
            uow.topology.save(topo)
            uow.settings.set_many({"lab_name": name})
            events = self._store(
                uow,
                [
                    self._event(
                        Severity.INFO,
                        EventCategory.SYSTEM,
                        f"lab {name} loaded ({len(topo.devices())} devices, "
                        f"{len(topo.links())} links)",
                        lab=name,
                    )
                ],
            )
        self._publish(events)

    def reset_lab(self) -> None:
        """Delete every device, link and subnet (US-SET-4)."""
        with self._ctx.uow_factory() as uow:
            uow.topology.clear()
            uow.simulations.clear()
            uow.settings.set_many({"lab_name": "empty-lab"})
            events = self._store(
                uow, [self._event(Severity.WARNING, EventCategory.SYSTEM, "lab reset")]
            )
        self._publish(events)

    def lab_is_empty(self) -> bool:
        """True if the lab has no devices."""
        with self._ctx.uow_factory() as uow:
            return not uow.topology.load().devices()
