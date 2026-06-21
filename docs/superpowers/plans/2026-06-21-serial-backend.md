# Serial Backend Implementation Plan (Phase 1 / MVP)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a serial (real-device) node backend alongside the existing virtual MQTT backend, behind one `NodeBackend` interface, so the web tool drives a mixed fleet of real + virtual test nodes with a unified, filterable TX/RX feed.

**Architecture:** Introduce `src/backends/` with `NodeBackend` (ABC), `VirtualBackend` (wraps the existing `VirtualNode` + `MqttInjector`), and `SerialBackend` (wraps `meshtastic.serial_interface.SerialInterface`). `MeshState` holds a mixed `backends` list. TX funnels through one `_after_tx` logger; serial RX is bridged from the meshtastic reader thread to asyncio via `loop.call_soon_threadsafe`.

**Tech Stack:** Python 3.11+, FastAPI/uvicorn, paho-mqtt, **meshtastic** (SerialInterface + pypubsub), pytest.

## Global Constraints

- Python `>=3.11`; keep deps already declared (do **not** remove `meshtastic`, `PyYAML`).
- meshtastic API (verified against installed lib): `SerialInterface(devPath=...)`; `sendText(text, destinationId='^all', channelIndex=0)`; `sendPosition(latitude=0.0, longitude=0.0, altitude=0, channelIndex=0)`; `sendTelemetry(destinationId='^all', channelIndex=0)`; `getMyNodeInfo() -> dict|None`; `close()`; RX via `from pubsub import pub; pub.subscribe(cb, "meshtastic.receive")`; ports via `meshtastic.util.findPorts()`; broadcast addr `'^all'`.
- **No hardware in tests** — `SerialBackend` always takes an injectable interface factory; tests pass a fake.
- Do **not** delete existing `NodeInjector` / `_ProxyInjector` (kept for back-compat + import tests).
- Existing suite (106 tests) must stay green after every task.
- Run tests with `./.venv/bin/python -m pytest` (system `python` is 3.14 without deps).
- Serial nodes default `auto_traffic=False` (scenarios drive virtual nodes only in Phase 1).
- Commit message footer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 1: `NodeBackend` interface + `RxEvent`

**Files:**
- Create: `src/backends/__init__.py` (empty)
- Create: `src/backends/base.py`
- Test: `tests/test_backends_base.py`

**Interfaces:**
- Produces: `NodeBackend` (ABC) with attrs `id: str`, `longname: str`, `kind: str`, `auto_traffic: bool` and methods `connected` (property), `connect()`, `disconnect()`, `send_text(text, to=None, channel=0) -> dict`, `send_position() -> dict`, `send_telemetry(metrics=None) -> dict`. `RxEvent` dataclass. `RxSink = Callable[[RxEvent], None]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backends_base.py
import pytest
from src.backends.base import NodeBackend, RxEvent


def test_rxevent_holds_signal_fields():
    ev = RxEvent(backend_id="!aa", from_id="!bb", ptype="text", payload="hi",
                 snr=5.5, rssi=-90, hops=3, channel=0, ts=1.0)
    assert ev.from_id == "!bb" and ev.snr == 5.5 and ev.payload == "hi"


def test_nodebackend_is_abstract():
    with pytest.raises(TypeError):
        NodeBackend()  # cannot instantiate the ABC directly
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_backends_base.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.backends'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/backends/__init__.py
```

