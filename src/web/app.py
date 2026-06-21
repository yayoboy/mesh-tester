from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.backends.base import NodeBackend, RxEvent
from src.backends.serial import SerialBackend
from src.backends.virtual import VirtualBackend, _telemetry_metrics  # noqa: F401 (re-export)
from src.config import AppConfig, ZoneConfig, load_config
from src.serial_ports import list_ports
from src.mqtt_injector import MqttInjector
from src.node_factory import NodeFactory
from src.recorder import Recorder
from src.virtual_node import VirtualNode
from src.zone import ITALY_PRESETS

_STATIC = Path(__file__).parent / "static"
_CHAT_VOCAB = ["ciao", "hello", "ack", "ok", "test", "ping", "here", "on air"]


# ── Scenario profiles ──────────────────────────────────────────────────────────

@dataclass
class ScenarioProfile:
    """Per-scenario timing and payload shape.

    Each virtual node runs an independent loop that:
      1. sleeps ``interval_s * (1 ± jitter_pct)``
      2. emits ``burst_size`` messages of kind ``kind``

    This gives every node an independent cadence, so scenarios with higher
    jitter look visibly more chaotic than low-jitter ones.
    """
    interval_s: float
    jitter_pct: float
    burst_size: int
    kind: str  # "position" | "chat" | "walk" | "burst_chat" | "telemetry"


DEFAULT_SCENARIOS: dict[str, ScenarioProfile] = {
    "idle":      ScenarioProfile(interval_s=60.0, jitter_pct=0.50, burst_size=1, kind="position"),
    "chat":      ScenarioProfile(interval_s=15.0, jitter_pct=0.70, burst_size=1, kind="chat"),
    "walk":      ScenarioProfile(interval_s=8.0,  jitter_pct=0.20, burst_size=1, kind="walk"),
    "burst":     ScenarioProfile(interval_s=6.0,  jitter_pct=0.10, burst_size=5, kind="burst_chat"),
    "telemetry": ScenarioProfile(interval_s=30.0, jitter_pct=0.40, burst_size=1, kind="telemetry"),
}


# ── WebSocket connection manager ───────────────────────────────────────────────

class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, data: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# ── Per-node injector ──────────────────────────────────────────────────────────

class NodeInjector:
    """Wraps a dedicated MqttInjector for a single virtual node (multi-board mode)."""

    def __init__(self, node: VirtualNode, cfg: AppConfig) -> None:
        self._node = node
        self._inj = MqttInjector(
            broker=cfg.mqtt.broker,
            port=cfg.mqtt.port,
            topic_root=cfg.mqtt.topic_root,
            channel=cfg.mqtt.channel,
            gateway_id=node.id,
        )

    @property
    def node(self) -> VirtualNode:
        return self._node

    @property
    def injector(self) -> MqttInjector:
        return self._inj

    @property
    def topic(self) -> str:
        return self._inj.topic

    def connect(self) -> None:
        self._inj.connect()

    def disconnect(self) -> None:
        if self._inj.connected:
            self._inj.disconnect()

    @property
    def connected(self) -> bool:
        return self._inj.connected

    def publish(self, payload: dict) -> float:
        return self._inj.publish(self._node, payload)


# ── Proxy injector ─────────────────────────────────────────────────────────────

class _ProxyInjector:
    """Fans a publish to the right NodeInjector. Kept for grouped connect/disconnect."""

    def __init__(self, node_injectors: list[NodeInjector]) -> None:
        self._map = {ni.node.id: ni for ni in node_injectors}
        self.topic = next(iter(self._map.values())).topic if self._map else ""
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        for ni in self._map.values():
            ni.connect()
        self._connected = True

    def disconnect(self) -> None:
        for ni in self._map.values():
            ni.disconnect()
        self._connected = False

    def publish(self, node: VirtualNode, payload: dict) -> float:
        ni = self._map.get(node.id)
        if ni:
            return ni.publish(payload)
        return time.time()


# ── Runtime state ──────────────────────────────────────────────────────────────

class MeshState:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.nodes: list[VirtualNode] = NodeFactory(
            cfg.zone, cfg.nodes, seed=42
        ).generate()
        self.node_injectors: list[NodeInjector] = []
        self.proxy_injector: Optional[_ProxyInjector] = None
        self.backends: list[NodeBackend] = []
        self.backend_by_id: dict[str, NodeBackend] = {}
        self.running: bool = False
        self.paused: bool = False
        self.mqtt_connected: bool = False
        self.active_scenario: str = "idle"
        self.scenarios: dict[str, ScenarioProfile] = {
            k: ScenarioProfile(**asdict(v)) for k, v in DEFAULT_SCENARIOS.items()
        }
        self.sent_per_node: dict[str, int] = {}
        self.total_sent: int = 0
        self._start_time: float = 0.0
        self._node_tasks: list[asyncio.Task] = []
        self.loop = None
        self.serial_backends: list = []
        # Optional JSONL session recorder (enabled via config.log_to_file)
        self.recorder: Optional[Recorder] = (
            Recorder(cfg.log_path) if cfg.log_to_file else None
        )

    def rebuild_nodes(self) -> None:
        self.nodes = NodeFactory(self.cfg.zone, self.cfg.nodes, seed=42).generate()
        self.sent_per_node = {}
        self.total_sent = 0


