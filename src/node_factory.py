from __future__ import annotations

from src.config import NodePoolConfig, ZoneConfig
from src.virtual_node import VirtualNode
from src.zone import scatter_nodes


class NodeFactory:
    """Generates a list of VirtualNodes from a ZoneConfig + NodePoolConfig."""

    def __init__(
        self,
        zone: ZoneConfig,
        pool: NodePoolConfig,
        seed: int = 42,
    ) -> None:
        self._zone = zone
        self._pool = pool
        self._seed = seed

    def generate(self) -> list[VirtualNode]:
        """Return a fresh list of VirtualNode, deterministic for the same seed."""
        return scatter_nodes(self._zone, self._pool, seed=self._seed)
