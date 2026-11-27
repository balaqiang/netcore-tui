"""Use-case services and the container handed to the TUI."""

from __future__ import annotations

from dataclasses import dataclass

from netcore.application.event_bus import EventBus
from netcore.application.services._common import ServiceContext
from netcore.application.services.device_service import DeviceService
from netcore.application.services.event_log_service import EventLogService
from netcore.application.services.ipam_service import IpamService
from netcore.application.services.monitoring_service import MonitoringService
from netcore.application.services.routing_service import RoutingService
from netcore.application.services.settings_service import SettingsService
from netcore.application.services.simulation_service import SimulationService
from netcore.application.services.switch_service import SwitchService
from netcore.application.services.topology_service import TopologyService


@dataclass(frozen=True, slots=True)
class Services:
    """Everything the presentation layer may call."""

    bus: EventBus
    devices: DeviceService
    ipam: IpamService
    routing: RoutingService
    switches: SwitchService
    topology: TopologyService
    simulation: SimulationService
    monitoring: MonitoringService
    events: EventLogService
    settings: SettingsService

    @classmethod
    def build(cls, ctx: ServiceContext) -> Services:
        """Instantiate all services over one context."""
        return cls(
            bus=ctx.bus,
            devices=DeviceService(ctx),
            ipam=IpamService(ctx),
            routing=RoutingService(ctx),
            switches=SwitchService(ctx),
            topology=TopologyService(ctx),
            simulation=SimulationService(ctx),
            monitoring=MonitoringService(ctx),
            events=EventLogService(ctx),
            settings=SettingsService(ctx),
        )


__all__ = [
    "DeviceService",
    "EventLogService",
    "IpamService",
    "MonitoringService",
    "RoutingService",
    "ServiceContext",
    "Services",
    "SettingsService",
    "SimulationService",
    "SwitchService",
    "TopologyService",
]