```python
# src/backends/base.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_backends_base.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/backends/__init__.py src/backends/base.py tests/test_backends_base.py
git commit -m "feat(backends): NodeBackend ABC + RxEvent

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `VirtualBackend`

**Files:**
- Create: `src/backends/virtual.py`
- Test: `tests/test_backends_virtual.py`

**Interfaces:**
- Consumes: `NodeBackend` (Task 1), `VirtualNode`, `MqttInjector`.
- Produces: `VirtualBackend(node, cfg)` with `kind="virtual"`, `auto_traffic=True`, `topic` property; `_telemetry_metrics() -> dict` (module-level, reused by app).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backends_virtual.py
from unittest.mock import patch
from src.config import AppConfig
from src.virtual_node import VirtualNode
from src.backends.virtual import VirtualBackend, _telemetry_metrics


def _node():
    return VirtualNode(id="!a1b2c3d4", longname="TST_Alpha", shortname="A1",
                       lat=45.0, lon=9.0, alt=100)


def test_virtual_backend_metadata():
    with patch("src.mqtt_injector.mqtt.Client"):
        b = VirtualBackend(_node(), AppConfig())
    assert b.kind == "virtual" and b.auto_traffic is True
    assert b.id == "!a1b2c3d4" and "!a1b2c3d4" in b.topic


def test_send_position_publishes_json():
    with patch("src.mqtt_injector.mqtt.Client") as cli:
        inst = cli.return_value
        b = VirtualBackend(_node(), AppConfig())
        b.connect()
        payload = b.send_position()
    assert payload["type"] == "sendposition"
    assert inst.publish.called


def test_telemetry_metrics_ranges():
    m = _telemetry_metrics()
    assert 20 <= m["battery_level"] <= 100 and 3.2 <= m["voltage"] <= 4.2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_backends_virtual.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.backends.virtual'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/backends/virtual.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_backends_virtual.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/backends/virtual.py tests/test_backends_virtual.py
git commit -m "feat(backends): VirtualBackend over MqttInjector

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: serial port discovery

**Files:**
- Create: `src/serial_ports.py`
- Test: `tests/test_serial_ports.py`

**Interfaces:**
- Produces: `list_ports() -> list[str]` (Meshtastic candidate device paths; never raises).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_serial_ports.py
import src.serial_ports as sp


def test_list_ports_uses_meshtastic_findports(monkeypatch):
    monkeypatch.setattr(sp, "_find_meshtastic_ports", lambda: ["/dev/ttyUSB0", "/dev/ttyUSB1"])
    assert sp.list_ports() == ["/dev/ttyUSB0", "/dev/ttyUSB1"]


def test_list_ports_never_raises(monkeypatch):
    def boom():
        raise RuntimeError("no lib")
    monkeypatch.setattr(sp, "_find_meshtastic_ports", boom)
    monkeypatch.setattr(sp, "_find_pyserial_ports", lambda: [])
    assert sp.list_ports() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_serial_ports.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.serial_ports'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/serial_ports.py
from __future__ import annotations


def _find_meshtastic_ports() -> list[str]:
    from meshtastic.util import findPorts
    return list(findPorts())


def _find_pyserial_ports() -> list[str]:
    from serial.tools import list_ports as _lp
    return [p.device for p in _lp.comports()]


def list_ports() -> list[str]:
    """Candidate serial device paths for Meshtastic devices. Never raises."""
    try:
        ports = _find_meshtastic_ports()
        if ports:
            return ports
    except Exception:
        pass
    try:
        return _find_pyserial_ports()
    except Exception:
        return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_serial_ports.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/serial_ports.py tests/test_serial_ports.py
git commit -m "feat(serial): list_ports() device discovery

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `SerialBackend` (fake-interface tested)

**Files:**
- Create: `src/backends/serial.py`
- Test: `tests/test_backends_serial.py`

**Interfaces:**
- Consumes: `NodeBackend`, `RxEvent`, `RxSink` (Task 1).
- Produces: `SerialBackend(port, sink, interface_factory=_default_interface_factory)` with `kind="serial"`, `auto_traffic=False`. `interface_factory(port) -> iface` is injectable for tests. RX callback `_on_receive(packet, interface)` builds an `RxEvent` and calls `sink`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backends_serial.py
from src.backends.serial import SerialBackend


class FakeIface:
    def __init__(self, port):
        self.port = port
        self.sent = []
    def getMyNodeInfo(self):
        return {"num": 2712847316, "user": {"id": "!a1b2c3d4", "longName": "Real One"}}
    def sendText(self, text, destinationId="^all", channelIndex=0, **kw):
        self.sent.append(("text", text, destinationId, channelIndex))
    def sendPosition(self, **kw):
        self.sent.append(("position",))
    def sendTelemetry(self, **kw):
        self.sent.append(("telemetry",))
    def close(self):
        self.closed = True


def _backend():
    events = []
    b = SerialBackend("/dev/ttyUSB0", sink=events.append,
                      interface_factory=lambda port: FakeIface(port))
    return b, events


def test_connect_reads_node_identity():
    b, _ = _backend()
    assert b.connected is False
    b.connect()
    assert b.connected is True
    assert b.id == "!a1b2c3d4" and b.longname == "Real One" and b.kind == "serial"


def test_send_text_calls_iface():
    b, _ = _backend()
    b.connect()
    b.send_text("hello", to="!ffffffff", channel=2)
    assert b._iface.sent == [("text", "hello", "!ffffffff", 2)]


def test_rx_callback_emits_event():
    b, events = _backend()
    b.connect()
    packet = {"fromId": "!deadbeef", "rxSnr": 6.25, "rxRssi": -88, "hopLimit": 3,
              "channel": 0, "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "ping"}}
    b._on_receive(packet=packet, interface=b._iface)
    assert len(events) == 1
    ev = events[0]
    assert ev.from_id == "!deadbeef" and ev.snr == 6.25 and ev.payload == "ping"
    assert ev.ptype == "TEXT_MESSAGE_APP"


def test_disconnect_closes_iface():
    b, _ = _backend()
    b.connect()
    b.disconnect()
    assert b.connected is False and getattr(b._iface, "closed", False) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_backends_serial.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.backends.serial'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/backends/serial.py
from __future__ import annotations

import time
from typing import Callable, Optional

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_backends_serial.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/backends/serial.py tests/test_backends_serial.py
git commit -m "feat(backends): SerialBackend over meshtastic SerialInterface

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: MeshState routes TX through virtual backends

**Files:**
- Modify: `src/web/app.py` (MeshState, `_emit`, `_node_loop`, `/api/start`, `_node_list`, `_telemetry_metrics` import)
- Test: `tests/test_web_api.py` (add mixed-list assertions)

**Interfaces:**
- Consumes: `VirtualBackend` (Task 2), `_telemetry_metrics` (Task 2).
- Produces: `MeshState.backends: list[NodeBackend]`; `_node_list()` entries gain `kind` and `port`; `_after_tx(backend, payload)` shared TX logger.

This task refactors the working MQTT path. Keep `NodeInjector`/`_ProxyInjector` defined (do not delete). Existing tests must stay green.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_api.py  (append)
def test_nodes_report_kind_virtual():
    client = make_client()
    nodes = client.get("/api/nodes").json()
    assert all(n["kind"] == "virtual" for n in nodes)
    assert all("port" in n for n in nodes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_web_api.py::test_nodes_report_kind_virtual -q`
