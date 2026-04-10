from __future__ import annotations
import json
import time
import paho.mqtt.client as mqtt
from src.virtual_node import VirtualNode


class MqttInjector:
    """MQTT injector that publishes Meshtastic payloads.

    Supports one or more gateway IDs (multi-gateway mode).
    When multiple gateway IDs are provided, each publish call sends to all of them.
    The ``topic`` property returns the first gateway's topic for backwards compatibility.
    """

    def __init__(
        self,
        broker: str,
        port: int,
        topic_root: str,
        channel: str,
        gateway_id: str | None = None,
        gateway_ids: list[str] | None = None,
    ):
        self.broker = broker
        self.port = port
        self._topic_root = topic_root
        self._channel = channel

        # Normalise to a list of gateway IDs
        if gateway_ids:
            self._gateway_ids = list(gateway_ids)
        elif gateway_id:
            self._gateway_ids = [gateway_id]
        else:
            raise ValueError("Provide gateway_id or gateway_ids")

        self._topics = [
            f"{topic_root}/json/{channel}/{gid}" for gid in self._gateway_ids
        ]
        self._client = mqtt.Client()
        self._connected = False

    # ── backward-compat property ───────────────────────────────────────────────

    @property
    def topic(self) -> str:
        """First gateway topic (backwards compatible)."""
        return self._topics[0]

    @property
    def topics(self) -> list[str]:
        """All gateway topics."""
        return list(self._topics)

    @property
    def gateway_ids(self) -> list[str]:
        return list(self._gateway_ids)

    @property
    def connected(self) -> bool:
        return self._connected

    # ── connection ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        self._client.connect(self.broker, self.port, keepalive=60)
        self._client.loop_start()
        self._connected = True

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    # ── publish ────────────────────────────────────────────────────────────────

    def publish(self, node: VirtualNode, payload: dict) -> float:
        """Publish *payload* for *node* to all configured gateway topics."""
        ts = time.time()
        raw = json.dumps(payload)
        for topic in self._topics:
            self._client.publish(topic, raw)
        return ts
