from __future__ import annotations

import random

from src.backends.base import NodeBackend
from src.mqtt_injector import MqttInjector
from src.virtual_node import VirtualNode


def _telemetry_metrics() -> dict:
    """Plausible device metrics for a telemetry payload (voltage tracks battery)."""
    battery = random.randint(20, 100)
    return {
        "battery_level": battery,
        "voltage": round(3.2 + battery / 100 * 1.0, 2),
        "snr": round(random.uniform(-5.0, 12.0), 1),
        "rssi": random.randint(-120, -40),
    }


class VirtualBackend(NodeBackend):
    """A virtual node that publishes Meshtastic JSON over MQTT."""

    kind = "virtual"

    def __init__(self, node: VirtualNode, cfg) -> None:
        self.node = node
        self.id = node.id
        self.longname = node.longname
        self.auto_traffic = True
        self._inj = MqttInjector(
            broker=cfg.mqtt.broker, port=cfg.mqtt.port,
            topic_root=cfg.mqtt.topic_root, channel=cfg.mqtt.channel,
            gateway_id=node.id,
        )

    @property
    def topic(self) -> str:
        return self._inj.topic

    @property
    def connected(self) -> bool:
        return self._inj.connected

    def connect(self) -> None:
        self._inj.connect()

    def disconnect(self) -> None:
        if self._inj.connected:
            self._inj.disconnect()

    def send_text(self, text: str, to: str | None = None, channel: int = 0) -> dict:
        payload = self.node.text_payload(text, to_node_id=to)
        self._inj.publish(self.node, payload)
        return payload

    def send_position(self) -> dict:
        payload = self.node.position_payload()
        self._inj.publish(self.node, payload)
        return payload

    def send_telemetry(self, metrics: dict | None = None) -> dict:
        payload = self.node.telemetry_payload(**(metrics or _telemetry_metrics()))
        self._inj.publish(self.node, payload)
        return payload
