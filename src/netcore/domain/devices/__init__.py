"""Network device classes (DEC-003)."""

from netcore.domain.devices.base import NetworkDevice
from netcore.domain.devices.router import Router, RoutingEntry, RoutingTable
from netcore.domain.devices.server import Server
from netcore.domain.devices.switch import MacTable, MacTableEntry, Switch, SwitchPort

__all__ = [
    "MacTable",
    "MacTableEntry",
    "NetworkDevice",
    "Router",
    "RoutingEntry",
    "RoutingTable",
    "Server",
    "Switch",
    "SwitchPort",
]