Expected: FAIL with `KeyError: 'kind'`

- [ ] **Step 3: Write minimal implementation**

In `src/web/app.py` imports add:

```python
from src.backends.base import NodeBackend, RxEvent
from src.backends.virtual import VirtualBackend, _telemetry_metrics  # noqa: F401 (re-export)
```

Delete the local `def _telemetry_metrics()` block in `app.py` (now imported from `virtual`). Keep its single definition in `backends/virtual.py`.

In `MeshState.__init__`, after `self.nodes = ...`, add:

```python
        self.backends: list[NodeBackend] = []
```

Replace the body of `/api/start` node-injector setup so it builds backends too. After the existing `state.node_injectors = [...]` and `state.proxy_injector = ...` lines, add:

```python
        state.backends = [VirtualBackend(n, state.cfg) for n in state.nodes]
        for b in state.backends:
            b.connect()
```

Change `_emit` to record via the backend lookup but keep publishing through the proxy (no behavior change yet — backends are connected in parallel). Add the shared logger and a backend index. In `MeshState.__init__` add:

```python
        self.backend_by_id: dict[str, NodeBackend] = {}
```

and in `/api/start` after building backends:

```python
        state.backend_by_id = {b.id: b for b in state.backends}
```

Update `_node_list()` to include kind/port:

