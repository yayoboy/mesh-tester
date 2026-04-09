from __future__ import annotations
from dataclasses import dataclass
import time

@dataclass
class VirtualNode:
    id: str
    longname: str
    shortname: str
    lat: float
    lon: float
    alt: int

    @classmethod
    def from_config(cls, cfg: dict) -> VirtualNode:
        return cls(
            id=cfg["id"], longname=cfg["longname"], shortname=cfg["shortname"],
            lat=cfg["lat"], lon=cfg["lon"], alt=cfg["alt"],
        )

    @property
    def id_decimal(self) -> int:
        return int(self.id[1:], 16)

    @property
    def latitude_i(self) -> int:
        return int(self.lat * 1e7)

    @property
    def longitude_i(self) -> int:
        return int(self.lon * 1e7)

    def text_payload(self, text: str, to_node_id: str | None = None) -> dict:
        payload = {"from": self.id_decimal, "type": "sendtext", "payload": text}
        if to_node_id is not None:
            payload["to"] = int(to_node_id[1:], 16)
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
