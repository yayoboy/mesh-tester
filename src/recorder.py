from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from src.virtual_node import VirtualNode

if TYPE_CHECKING:
    from src.mqtt_injector import MqttInjector


class Recorder:
    """Records virtual-node traffic events to a JSONL file and replays them."""

    def __init__(self, path: str) -> None:
        self._path = path
        # Ensure the parent directory exists so a relative path like
        # "logs/session.jsonl" works without manual setup.
        parent = Path(path).parent
        if parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

    def record(self, node: VirtualNode, payload: dict) -> None:
        """Append one event line to the JSONL file."""
        entry = {
            "ts": time.time(),
            "node_id": node.id,
            "node_longname": node.longname,
            "node_shortname": node.shortname,
            "node_lat": node.lat,
            "node_lon": node.lon,
            "node_alt": node.alt,
            "type": payload.get("type"),
            "payload": payload,
        }
        with open(self._path, "a") as fh:
            fh.write(json.dumps(entry) + "\n")

    @staticmethod
    def replay(path: str, injector: MqttInjector, speed_multiplier: float = 1.0) -> None:
        """Replay a recorded session, publishing each event via *injector*.

        speed_multiplier:
            1.0  — real-time (original inter-event gaps)
            > 1  — faster (e.g. 2.0 = twice as fast)
            0    — no delays (instant)
        """
        with open(path) as fh:
            entries = [json.loads(line) for line in fh if line.strip()]

        prev_ts: float | None = None
        for entry in entries:
            if speed_multiplier > 0 and prev_ts is not None:
                gap = (entry["ts"] - prev_ts) / speed_multiplier
                if gap > 0:
                    time.sleep(gap)
            prev_ts = entry["ts"]

            node = VirtualNode(
                id=entry["node_id"],
                longname=entry["node_longname"],
                shortname=entry["node_shortname"],
                lat=entry["node_lat"],
                lon=entry["node_lon"],
                alt=entry["node_alt"],
            )
            injector.publish(node, entry["payload"])