```python
    def _node_list() -> list[dict]:
        board_map = {ni.node.id: ni for ni in state.node_injectors}
        bmap = state.backend_by_id
        out = []
        for n in state.nodes:
            b = bmap.get(n.id)
            out.append({
                "id": n.id, "longname": n.longname, "shortname": n.shortname,
                "lat": round(n.lat, 6), "lon": round(n.lon, 6), "alt": n.alt,
                "sent": state.sent_per_node.get(n.id, 0), "is_rogue": n.is_rogue,
                "topic": board_map[n.id].topic if n.id in board_map else None,
                "board_connected": board_map[n.id].connected if n.id in board_map else False,
                "kind": b.kind if b else "virtual",
                "port": getattr(b, "port", None) if b else None,
            })
        return out
```

- [ ] **Step 4: Run the full suite**

Run: `./.venv/bin/python -m pytest -q`
Expected: PASS (all existing + new green). If `test_proxy_injector_topic_from_first_node` or `_telemetry_metrics` import tests reference moved names, confirm `_telemetry_metrics` is re-exported from `app` (it is, via the import line) and `NodeInjector`/`_ProxyInjector` still exist.

- [ ] **Step 5: Commit**

```bash
git add src/web/app.py tests/test_web_api.py
git commit -m "refactor(web): build VirtualBackend fleet in MeshState, expose kind/port

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: RX bridge + serial connect/disconnect/ports API

**Files:**
- Modify: `src/web/app.py` (MeshState fields, routes, RX sink)
- Test: `tests/test_web_serial_api.py`

**Interfaces:**
- Consumes: `SerialBackend` (Task 4), `list_ports` (Task 3), `RxEvent`.
- Produces: routes `GET /api/serial/ports`, `POST /api/serial/connect`, `POST /api/serial/{node_id}/disconnect`; `state.loop`; `_rx_sink(ev)`; WS event `{"type":"log","level":"rx", ...}`. Serial connect uses an injectable factory stored on `state.serial_interface_factory` (default `None` → real).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_serial_api.py
from fastapi.testclient import TestClient
from src.config import AppConfig
from src.web.app import create_app


class FakeIface:
    def __init__(self, port): self.port = port
    def getMyNodeInfo(self):
        return {"num": 1, "user": {"id": "!00000001", "longName": "USB Node"}}
    def sendText(self, *a, **k): pass
    def sendPosition(self, *a, **k): pass
    def sendTelemetry(self, *a, **k): pass
    def close(self): pass


def make_client():
    cfg = AppConfig(); cfg.nodes.count = 2
    app = create_app(cfg)
    app.state.serial_interface_factory = lambda port: FakeIface(port)  # injected
    return TestClient(app)


def test_serial_ports_endpoint(monkeypatch):
    import src.web.app as appmod
    monkeypatch.setattr(appmod, "list_ports", lambda: ["/dev/ttyUSB0"])
    client = make_client()
    assert client.get("/api/serial/ports").json() == ["/dev/ttyUSB0"]


def test_serial_connect_adds_node():
    client = make_client()
    resp = client.post("/api/serial/connect", json={"port": "/dev/ttyUSB0"})
    data = resp.json()
    assert data["ok"] is True and data["node"]["kind"] == "serial"
    nodes = client.get("/api/nodes").json()
    assert any(n["kind"] == "serial" and n["port"] == "/dev/ttyUSB0" for n in nodes)


def test_serial_disconnect_removes_node():
    client = make_client()
    client.post("/api/serial/connect", json={"port": "/dev/ttyUSB0"})
    nid = next(n["id"] for n in client.get("/api/nodes").json() if n["kind"] == "serial")
    assert client.post(f"/api/serial/{nid}/disconnect").json()["ok"] is True
    assert all(n["kind"] != "serial" for n in client.get("/api/nodes").json())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_web_serial_api.py -q`
Expected: FAIL (404 / missing routes)

- [ ] **Step 3: Write minimal implementation**

In `src/web/app.py` imports add:

```python
import asyncio
from src.backends.serial import SerialBackend
from src.serial_ports import list_ports
```

In `MeshState.__init__` add:

```python
        self.loop = None
        self.serial_backends: list = []
```

