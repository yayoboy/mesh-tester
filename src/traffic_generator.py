from __future__ import annotations
import random
from typing import Callable, Optional
from src.virtual_node import VirtualNode
from src.mqtt_injector import MqttInjector


class TrafficGenerator:
    def __init__(self, injector: MqttInjector, nodes: list[VirtualNode],
                 on_send: Optional[Callable] = None):
        self._injector = injector
        self._nodes: list[VirtualNode] = list(nodes)
        self._on_send = on_send
        self._total_sent = 0
        self._running = False

    @property
    def total_sent(self) -> int:
        return self._total_sent

    @property
    def running(self) -> bool:
        return self._running

    @property
    def nodes(self) -> list[VirtualNode]:
        return list(self._nodes)

    def add_node(self, node: VirtualNode) -> None:
        self._nodes.append(node)

    def remove_node(self, node_id: str) -> None:
        self._nodes = [n for n in self._nodes if n.id != node_id]

    def _publish(self, node: VirtualNode, payload: dict) -> None:
        self._injector.publish(node, payload)
        self._total_sent += 1
        if self._on_send is not None:
            self._on_send(node, payload, self._injector.topic)

    def announce_nodes(self) -> None:
        for node in self._nodes:
            self._publish(node, node.position_payload())

    def send_text_round(self, msg_prefix: str = "test", delay_jitter_ms: int = 0) -> None:
        for node in self._nodes:
            text = f"{msg_prefix} #{self._total_sent + 1}"
            self._publish(node, node.text_payload(text))

    def send_position_round(self) -> None:
        for node in self._nodes:
            self._publish(node, node.position_payload())

    def idle_round(self) -> None:
        """Send one position per node (beacon)."""
        for node in self._nodes:
            self._publish(node, node.position_payload())

    def chat_round(self, vocabulary: list[str]) -> None:
        """Send one random text from vocabulary per node."""
        for node in self._nodes:
            text = random.choice(vocabulary)
            self._publish(node, node.text_payload(text))

    def walk_round(self, speed_kmh: float, heading_deg: float, interval_s: float = 1.0) -> None:
        """Move each node by speed_kmh in heading_deg direction, then publish position."""
        for node in self._nodes:
            node.step(speed_kmh=speed_kmh, heading_deg=heading_deg, interval_s=interval_s)
            self._publish(node, node.position_payload())

    def burst_round(self, count: int = 5, msg_prefix: str = "burst") -> None:
        """Send count texts per node at maximum rate."""
        for node in self._nodes:
            for _ in range(count):
                text = f"{msg_prefix} #{self._total_sent + 1}"
                self._publish(node, node.text_payload(text))
