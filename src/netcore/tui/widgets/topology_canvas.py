"""TopologyCanvas — layered layout with link list (UI_SPEC §5.6)."""

from __future__ import annotations

import itertools

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget

from netcore.application.dto import (
    DeviceStatus,
    DeviceType,
    LinkDTO,
    NodeDTO,
    TopologyDTO,
)
from netcore.tui.formatting import color

LAYERS = (
    (DeviceType.ROUTER, "ROUTERS "),
    (DeviceType.SWITCH, "SWITCHES"),
    (DeviceType.SERVER, "SERVERS "),
)
LIST_THRESHOLD = 40


class TopologyCanvas(Widget, can_focus=True):
    """Routers top, switches middle, servers bottom; links below."""

    BINDINGS = [  # noqa: RUF012 - Textual class attribute
        Binding("left", "move(-1)", "←", show=False),
        Binding("right", "move(1)", "→", show=False),
        Binding("up", "layer(-1)", "↑", show=False),
        Binding("down", "layer(1)", "↓", show=False),
        Binding("enter", "open", "Open device"),
    ]

    class NodeSelected(Message):
        """Selection changed or a node was opened."""

        def __init__(self, node_id: int, opened: bool = False) -> None:
            super().__init__()
            self.node_id = node_id
            self.opened = opened

    def __init__(self, canvas_id: str = "topology-canvas") -> None:
        super().__init__(id=canvas_id)
        self._topo = TopologyDTO((), ())
        self._layer = 0
        self._index = 0
        self.highlight_path = True
        self.list_mode = False

    def load(self, topo: TopologyDTO) -> None:
        """Replace the topology."""
        self._topo = topo
        if len(topo.nodes) > LIST_THRESHOLD:
            self.list_mode = True
        self._clamp()
        self.refresh(layout=True)

    def _layer_nodes(self, layer: int) -> list[NodeDTO]:
        kind = LAYERS[layer][0]
        return [n for n in self._topo.nodes if n.device_type is kind]

    def _clamp(self) -> None:
        for _ in range(3):
            if self._layer_nodes(self._layer):
                break
            self._layer = (self._layer + 1) % 3
        nodes = self._layer_nodes(self._layer)
        self._index = max(0, min(self._index, len(nodes) - 1))

    @property
    def selected(self) -> NodeDTO | None:
        """Selected node."""
        nodes = self._layer_nodes(self._layer)
        return nodes[self._index] if nodes else None

    def get_content_height(
        self, container: object, viewport: object, width: int
    ) -> int:
        """Rows needed."""
        return len(self._lines())

    def _node_cell(self, node: NodeDTO, selected: bool, on_path: bool) -> Text:
        glyph = {"ONLINE": "●", "OFFLINE": "○", "MAINTENANCE": "◐"}[node.status.value]
        token = {
            DeviceStatus.ONLINE: "success",
            DeviceStatus.OFFLINE: "error",
            DeviceStatus.MAINTENANCE: "warning",
        }[node.status]
        style = color("accent") + " bold" if on_path else color(token)
        if selected:
            style += " reverse"
        return Text(f"[{glyph} {node.hostname}]", style=style)

    def _link_on_path(self, link: LinkDTO) -> bool:
        path = self._topo.last_path
        for a, b in itertools.pairwise(path):
            if {a, b} == {link.a_device_id, link.b_device_id}:
                return True
        return False

    def _lines(self) -> list[Text]:
        topo = self._topo
        if not topo.nodes:
            return [
                Text(
                    "No devices yet — add some in Devices (2) or load a sample lab "
                    "in Settings (0).",
                    style=color("secondary"),
                )
            ]
        path = set(topo.last_path) if self.highlight_path else set()
        selected = self.selected
        lines: list[Text] = []
        if self.list_mode:
            lines.append(Text("ADJACENCY LIST (t toggles canvas)", style="bold"))
            for node in topo.nodes:
                line = self._node_cell(node, node == selected, node.id in path)
                peers = [
                    (lk.b_device if lk.a_device_id == node.id else lk.a_device)
                    for lk in topo.links
                    if node.id in (lk.a_device_id, lk.b_device_id)
                ]
                line.append(" → " + (", ".join(peers) or "(no links)"))
                lines.append(line)
            return lines
        for layer, (_kind, label) in enumerate(LAYERS):
            nodes = self._layer_nodes(layer)
            line = Text(f"{label}  ", style=color("secondary"))
            for idx, node in enumerate(nodes):
                is_sel = layer == self._layer and idx == self._index
                line.append_text(self._node_cell(node, is_sel, node.id in path))
                line.append("  ")
            lines.append(line)
            lines.append(Text(""))
        lines.append(Text("LINKS", style="bold"))
        for link in topo.links:
            on_path = self.highlight_path and self._link_on_path(link)
            if link.operational:
                wire, token = "━━━━", "success"
            else:
                wire, token = "┄┄┄┄", "error"
            line = Text(f"  {link.a_device + ':' + link.a_interface:>20} ")
            line.append(wire, style=color("accent") if on_path else color(token))
            line.append(f" {link.b_device + ':' + link.b_interface:<20}")
            state = (
                "up"
                if link.operational
                else ("down" if not link.admin_up else "inactive")
            )
            line.append(
                f"   {link.capacity_mbps} Mbps  {state}", style=color("secondary")
            )
            lines.append(line)
        return lines

    def render(self) -> Text:
        """Render all lines."""
        return Text("\n").join(self._lines())

    def action_move(self, delta: int) -> None:
        """Move within the layer."""
        nodes = self._layer_nodes(self._layer)
        if nodes:
            self._index = (self._index + delta) % len(nodes)
            self._notify()

    def action_layer(self, delta: int) -> None:
        """Move between layers (skipping empty ones)."""
        for _ in range(3):
            self._layer = (self._layer + delta) % 3
            if self._layer_nodes(self._layer):
                break
        self._clamp()
        self._notify()

    def action_open(self) -> None:
        """Open the selected node."""
        if self.selected is not None:
            self.post_message(self.NodeSelected(self.selected.id, opened=True))

    def _notify(self) -> None:
        self.refresh()
        if self.selected is not None:
            self.post_message(self.NodeSelected(self.selected.id))