Make `_node_list()` include serial nodes (not only `state.nodes`). After the virtual loop, append:

```python
        for b in state.serial_backends:
            out.append({
                "id": b.id, "longname": b.longname, "shortname": b.id[-4:],
                "lat": None, "lon": None, "alt": None,
                "sent": state.sent_per_node.get(b.id, 0), "is_rogue": False,
                "topic": None, "board_connected": b.connected,
                "kind": "serial", "port": b.port,
            })
```

Add the RX sink + broadcast helpers and routes inside `create_app` (after `_emit`):

```python
    async def _broadcast_rx(ev: RxEvent) -> None:
        pl = ev.payload if isinstance(ev.payload, (str, int, float)) else None
        await manager.broadcast({
            "type": "log", "level": "rx",
            "node": ev.backend_id, "from": ev.from_id, "ptype": ev.ptype,
            "snr": ev.snr, "rssi": ev.rssi, "hops": ev.hops,
            "channel": ev.channel, "payload": pl, "ts": ev.ts,
        })

    def _rx_sink(ev: RxEvent) -> None:
        loop = state.loop
        if loop is None:
            return
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_broadcast_rx(ev)))

    @app.get("/api/serial/ports")
    async def serial_ports() -> list:
        return list_ports()

    @app.post("/api/serial/connect")
    async def serial_connect(body: dict) -> dict:
        state.loop = asyncio.get_running_loop()
        port = body.get("port")
        if not port:
            return {"ok": False, "reason": "missing port"}
        factory = getattr(app.state, "serial_interface_factory", None)
        kwargs = {"interface_factory": factory} if factory else {}
        backend = SerialBackend(port, sink=_rx_sink, **kwargs)
        try:
            backend.connect()
        except Exception as exc:
            return {"ok": False, "reason": f"serial connect failed: {exc}"}
        state.serial_backends.append(backend)
        state.backend_by_id[backend.id] = backend
        await manager.broadcast({"type": "nodes_snapshot", "nodes": _node_list()})
        node = next((n for n in _node_list() if n["id"] == backend.id), None)
        return {"ok": True, "node": node}

    @app.post("/api/serial/{node_id}/disconnect")
    async def serial_disconnect(node_id: str) -> dict:
        b = next((x for x in state.serial_backends if x.id == node_id), None)
        if b is None:
            return {"ok": False, "reason": "serial node not found"}
        b.disconnect()
        state.serial_backends.remove(b)
        state.backend_by_id.pop(node_id, None)
        await manager.broadcast({"type": "nodes_snapshot", "nodes": _node_list()})
        return {"ok": True}
```

Note (real-hardware gotcha, not test-blocking): pypubsub holds listeners weakly; the `SerialBackend` stays referenced via `state.serial_backends`, keeping `_on_receive` alive. Confirm RX still fires after GC during the hardware bring-up.

- [ ] **Step 4: Run tests**

Run: `./.venv/bin/python -m pytest tests/test_web_serial_api.py -q && ./.venv/bin/python -m pytest -q`
Expected: PASS (new file green + full suite green)

- [ ] **Step 5: Commit**

```bash
git add src/web/app.py tests/test_web_serial_api.py
git commit -m "feat(web): serial connect/disconnect/ports + RX-to-WebSocket bridge

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: manual send from any node

**Files:**
- Modify: `src/web/app.py` (route + `_after_tx`)
- Test: `tests/test_web_serial_api.py` (append)

**Interfaces:**
- Consumes: `state.backend_by_id` (Task 5/6).
- Produces: `POST /api/nodes/{node_id}/send` body `{"type": "text"|"position"|"telemetry", "text"?, "to"?, "channel"?}`; `_after_tx(node_or_id, payload)` logs to feed + recorder + WS.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_serial_api.py  (append)
def test_manual_send_text_from_serial_node():
    client = make_client()
    client.post("/api/serial/connect", json={"port": "/dev/ttyUSB0"})
    nid = next(n["id"] for n in client.get("/api/nodes").json() if n["kind"] == "serial")
    resp = client.post(f"/api/nodes/{nid}/send", json={"type": "text", "text": "hi"})
    assert resp.json()["ok"] is True


def test_manual_send_unknown_node():
    client = make_client()
    resp = client.post("/api/nodes/!nope/send", json={"type": "text", "text": "x"})
    assert resp.json()["ok"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_web_serial_api.py::test_manual_send_text_from_serial_node -q`
