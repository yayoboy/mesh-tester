from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog

from src.virtual_node import VirtualNode


class NodeDetailScreen(ModalScreen[None]):
    """Modal popup showing details, history, and controls for one node."""

    DEFAULT_CSS = """
    NodeDetailScreen {
        align: center middle;
    }
    #node-detail-dialog {
        width: 70;
        height: 30;
        border: double $primary;
        background: $surface;
        padding: 1 2;
    }
    #node-detail-title {
        text-style: bold;
        color: $accent;
        height: 1;
        margin-bottom: 1;
    }
    #node-detail-fields {
        height: auto;
        margin-bottom: 1;
    }
    #node-detail-history {
        height: 10;
        border: solid $panel;
        margin-bottom: 1;
    }
    #node-detail-actions {
        height: 3;
    }
    #node-detail-actions Button {
        margin-right: 1;
    }
    """

    class NodePinned(Message):
        """Posted when user pins a node."""
        def __init__(self, node_id: str) -> None:
            super().__init__()
            self.node_id = node_id

    class NodeMuted(Message):
        """Posted when user mutes a node."""
        def __init__(self, node_id: str) -> None:
            super().__init__()
            self.node_id = node_id

    class NodeRogued(Message):
        """Posted when user toggles rogue mode on a node."""
        def __init__(self, node_id: str) -> None:
            super().__init__()
            self.node_id = node_id

    def __init__(self, node: VirtualNode, history: list[str] | None = None) -> None:
        super().__init__()
        self._node = node
        self._history: list[str] = history or []

    def compose(self) -> ComposeResult:
        with Vertical(id="node-detail-dialog"):
            yield Label(
                f"Node: {self._node.longname} ({self._node.id})",
                id="node-detail-title",
            )
            yield Label(
                f"Lat: {self._node.lat:.6f}  Lon: {self._node.lon:.6f}  Alt: {self._node.alt} m\n"
                f"Rogue: {'YES' if self._node.is_rogue else 'no'}",
                id="node-detail-fields",
            )
            yield RichLog(id="node-detail-history", markup=False)
            with Horizontal(id="node-detail-actions"):
                yield Button("Pin",   id="btn-pin",   variant="success")
                yield Button("Mute",  id="btn-mute",  variant="warning")
                yield Button("Rogue", id="btn-rogue",  variant="error")
                yield Button("Close", id="btn-close")

    def on_mount(self) -> None:
        log = self.query_one("#node-detail-history", RichLog)
        for entry in self._history[-20:]:
            log.write(entry)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-pin":
            self.post_message(self.NodePinned(self._node.id))
            self.dismiss()
        elif btn_id == "btn-mute":
            self.post_message(self.NodeMuted(self._node.id))
            self.dismiss()
        elif btn_id == "btn-rogue":
            self.post_message(self.NodeRogued(self._node.id))
            self.dismiss()
        elif btn_id == "btn-close":
            self.dismiss()
