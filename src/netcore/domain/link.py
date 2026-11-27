"""Link between two interfaces (NETWORK_SPEC §4)."""

from __future__ import annotations

from netcore.domain.errors import InvalidLinkError
from netcore.domain.ids import DeviceId, LinkId
from netcore.domain.interface import InterfaceRef

MIN_CAPACITY_MBPS = 1
MAX_CAPACITY_MBPS = 400_000
DEFAULT_CAPACITY_MBPS = 1000
DEFAULT_LATENCY_MS = 0.1


class Link:
    """A cable joining exactly two interfaces on different devices."""

    def __init__(
        self,
        link_id: LinkId,
        endpoint_a: InterfaceRef,
        endpoint_b: InterfaceRef,
        capacity_mbps: int = DEFAULT_CAPACITY_MBPS,
        latency_ms: float = DEFAULT_LATENCY_MS,
        admin_up: bool = True,
    ) -> None:
        if endpoint_a.device_id == endpoint_b.device_id:
            raise InvalidLinkError("A link must connect two different devices.")
        if not MIN_CAPACITY_MBPS <= capacity_mbps <= MAX_CAPACITY_MBPS:
            raise InvalidLinkError(
                f"Capacity {capacity_mbps} Mbps is outside "
                f"{MIN_CAPACITY_MBPS}-{MAX_CAPACITY_MBPS} Mbps."
            )
        if latency_ms < 0:
            raise InvalidLinkError("Latency must not be negative.")
        self._id = link_id
        self._a = endpoint_a
        self._b = endpoint_b
        self._capacity = capacity_mbps
        self._latency = latency_ms
        self._admin_up = admin_up

    @property
    def id(self) -> LinkId:
        """Link identifier."""
        return self._id

    @property
    def endpoint_a(self) -> InterfaceRef:
        """First endpoint."""
        return self._a

    @property
    def endpoint_b(self) -> InterfaceRef:
        """Second endpoint."""
        return self._b

    @property
    def capacity_mbps(self) -> int:
        """Configured bandwidth capacity (never mutated by traffic)."""
        return self._capacity

    @property
    def latency_ms(self) -> float:
        """Simulated one-way latency."""
        return self._latency

    @property
    def admin_up(self) -> bool:
        """Administrative state."""
        return self._admin_up

    def endpoints(self) -> tuple[InterfaceRef, InterfaceRef]:
        """Both endpoints."""
        return (self._a, self._b)

    def involves(self, device_id: DeviceId) -> bool:
        """True if either endpoint belongs to ``device_id``."""
        return device_id in (self._a.device_id, self._b.device_id)

    def peer_of(self, ref: InterfaceRef) -> InterfaceRef:
        """The opposite endpoint of ``ref``."""
        if ref == self._a:
            return self._b
        if ref == self._b:
            return self._a
        raise InvalidLinkError(f"{ref} is not an endpoint of link {self._id}.")

    def set_admin(self, up: bool) -> None:
        """Set administrative state (failure injection)."""
        self._admin_up = up

    def __repr__(self) -> str:
        return f"Link({self._id}, {self._a} <-> {self._b})"