# ── Request schemas ────────────────────────────────────────────────────────────

class CustomZoneBody(BaseModel):
    name: str = Field(default="Custom", max_length=40)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=5.0, gt=0, le=200)


class ScenarioProfileBody(BaseModel):
    interval_s: Optional[float] = Field(default=None, gt=0, le=3600)
    jitter_pct: Optional[float] = Field(default=None, ge=0, le=1)
    burst_size: Optional[int] = Field(default=None, ge=1, le=50)


class NodeCountBody(BaseModel):
    count: int = Field(ge=1, le=50)


class NodePatchBody(BaseModel):
    longname: Optional[str] = Field(default=None, max_length=40)
    shortname: Optional[str] = Field(default=None, max_length=4)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    alt: Optional[int] = Field(default=None, ge=-500, le=10000)
    is_rogue: Optional[bool] = None


class SendBody(BaseModel):
    type: str = Field(pattern="^(text|position|telemetry)$")
    text: Optional[str] = Field(default=None, max_length=200)
    to: Optional[str] = None
    channel: int = Field(default=0, ge=0, le=7)


# ── App factory ────────────────────────────────────────────────────────────────

def create_app(cfg: Optional[AppConfig] = None) -> FastAPI:
    if cfg is None:
        cfg = load_config()

    app = FastAPI(title="Mesh Tester", description="Virtual Meshtastic node injector")
    manager = ConnectionManager()
    state = MeshState(cfg)

    if _STATIC.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    # ── helpers ────────────────────────────────────────────────────────────────

    def _status_dict() -> dict:
        elapsed = int(time.time() - state._start_time) if state._start_time else 0
        return {
            "running": state.running,
            "paused": state.paused,
            "mqtt_connected": state.mqtt_connected,
            "scenario": state.active_scenario,
            "total_sent": state.total_sent,
            "uptime": elapsed,
            "zone": state.cfg.zone.name,
            "zone_center": {
                "lat": state.cfg.zone.center_lat,
                "lon": state.cfg.zone.center_lon,
                "radius_km": state.cfg.zone.radius_km,
            },
            "node_count": len(state.nodes),
            "scenarios": {k: asdict(v) for k, v in state.scenarios.items()},
        }

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
        for b in state.serial_backends:
            out.append({
                "id": b.id, "longname": b.longname, "shortname": b.id[-4:],
                "lat": None, "lon": None, "alt": None,
                "sent": state.sent_per_node.get(b.id, 0), "is_rogue": False,
                "topic": None, "board_connected": b.connected,
                "kind": "serial", "port": b.port,
            })
        return out

    # ── Emit a single payload (publish + counters + ws broadcast) ─────────────

    async def _emit(node: VirtualNode, payload: dict) -> None:
        if state.proxy_injector is None:
            return
        state.proxy_injector.publish(node, payload)
        if state.recorder is not None:
            state.recorder.record(node, payload)
        state.sent_per_node[node.id] = state.sent_per_node.get(node.id, 0) + 1
        state.total_sent += 1
        ts = time.time()

        await manager.broadcast({
            "type": "node_update",
            "node_id": node.id,
            "sent": state.sent_per_node[node.id],
            "lat": round(node.lat, 6),
            "lon": round(node.lon, 6),
            "total_sent": state.total_sent,
        })

        ptype = payload.get("type")
        if ptype == "sendtext":
            await manager.broadcast({
                "type": "log", "level": "text",
                "node": node.longname, "node_id": node.id,
                "text": str(payload.get("payload", "")), "ts": ts,
            })
        elif ptype == "sendposition":
            await manager.broadcast({
                "type": "log", "level": "position",
                "node": node.longname, "node_id": node.id,
                "lat": round(node.lat, 6), "lon": round(node.lon, 6),
                "ts": ts,
            })
        elif ptype == "telemetry":
            metrics = payload.get("payload", {})
            await manager.broadcast({
                "type": "log", "level": "telemetry",
                "node": node.longname, "node_id": node.id,
                "battery": metrics.get("battery_level"),
                "voltage": metrics.get("voltage"),
                "ts": ts,
            })

    # ── Per-node loop ─────────────────────────────────────────────────────────

    async def _node_loop(node: VirtualNode) -> None:
        """One independent scheduler per node; gives visibly distinct cadences."""
        # stagger initial start so nodes don't all fire in lockstep
        await asyncio.sleep(random.uniform(0, 4.0))
        while state.running:
            profile = state.scenarios.get(state.active_scenario)
            if profile is None:
                await asyncio.sleep(1.0)
                continue

            delta = (random.random() * 2 - 1) * profile.jitter_pct
            sleep_s = max(0.2, profile.interval_s * (1.0 + delta))

            try:
                await asyncio.sleep(sleep_s)
            except asyncio.CancelledError:
                return

            if not state.running:
                return
            if state.paused:
                continue

            profile = state.scenarios.get(state.active_scenario)
            if profile is None:
                continue

            try:
                if profile.kind == "position":
                    await _emit(node, node.position_payload())
                elif profile.kind == "chat":
                    for _ in range(profile.burst_size):
                        text = random.choice(_CHAT_VOCAB)
                        await _emit(node, node.text_payload(text))
                        if profile.burst_size > 1:
                            await asyncio.sleep(0.08)
                elif profile.kind == "walk":
                    node.step(
                        speed_kmh=3.6,
                        heading_deg=random.randint(0, 359),
                        interval_s=profile.interval_s,
                    )
                    await _emit(node, node.position_payload())
                elif profile.kind == "burst_chat":
                    for i in range(profile.burst_size):
                        text = f"burst#{state.total_sent + 1}"
                        await _emit(node, node.text_payload(text))
                        await asyncio.sleep(0.05)
                elif profile.kind == "telemetry":
                    await _emit(node, node.telemetry_payload(**_telemetry_metrics()))
            except Exception as exc:  # pragma: no cover
                print(f"[_node_loop] {node.id} error: {exc}")

            await manager.broadcast({"type": "status", **_status_dict()})

    async def _cancel_tasks() -> None:
        for t in state._node_tasks:
            if not t.done():
                t.cancel()
        for t in state._node_tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        state._node_tasks = []

    # ── Serial RX bridge ───────────────────────────────────────────────────────

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

    # ── routes ─────────────────────────────────────────────────────────────────

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

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse((_STATIC / "index.html").read_text())

    @app.get("/api/status")
    async def get_status() -> dict:
        return _status_dict()

    @app.get("/api/nodes")
    async def get_nodes() -> list:
        return _node_list()

    @app.get("/api/boards")
    async def get_boards() -> list:
        return [
            {"node_id": ni.node.id, "topic": ni.topic, "connected": ni.connected}
            for ni in state.node_injectors
        ]

    @app.get("/api/zones")
    async def get_zones() -> list:
        return [
            {"name": name, "lat": z.center_lat, "lon": z.center_lon, "radius": z.radius_km}
            for name, z in ITALY_PRESETS.items()
        ]

    @app.post("/api/start")
    async def start() -> dict:
        if state.running and not state.paused:
            return {"ok": False, "reason": "already running"}

        if state.paused:
            state.paused = False
            await manager.broadcast({"type": "status", **_status_dict()})
            return {"ok": True, "action": "resumed"}

        state.node_injectors = [NodeInjector(n, state.cfg) for n in state.nodes]
        state.proxy_injector = _ProxyInjector(state.node_injectors)
        state.sent_per_node = {n.id: 0 for n in state.nodes}
        state.total_sent = 0
        state.backends = [VirtualBackend(n, state.cfg) for n in state.nodes]
        state.backend_by_id = {b.id: b for b in state.backends}

        try:
            state.proxy_injector.connect()
            state.mqtt_connected = True
        except Exception as exc:
            return {"ok": False, "reason": f"MQTT connect failed: {exc}"}

        # Announce initial positions
        for n in state.nodes:
            await _emit(n, n.position_payload())

        state.running = True
        state._start_time = time.time()
        state._node_tasks = [
            asyncio.create_task(_node_loop(n)) for n in state.nodes
        ]

        await manager.broadcast({"type": "status", **_status_dict()})
        await manager.broadcast({"type": "nodes_snapshot", "nodes": _node_list()})
        return {"ok": True, "boards": len(state.node_injectors)}

    @app.post("/api/pause")
    async def pause() -> dict:
        if not state.running:
            return {"ok": False, "reason": "not running"}
        state.paused = not state.paused
        await manager.broadcast({"type": "status", **_status_dict()})
        return {"ok": True, "paused": state.paused}

    @app.post("/api/stop")
    async def stop() -> dict:
        state.running = False
        state.paused = False
        await _cancel_tasks()
        if state.proxy_injector:
            state.proxy_injector.disconnect()
            state.mqtt_connected = False
        await manager.broadcast({"type": "status", **_status_dict()})
        return {"ok": True}

    @app.post("/api/scenario/{name}")
    async def set_scenario(name: str) -> dict:
        if name not in state.scenarios:
            return {"ok": False, "reason": f"unknown scenario; valid: {sorted(state.scenarios)}"}
        state.active_scenario = name
        await manager.broadcast({"type": "status", **_status_dict()})
        return {"ok": True, "scenario": name}

    @app.post("/api/config/scenario/{name}")
    async def config_scenario(name: str, body: ScenarioProfileBody) -> dict:
        if name not in state.scenarios:
            return {"ok": False, "reason": f"unknown scenario; valid: {sorted(state.scenarios)}"}
        prof = state.scenarios[name]
        if body.interval_s is not None:
            prof.interval_s = body.interval_s
        if body.jitter_pct is not None:
            prof.jitter_pct = body.jitter_pct
        if body.burst_size is not None:
            prof.burst_size = body.burst_size
        await manager.broadcast({"type": "status", **_status_dict()})
        return {"ok": True, "scenario": name, "profile": asdict(prof)}

    @app.post("/api/config/nodes")
    async def config_node_count(body: NodeCountBody) -> dict:
        if state.running:
            return {"ok": False, "reason": "stop traffic first"}
        state.cfg.nodes.count = body.count
        state.rebuild_nodes()
        await manager.broadcast({"type": "nodes_snapshot", "nodes": _node_list()})
        await manager.broadcast({"type": "status", **_status_dict()})
        return {"ok": True, "count": body.count}

    @app.post("/api/zone/custom")
    async def set_zone_custom(body: CustomZoneBody) -> dict:
        if state.running:
            return {"ok": False, "reason": "stop traffic first"}
        state.cfg.zone = ZoneConfig(
            name=body.name or "Custom",
            center_lat=body.lat,
            center_lon=body.lon,
            radius_km=body.radius_km,
        )
        state.rebuild_nodes()
        await manager.broadcast({"type": "nodes_snapshot", "nodes": _node_list()})
        await manager.broadcast({"type": "status", **_status_dict()})
        return {"ok": True, "zone": body.name}

    @app.post("/api/zone/{name}")
    async def set_zone(name: str) -> dict:
        if name not in ITALY_PRESETS:
            return {"ok": False, "reason": f"unknown zone; valid: {list(ITALY_PRESETS)}"}
        if state.running:
            return {"ok": False, "reason": "stop traffic first"}
        state.cfg.zone = ITALY_PRESETS[name]
        state.rebuild_nodes()
        await manager.broadcast({"type": "nodes_snapshot", "nodes": _node_list()})
        await manager.broadcast({"type": "status", **_status_dict()})
        return {"ok": True, "zone": name}

    async def _after_tx(node_id: str, b: NodeBackend, payload: dict) -> None:
        state.total_sent += 1
        state.sent_per_node[node_id] = state.sent_per_node.get(node_id, 0) + 1
        await manager.broadcast({
            "type": "log", "level": "tx", "node": b.longname, "node_id": node_id,
            "ptype": payload.get("type"), "payload": payload.get("payload"),
            "ts": time.time(),
        })

    @app.post("/api/nodes/{node_id}/send")
    async def manual_send(node_id: str, body: SendBody) -> dict:
        b = state.backend_by_id.get(node_id)
        if b is None:
            return {"ok": False, "reason": "node not found"}
        if not b.connected:
            try:
                b.connect()
            except Exception as exc:
                return {"ok": False, "reason": f"connect failed: {exc}"}
        try:
            if body.type == "text":
                payload = b.send_text(body.text or "", to=body.to, channel=body.channel)
            elif body.type == "position":
                payload = b.send_position()
            else:
                payload = b.send_telemetry()
        except Exception as exc:
            return {"ok": False, "reason": f"send failed: {exc}"}
        await _after_tx(node_id, b, payload)
        return {"ok": True, "sent": payload}

    @app.patch("/api/nodes/{node_id}")
    async def patch_node(node_id: str, body: NodePatchBody) -> dict:
        target = next((n for n in state.nodes if n.id == node_id), None)
        if target is None:
            return {"ok": False, "reason": "node not found"}
        if body.longname is not None:
            target.longname = body.longname
        if body.shortname is not None:
            target.shortname = body.shortname
        if body.lat is not None:
            target.lat = body.lat
        if body.lon is not None:
            target.lon = body.lon
        if body.alt is not None:
            target.alt = body.alt
        if body.is_rogue is not None:
            target.is_rogue = body.is_rogue
        await manager.broadcast({"type": "nodes_snapshot", "nodes": _node_list()})
        return {"ok": True, "node_id": node_id}

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await manager.connect(ws)
        await ws.send_json({"type": "status", **_status_dict()})
        await ws.send_json({"type": "nodes_snapshot", "nodes": _node_list()})
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(ws)

    return app
