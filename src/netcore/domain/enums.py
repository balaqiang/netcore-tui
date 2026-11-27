"""Domain enumerations (UML.md §4)."""

from __future__ import annotations

from enum import StrEnum


class DeviceType(StrEnum):
    """Kind of network device."""

    ROUTER = "ROUTER"
    SWITCH = "SWITCH"
    SERVER = "SERVER"


class DeviceStatus(StrEnum):
    """Administrative/operational status of a device."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"


class Protocol(StrEnum):
    """L4 protocol carried by a simulated packet."""

    ICMP = "ICMP"
    TCP = "TCP"
    UDP = "UDP"


class RouteType(StrEnum):
    """Origin of a routing table entry."""

    CONNECTED = "CONNECTED"
    STATIC = "STATIC"
    DEFAULT = "DEFAULT"


class HopKind(StrEnum):
    """Kind of a hop record in a simulation trace."""

    SEND = "SEND"
    ARP = "ARP"
    SWITCH = "SWITCH"
    ROUTE = "ROUTE"
    DELIVER = "DELIVER"
    DROP = "DROP"
    FLOOD = "FLOOD"


class ForwardAction(StrEnum):
    """Decision a device takes for a received frame."""

    FORWARD = "FORWARD"
    DELIVER = "DELIVER"
    DROP = "DROP"
    FLOOD = "FLOOD"


class SimulationStatus(StrEnum):
    """Final outcome of a simulated packet."""

    DELIVERED = "DELIVERED"
    DROPPED = "DROPPED"


class DropReason(StrEnum):
    """Why a packet was dropped (NETWORK_SPEC §9.3)."""

    NO_ROUTE = "NO_ROUTE"
    TTL_EXPIRED = "TTL_EXPIRED"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    LINK_DOWN = "LINK_DOWN"
    INTERFACE_DOWN = "INTERFACE_DOWN"
    PORT_DOWN = "PORT_DOWN"
    ARP_FAILED = "ARP_FAILED"
    NOT_FOR_ME = "NOT_FOR_ME"
    HOP_LIMIT = "HOP_LIMIT"
    NO_INTERFACE = "NO_INTERFACE"
    FILTERED = "FILTERED"
    CONGESTION = "CONGESTION"


class Severity(StrEnum):
    """Event severity."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventCategory(StrEnum):
    """Event category (NETWORK_SPEC §11)."""

    CONFIG = "CONFIG"
    STATE = "STATE"
    FORWARD = "FORWARD"
    DROP = "DROP"
    DELIVERY = "DELIVERY"
    ARP = "ARP"
    TRAFFIC = "TRAFFIC"
    SYSTEM = "SYSTEM"


class Direction(StrEnum):
    """Direction of traffic on a device (TX/RX) or link (A→B / B→A)."""

    TX = "TX"
    RX = "RX"
    A_TO_B = "A_TO_B"
    B_TO_A = "B_TO_A"


class ArpEntryType(StrEnum):
    """ARP cache entry type."""

    DYNAMIC = "DYNAMIC"
    STATIC = "STATIC"


class ArpOp(StrEnum):
    """ARP message operation."""

    REQUEST = "REQUEST"
    REPLY = "REPLY"
