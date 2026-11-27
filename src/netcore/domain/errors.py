"""Domain exception hierarchy (UML.md §5, NETWORK_SPEC §12).

Every error carries a stable ``code`` and a human-readable ``message``.
Codes NET016+ extend the NETWORK_SPEC §12 catalogue for cases the spec
names but does not number.
"""

from __future__ import annotations


class NetCoreError(Exception):
    """Base class for all NetCore domain errors."""

    code: str = "NET000"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ValidationError(NetCoreError):
    """Input violates a network rule."""


class NotFoundError(NetCoreError):
    """Referenced entity does not exist."""


class ConflictError(NetCoreError):
    """Operation conflicts with existing state."""


class InvalidAddressError(ValidationError):
    """Malformed IPv4/MAC address or interface address."""

    code = "NET001"


class InvalidSubnetError(ValidationError):
    """Malformed subnet or subnet with host bits set."""

    code = "NET002"


class AddressNotInSubnetError(ValidationError):
    """Interface address is not inside a defined subnet."""

    code = "NET003"


class ReservedAddressError(ValidationError):
    """Network/broadcast address used as host address."""

    code = "NET004"


class DuplicateAddressError(ConflictError):
    """IPv4 address already assigned in the lab."""

    code = "NET005"


class DuplicateMacError(ConflictError):
    """MAC address already used in the lab."""

    code = "NET006"


class DuplicateHostnameError(ConflictError):
    """Hostname already exists (case-insensitive)."""

    code = "NET007"


class OverlappingSubnetError(ConflictError):
    """Subnet overlaps an existing one without a parent declaration."""

    code = "NET008"


class InvalidNextHopError(ValidationError):
    """Next hop / gateway not on a connected subnet."""

    code = "NET009"


class DuplicateRouteError(ConflictError):
    """Route with same destination and next hop already exists."""

    code = "NET010"


class InvalidPortError(ValidationError):
    """Switch port number outside the valid range."""

    code = "NET011"


class InterfaceInUseError(ConflictError):
    """Interface already has a link."""

    code = "NET012"


class InvalidLinkError(ValidationError):
    """Link endpoints or attributes are invalid."""

    code = "NET013"


class InvalidSourceError(ValidationError):
    """Simulation source cannot send."""

    code = "NET014"


class DeviceNotFoundError(NotFoundError):
    """Device id/hostname does not exist."""

    code = "NET015"


class InterfaceNotFoundError(NotFoundError):
    """Interface name does not exist on the device."""

    code = "NET016"


class LinkNotFoundError(NotFoundError):
    """Link id does not exist."""

    code = "NET017"


class SubnetNotFoundError(NotFoundError):
    """Subnet id does not exist."""

    code = "NET018"


class RouteNotFoundError(NotFoundError):
    """Route id does not exist or is not removable."""

    code = "NET019"


class SubnetInUseError(ConflictError):
    """Subnet still has assigned addresses."""

    code = "NET020"


class DuplicateInterfaceError(ConflictError):
    """Interface name repeated on one device."""

    code = "NET021"


class InvalidValueError(ValidationError):
    """Generic out-of-range or malformed value (hostname, TTL, counts...)."""

    code = "NET022"
