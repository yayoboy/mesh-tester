from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class RxEvent:
    """A packet received from the real mesh through a serial-connected node."""
    backend_id: str          # id of the local node that received it
    from_id: str             # source node id
    ptype: str               # "text" | "position" | "telemetry" | portnum name
    payload: object          # str for text, dict for position/telemetry, else raw
    snr: Optional[float] = None
    rssi: Optional[int] = None
    hops: Optional[int] = None
    channel: Optional[int] = None
    ts: float = 0.0


RxSink = Callable[[RxEvent], None]


class NodeBackend(abc.ABC):
    """A single test node — real (serial) or virtual (MQTT)."""

    id: str
    longname: str
    kind: str            # "virtual" | "serial"
    auto_traffic: bool   # participates in the scenario scheduler

    @property
    @abc.abstractmethod
    def connected(self) -> bool: ...

    @abc.abstractmethod
    def connect(self) -> None: ...

    @abc.abstractmethod
    def disconnect(self) -> None: ...

    @abc.abstractmethod
    def send_text(self, text: str, to: str | None = None, channel: int = 0) -> dict: ...

    @abc.abstractmethod
    def send_position(self) -> dict: ...

    @abc.abstractmethod
    def send_telemetry(self, metrics: dict | None = None) -> dict: ...