Expected: FAIL (404)

- [ ] **Step 3: Write minimal implementation**

Add a `SendBody` schema near the other Pydantic models:

```python
class SendBody(BaseModel):
    type: str = Field(pattern="^(text|position|telemetry)$")
    text: Optional[str] = Field(default=None, max_length=200)
    to: Optional[str] = None
    channel: int = Field(default=0, ge=0, le=7)
```

Add the route inside `create_app`:

```python
    @app.post("/api/nodes/{node_id}/send")
    async def manual_send(node_id: str, body: SendBody) -> dict:
        b = state.backend_by_id.get(node_id)
        if b is None:
            return {"ok": False, "reason": "node not found"}
        if not b.connected:
            return {"ok": False, "reason": "node not connected"}
        try:
            if body.type == "text":
                payload = b.send_text(body.text or "", to=body.to, channel=body.channel)
            elif body.type == "position":
                payload = b.send_position()
            else:
                payload = b.send_telemetry()
        except Exception as exc:
            return {"ok": False, "reason": f"send failed: {exc}"}
        state.total_sent += 1
        state.sent_per_node[node_id] = state.sent_per_node.get(node_id, 0) + 1
        await manager.broadcast({
            "type": "log", "level": "tx", "node": b.longname, "node_id": node_id,
            "ptype": payload.get("type"), "payload": payload.get("payload"),
            "ts": time.time(),
        })
        return {"ok": True, "sent": payload}
```

- [ ] **Step 4: Run tests**

Run: `./.venv/bin/python -m pytest tests/test_web_serial_api.py -q && ./.venv/bin/python -m pytest -q`
Expected: PASS (full suite green)

- [ ] **Step 5: Commit**

```bash
git add src/web/app.py tests/test_web_serial_api.py
git commit -m "feat(web): POST /api/nodes/{id}/send manual TX from any backend

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: dashboard — mixed list, connect-serial, manual send, filterable feed

**Files:**
- Modify: `src/web/static/index.html`
- Test: manual (browser) — documented checklist; no automated UI test in this stack.

**Interfaces:**
- Consumes: `/api/serial/ports`, `/api/serial/connect`, `/api/serial/{id}/disconnect`, `/api/nodes/{id}/send`, WS `level:"rx"|"tx"`.

- [ ] **Step 1: Node badge.** In the Alpine node-row template, add next to the node name:

```html
<span class="text-[10px] px-1 rounded"
      :class="n.kind === 'serial' ? 'bg-yellow-700 text-yellow-100' : 'bg-zinc-700 text-zinc-300'"
      x-text="n.kind === 'serial' ? ('SERIAL · ' + (n.port || '')) : 'VIRT'"></span>
```

- [ ] **Step 2: Connect-serial control.** Add a panel that loads ports and connects:

```html
<div class="flex gap-2 items-center">
  <select x-model="serialPort" class="bg-ink-900 text-xs rounded px-2 py-1">
    <template x-for="p in serialPorts" :key="p"><option :value="p" x-text="p"></option></template>
  </select>
  <button @click="loadSerialPorts()" class="text-xs">↻</button>
  <button @click="connectSerial()" :disabled="!serialPort" class="text-xs">Connect</button>
