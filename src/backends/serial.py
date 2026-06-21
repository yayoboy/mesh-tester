from __future__ import annotations

import time
from typing import Callable

from src.backends.base import NodeBackend, RxEvent, RxSink


def _default_interface_factory(port: str):
    # Imported lazily so the module loads without hardware / the meshtastic lib.
    from meshtastic.serial_interface import SerialInterface
    return SerialInterface(devPath=port)


class SerialBackend(NodeBackend):
    """A real Meshtastic node reachable over a serial (USB) port."""

    kind = "serial"

    def __init__(self, port: str, sink: RxSink,
                 interface_factory: Callable[[str], object] = _default_interface_factory) -> None:
        self.port = port
        self.id = port            # placeholder until connected
        self.longname = port
        self.auto_traffic = False
        self._sink = sink
        self._factory = interface_factory
        self._iface = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self._iface = self._factory(self.port)
        info = self._iface.getMyNodeInfo() or {}
        user = info.get("user", {}) if isinstance(info, dict) else {}
        num = info.get("num") if isinstance(info, dict) else None
        self.id = user.get("id") or (f"!{num:08x}" if isinstance(num, int) else self.port)
        self.longname = user.get("longName") or self.id
        try:
            from pubsub import pub
            # pypubsub holds listeners weakly; MeshState keeps this backend referenced so the callback survives.
            pub.subscribe(self._on_receive, "meshtastic.receive")
        except Exception:
            pass
        self._connected = True

    def disconnect(self) -> None:
        try:
            from pubsub import pub
            pub.unsubscribe(self._on_receive, "meshtastic.receive")
        except Exception:
            pass
        if self._iface is not None:
            try:
                self._iface.close()
            except Exception:
                pass
        self._connected = False

    def send_text(self, text: str, to: str | None = None, channel: int = 0) -> dict:
        self._iface.sendText(text, destinationId=to or "^all", channelIndex=channel)
        return {"type": "sendtext", "payload": text, "to": to, "channel": channel}

    def send_position(self) -> dict:
        self._iface.sendPosition()
        return {"type": "sendposition"}

    def send_telemetry(self, metrics: dict | None = None) -> dict:
        self._iface.sendTelemetry()
        return {"type": "telemetry"}

    def _on_receive(self, packet=None, interface=None) -> None:
        if not isinstance(packet, dict):
            return
        dec = packet.get("decoded", {}) or {}
        payload = dec.get("text")
        if payload is None:
            payload = dec.get("position") or dec.get("telemetry") or dec
        ev = RxEvent(
            backend_id=self.id,
            from_id=str(packet.get("fromId") or packet.get("from", "?")),
            ptype=str(dec.get("portnum", "UNKNOWN")),
            payload=payload,
            snr=packet.get("rxSnr"),
            rssi=packet.get("rxRssi"),
            hops=packet.get("hopLimit"),
            channel=packet.get("channel"),
            ts=time.time(),
        )
        self._sink(ev)
