from __future__ import annotations
import json
import time
import paho.mqtt.client as mqtt
from src.virtual_node import VirtualNode

class MqttInjector:
    def __init__(self, broker: str, port: int, topic_root: str,
                 channel: str, gateway_id: str):
        self.broker = broker
        self.port = port
        self.topic = f"{topic_root}/json/{channel}/{gateway_id}"
        self._client = mqtt.Client()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self._client.connect(self.broker, self.port, keepalive=60)
        self._client.loop_start()
        self._connected = True

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    def publish(self, node: VirtualNode, payload: dict) -> float:
        ts = time.time()
        self._client.publish(self.topic, json.dumps(payload))
        return ts
