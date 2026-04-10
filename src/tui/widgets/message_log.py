from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from rich.text import Text
from textual.widgets import RichLog

from src.virtual_node import VirtualNode


class _TextEntry(TypedDict):
    type: str        # "text"
    node_id: str
    shortname: str
    text: str


class _PositionEntry(TypedDict):
    type: str        # "position"
    node_id: str
    shortname: str
    lat: float
    lon: float
    alt: int


class MessageLog(RichLog):
    """Scrollable colorized log of text and position events."""

    DEFAULT_CSS = """
    MessageLog {
        height: 1fr;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.entries: list[_TextEntry | _PositionEntry] = []

    def log_text(self, node: VirtualNode, text: str) -> None:
        """Append a text-message event to the log."""
        ts = datetime.now().strftime("%H:%M:%S")
        line = Text()
        line.append(f"[{ts}] ", style="dim")
        line.append(f"[{node.shortname}] ", style="bold cyan")
        line.append("txt ", style="dim")
        line.append(text, style="white")
        self.write(line)
        self.entries.append(
            {"type": "text", "node_id": node.id, "shortname": node.shortname, "text": text}
        )

    def log_position(self, node: VirtualNode) -> None:
        """Append a position-update event to the log."""
        ts = datetime.now().strftime("%H:%M:%S")
        line = Text()
        line.append(f"[{ts}] ", style="dim")
        line.append(f"[{node.shortname}] ", style="bold green")
        line.append("pos ", style="dim")
        line.append(
            f"{node.lat:.4f}, {node.lon:.4f}  alt={node.alt} m",
            style="yellow",
        )
        self.write(line)
        self.entries.append(
            {
                "type": "position",
                "node_id": node.id,
                "shortname": node.shortname,
                "lat": node.lat,
                "lon": node.lon,
                "alt": node.alt,
            }
        )
