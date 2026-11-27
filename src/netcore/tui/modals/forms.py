"""Named form modals (UI_SPEC §6). Screens pass options and a submit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from textual.widgets import Input, Select

from netcore.application.dto import DeviceType, Protocol
from netcore.tui.modals.base import FormModal, Submit
from netcore.tui.widgets.form import FormField, select_value

Options = Sequence[tuple[str, object]]


def _input(field_id: str, value: str = "", placeholder: str = "") -> Input:
    return Input(value=value, placeholder=placeholder, id=f"in-{field_id}")


def _select(
    field_id: str, options: Options, value: object = None, blank: bool = False
) -> Select:
    kwargs: dict = {"allow_blank": blank, "id": f"in-{field_id}"}
    if value is not None:
        kwargs["value"] = value
    return Select([(label, v) for label, v in options], **kwargs)


class DeviceFormModal(FormModal):
    """Add/edit device."""

    def __init__(
        self,
        submit: Submit,
        edit: Mapping[str, str] | None = None,
        is_server: bool = False,
    ) -> None:
        fields = [
            FormField(
                "Hostname",
                _input("hostname", (edit or {}).get("hostname", "")),
                "hostname",
            )
        ]
        if edit is None:
            fields.append(
                FormField(
                    "Type",
                    _select(
                        "type",
                        [(t.value.title(), t) for t in DeviceType],
                        DeviceType.SERVER,
                    ),
                    "type",
                )
            )
            fields.append(
                FormField(
                    "Interface count (blank = default: router 4, switch 24, server 2)",
                    _input("count", placeholder="default"),
                    "count",
                )
            )
        fields.append(
            FormField(
                "Location (rack/row)",
                _input("location", (edit or {}).get("location", "")),
                "location",
            )
        )
        fields.append(
            FormField(
                "Description",
                _input("description", (edit or {}).get("description", "")),
                "description",
            )
        )
        if is_server:
            fields.append(
                FormField(
                    "Default gateway (blank = none)",
                    _input("gateway", (edit or {}).get("gateway", "")),
                    "gateway",
                )
            )
        super().__init__(
            "Edit device" if edit else "Add device",
            fields,
            submit,
            "device-form",
            {
                "NET007": "hostname",
                "NET022": "count",
                "NET009": "gateway",
                "NET001": "gateway",
            },
        )


class SubnetFormModal(FormModal):
    """Add subnet."""

    def __init__(self, submit: Submit, parents: Options) -> None:
        super().__init__(
            "Add subnet",
            [
                FormField("CIDR (e.g. 10.0.1.0/24)", _input("cidr"), "cidr"),
                FormField("Name", _input("name"), "name"),
                FormField("Gateway (optional)", _input("gateway"), "gateway"),
                FormField(
                    "Parent subnet (optional)",
                    _select("parent", parents, blank=True),
                    "parent",
                ),
            ],
            submit,
            "subnet-form",
            {
                "NET001": "cidr",
                "NET002": "cidr",
                "NET008": "cidr",
                "NET009": "gateway",
                "NET004": "gateway",
            },
        )


class AssignAddressModal(FormModal):
    """Assign address: device + interface selects, IP pre-filled."""

    def __init__(
        self,
        submit: Submit,
        devices: Options,
        interfaces: Mapping[object, Sequence[str]],
        suggestion: str,
    ) -> None:
        self._interfaces = interfaces
        first = devices[0][1] if devices else None
        iface_opts = (
            [(n, n) for n in interfaces.get(first, [])] if first is not None else []
        )
        super().__init__(
            "Assign address",
            [
                FormField("Device", _select("device", devices, first), "device"),
                FormField(
                    "Interface",
                    _select(
                        "interface",
                        iface_opts,
                        iface_opts[0][1] if iface_opts else None,
                    ),
                    "interface",
                ),
                FormField(
                    "Address (a.b.c.d/nn)", _input("address", suggestion), "address"
                ),
            ],
            submit,
            "assign-form",
            {
                "NET001": "address",
                "NET003": "address",
                "NET004": "address",
                "NET005": "address",
            },
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        """Refresh interface options when the device changes."""
        if event.select.id != "in-device":
            return
        names = self._interfaces.get(select_value(event.select), [])
        iface = self.query_one("#in-interface", Select)
        iface.set_options([(n, n) for n in names])
        if names:
            iface.value = names[0]


class RouteFormModal(FormModal):
    """Add static route."""

    def __init__(self, submit: Submit, interfaces: Sequence[str]) -> None:
        super().__init__(
            "Add static route",
            [
                FormField(
                    "Destination (CIDR, 0.0.0.0/0 = default)",
                    _input("destination"),
                    "destination",
                ),
                FormField("Next hop", _input("next_hop"), "next_hop"),
                FormField(
                    "Egress interface (blank = derive from next hop)",
                    _select("interface", [(n, n) for n in interfaces], blank=True),
                    "interface",
                ),
                FormField("Metric (0-65535)", _input("metric", "0"), "metric"),
            ],
            submit,
            "route-form",
            {
                "NET002": "destination",
                "NET009": "next_hop",
                "NET010": "destination",
                "NET022": "metric",
            },
        )


class LinkFormModal(FormModal):
    """Connect two interfaces."""

    def __init__(
        self,
        submit: Submit,
        devices: Options,
        interfaces: Mapping[object, Sequence[str]],
        default_capacity: int,
    ) -> None:
        self._interfaces = interfaces
        a = devices[0][1] if devices else None
        b = devices[1][1] if len(devices) > 1 else a

        def opts(dev: object) -> list[tuple[str, str]]:
            return [(n, n) for n in interfaces.get(dev, [])]

        a_opts, b_opts = opts(a), opts(b)
        super().__init__(
            "Add link",
            [
                FormField("Device A", _select("device_a", devices, a), "device_a"),
                FormField(
                    "Interface A",
                    _select("interface_a", a_opts, a_opts[0][1] if a_opts else None),
                    "interface_a",
                ),
                FormField("Device B", _select("device_b", devices, b), "device_b"),
                FormField(
                    "Interface B",
                    _select("interface_b", b_opts, b_opts[0][1] if b_opts else None),
                    "interface_b",
                ),
                FormField(
                    "Capacity (Mbps)",
                    _input("capacity", str(default_capacity)),
                    "capacity",
                ),
            ],
            submit,
            "link-form",
            {"NET012": "interface_a", "NET013": "device_b"},
            wide=True,
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        """Keep interface options in sync with the chosen devices."""
        target = {
            "in-device_a": "#in-interface_a",
            "in-device_b": "#in-interface_b",
        }.get(event.select.id or "")
        if target is None:
            return
        names = self._interfaces.get(select_value(event.select), [])
        iface = self.query_one(target, Select)
        iface.set_options([(n, n) for n in names])
        if names:
            iface.value = names[0]


class PortEditModal(FormModal):
    """Edit switch port."""

    def __init__(
        self, submit: Submit, speed: int, description: str, speeds: Sequence[int]
    ) -> None:
        super().__init__(
            "Edit port",
            [
                FormField(
                    "Speed (Mbps)",
                    _select("speed", [(str(s), s) for s in speeds], speed),
                    "speed",
                ),
                FormField(
                    "Description", _input("description", description), "description"
                ),
            ],
            submit,
            "port-edit",
        )


class FlowFormModal(FormModal):
    """Start a simulated flow."""

    def __init__(self, submit: Submit, sources: Options) -> None:
        super().__init__(
            "Start simulated flow",
            [
                FormField(
                    "Source",
                    _select("src", sources, sources[0][1] if sources else None),
                    "src",
                ),
                FormField("Destination IP", _input("dst"), "dst"),
                FormField(
                    "Protocol",
                    _select("proto", [(p.value, p) for p in Protocol], Protocol.UDP),
                    "proto",
                ),
                FormField("Packet size (64-9000 B)", _input("size", "512"), "size"),
                FormField(
                    "Packets per second (1-100000)", _input("pps", "1000"), "pps"
                ),
                FormField("Duration (1-3600 s)", _input("duration", "60"), "duration"),
            ],
            submit,
            "flow-form",
            {"NET001": "dst", "NET014": "src", "NET022": "pps"},
            submit_label="Start",
        )


class ExportModal(FormModal):
    """Export filtered events."""

    def __init__(self, submit: Submit, default_path: str) -> None:
        super().__init__(
            "Export events",
            [
                FormField(
                    "Format",
                    _select("fmt", [("CSV", "csv"), ("JSON", "json")], "csv"),
                    "fmt",
                ),
                FormField("Path", _input("path", default_path), "path"),
                FormField(
                    "Overwrite if the file exists?",
                    _select(
                        "overwrite", [("No", False), ("Yes, overwrite", True)], False
                    ),
                    "overwrite",
                ),
            ],
            submit,
            "export",
            {
                "APP008": "fmt",
                "APP009": "path",
                "APP010": "overwrite",
                "APP011": "path",
            },
            submit_label="Export",
        )