</div>
```

In the Alpine data object add `serialPort: '', serialPorts: []` and methods:

```javascript
async loadSerialPorts() { this.serialPorts = await (await fetch('/api/serial/ports')).json(); },
async connectSerial() {
  await this.apiPost('/api/serial/connect', { port: this.serialPort });
},
sendFrom(id, type, text) { return this.apiPost(`/api/nodes/${id}/send`, { type, text }); },
```

- [ ] **Step 3: Feed filters + RX/TX rendering.** Add filter state `feedFilters: { dir: 'all', type: 'all', node: 'all' }` and a computed `filteredLog`:

```javascript
get filteredLog() {
  return this.log.filter(e => {
    const dir = e.level === 'rx' ? 'rx' : 'tx';
    if (this.feedFilters.dir !== 'all' && this.feedFilters.dir !== dir) return false;
    if (this.feedFilters.node !== 'all' && (e.node_id || e.node) !== this.feedFilters.node) return false;
    return true;
  });
}
```

Point the feed `x-for` at `filteredLog` instead of `log`, and add an `entry.level === 'rx'` template:

```html
<template x-if="entry.level === 'rx'">
  <span>
    <i class="ph-duotone ph-arrow-down ph-xs text-sky-400 mr-0.5"></i>
    <span class="text-sky-300 font-medium" x-text="entry.from"></span>
    <span class="text-ink-faint mx-1" x-text="entry.ptype"></span>
    <span class="text-ink-muted" x-text="entry.payload ?? ''"></span>
    <span class="text-ink-faint ml-1" x-show="entry.snr != null" x-text="`SNR ${entry.snr} · RSSI ${entry.rssi}`"></span>
  </span>
</template>
```

- [ ] **Step 4: Manual verification checklist.** Start the app on the host:

```bash
./.venv/bin/python web_main.py
```

Verify in the browser at `http://localhost:8080`: (a) virtual nodes show **VIRT** badge; (b) `/api/serial/ports` populates the dropdown (empty is fine without a device); (c) with a device, Connect adds a **SERIAL** node; (d) manual send buttons call the API; (e) feed filter chips switch between TX/RX/all. With no device, confirm the dropdown is empty and nothing crashes.

- [ ] **Step 5: Commit**

```bash
git add src/web/static/index.html
git commit -m "feat(web/ui): serial node badge, connect control, manual send, filterable TX/RX feed

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: docs — README serial section + Docker/USB caveat

**Files:**
- Modify: `README.md`
- Modify: `TASKS.md`

- [ ] **Step 1: README serial section.** Under Architecture, add a "Serial (real) nodes" subsection: backends abstraction (`VirtualBackend` | `SerialBackend`), how to connect a device (host-run, `/api/serial/ports` → Connect), the **USB + Docker caveat** (serial needs host access or compose `devices: ["/dev/ttyUSB0:/dev/ttyUSB0"]` + `group_add`), and that scenarios drive virtual nodes only in this phase (serial = manual send).

- [ ] **Step 2: TASKS.md.** Add a "v4 — serial backend (Phase 1)" section listing Tasks 1–9 as done, and bump the test count to the new total.

- [ ] **Step 3: Run the full suite** to capture the final count.

Run: `./.venv/bin/python -m pytest -q`
Expected: PASS — record the number printed.

- [ ] **Step 4: Commit**

```bash
git add README.md TASKS.md
git commit -m "docs: serial backend usage + Docker/USB caveat + TASKS v4

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:** unified `NodeBackend` (T1) ✓; VirtualBackend refactor (T2,T5) ✓; SerialBackend via meshtastic (T4) ✓; port discovery (T3) ✓; connect/disconnect API (T6) ✓; RX thread→asyncio bridge + `rx` feed event (T6) ✓; manual send any node (T7) ✓; mixed list + filterable feed UI (T8) ✓; error handling (clean failures in T4/T6/T7) ✓; testing with fake interface (T4,T6) ✓; Docker/USB caveat (T9) ✓. Deferred per spec (Phase 2): admin, traceroute, serial scenario auto-traffic, ACK/delivery — intentionally absent.

**Placeholder scan:** no TBD/TODO; every code step shows full code; the only "verify on hardware" notes are explicit Phase-1 limits, not missing code.

**Type consistency:** `send_text(text, to=None, channel=0)`, `send_position()`, `send_telemetry(metrics=None)` identical across base/virtual/serial; `RxEvent` fields match producer (T4 `_on_receive`) and consumer (T6 `_broadcast_rx`); `state.backend_by_id` defined in T5, used in T6/T7; `serial_interface_factory` injected via `app.state` in T6 test and route.
