from __future__ import annotations

from textual.widgets import DataTable

from src.virtual_node import VirtualNode

# (label shown in header, key used in get_cell / update_cell)
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("ID", "id"),
    ("Name", "name"),
    ("Lat", "lat"),
    ("Lon", "lon"),
    ("Alt", "alt"),
    ("Sent", "sent"),
)


class NodeTable(DataTable):
    """DataTable pre-configured for virtual node stats."""

    DEFAULT_CSS = """
    NodeTable {
        height: 1fr;
    }
    """

    def on_mount(self) -> None:
        for label, key in _COLUMNS:
            self.add_column(label, key=key)

    def add_node(self, node: VirtualNode) -> None:
        """Add a new row for *node*. Uses node.id as the row key."""
        self.add_row(
            node.id,
            node.longname,
            f"{node.lat:.4f}",
            f"{node.lon:.4f}",
            str(node.alt),
            "0",
            key=node.id,
        )

    def update_sent(self, node_id: str, count: int) -> None:
        """Update the Sent counter for the row identified by *node_id*."""
        self.update_cell(node_id, "sent", str(count))
