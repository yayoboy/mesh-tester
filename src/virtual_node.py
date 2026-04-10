from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


@dataclass
class VirtualNode:
    id: str
    longname: str
    shortname: str
    lat: float
    lon: float
    alt: int
    is_rogue: bool = False

    # ── factories ──────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, cfg: dict) -> VirtualNode:
        return cls(
            id=cfg["id"], longname=cfg["longname"], shortname=cfg["shortname"],
            lat=cfg["lat"], lon=cfg["lon"], alt=cfg["alt"],
        )

    # ── properties ─────────────────────────────────────────────────────────────

    @property
    def id_decimal(self) -> int:
        return int(self.id[1:], 16)

    @property
    def latitude_i(self) -> int:
        return int(self.lat * 1e7)

    @property
    def longitude_i(self) -> int:
        return int(self.lon * 1e7)

    # ── mobility ───────────────────────────────────────────────────────────────

    def step(self, speed_kmh: float, heading_deg: float, interval_s: float = 1.0) -> None:
        """Move the node by *speed_kmh* in direction *heading_deg* for *interval_s* seconds.

        heading_deg: 0=North, 90=East, 180=South, 270=West.
        Updates lat/lon in place.
        """
        dist_km = speed_kmh * interval_s / 3600.0
        heading_rad = math.radians(heading_deg)
        dlat = dist_km / 111.0 * math.cos(heading_rad)
        dlon = dist_km / (111.0 * math.cos(math.radians(self.lat))) * math.sin(heading_rad)
        self.lat = round(self.lat + dlat, 7)
        self.lon = round(self.lon + dlon, 7)

    # ── payloads ───────────────────────────────────────────────────────────────

    def text_payload(self, text: str, to_node_id: str | None = None) -> dict:
        payload: dict = {"from": self.id_decimal, "type": "sendtext", "payload": text}
        if to_node_id is not None:
            payload["to"] = int(to_node_id[1:], 16)
        if self.is_rogue:
            payload["_rogue"] = True          # marker for rogue/malformed message
            payload["from"] = 0xDEADBEEF     # spoofed source ID
        return payload

    def position_payload(self) -> dict:
        return {
            "from": self.id_decimal,
            "type": "sendposition",
            "payload": {
                "latitude_i": self.latitude_i,
                "longitude_i": self.longitude_i,
                "altitude": self.alt,
                "time": int(time.time()),
            },
        }

    def telemetry_payload(
        self,
        battery_level: int = 100,
        voltage: float = 4.1,
        snr: float = 0.0,
        rssi: int = -100,
    ) -> dict:
        """Return a Meshtastic telemetry payload with device metrics."""
        return {
            "from": self.id_decimal,
            "type": "telemetry",
            "payload": {
                "battery_level": battery_level,
                "voltage": round(voltage, 2),
                "snr": round(snr, 1),
                "rssi": rssi,
                "time": int(time.time()),
            },
        }
