from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.config import AppConfig, load_config
from src.mqtt_injector import MqttInjector
from src.node_factory import NodeFactory
from src.traffic_generator import TrafficGenerator
from src.virtual_node import VirtualNode
from src.zone import ITALY_PRESETS

_STATIC = Path(__file__).parent / "static"
_CHAT_VOCAB = ["ciao", "hello", "ack", "ok", "test", "ping", "here", "on air"]


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
    """Wraps a dedicated MqttInjector for a single virtual node (multi-board mode).

    In multi-board mode each VirtualNode publishes via its own gateway topic
    (topic_root/json/channel/<node.id>), so the mesh sees it as a separate board.
    """

    def __init__(self, node: VirtualNode, cfg: AppConfig) -> None:
        self._node = node
        self._inj = MqttInjector(
            broker=cfg.mqtt.broker,
            port=cfg.mqtt.port,
            topic_root=cfg.mqtt.topic_root,
            channel=cfg.mqtt.channel,
            gateway_id=node.id,           # ← node ID used as gateway ID
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


# ── Runtime state ──────────────────────────────────────────────────────────────

class MeshState:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.nodes: list[VirtualNode] = NodeFactory(
            cfg.zone, cfg.nodes, seed=42
        ).generate()
        # One injector per node (multi-board mode)
        self.node_injectors: list[NodeInjector] = []
        # Single TrafficGenerator uses a "proxy" injector
        self.proxy_injector: Optional[_ProxyInjector] = None
        self.generator: Optional[TrafficGenerator] = None
        self.running: bool = False
        self.paused: bool = False
        self.mqtt_connected: bool = False
        self.active_scenario: str = "idle"
        self.sent_per_node: dict[str, int] = {}
        self._start_time: float = 0.0
        self._loop_task: Optional[asyncio.Task] = None

    def rebuild_nodes(self) -> None:
        """Regenerate nodes from current config (e.g. after zone change)."""
        self.nodes = NodeFactory(self.cfg.zone, self.cfg.nodes, seed=42).generate()
        self.sent_per_node = {}

    def board_info(self) -> list[dict]:
        """Return per-node board info (id, topic, connected)."""
        return [
            {
                "node_id": ni.node.id,
                "topic": ni.topic,
                "connected": ni.connected,
            }
            for ni in self.node_injectors
        ]


# ── Proxy injector: dispatches publish to per-node injector ───────────────────

class _ProxyInjector:
    """Looks like MqttInjector to TrafficGenerator but routes each publish
    to the NodeInjector that owns that node."""

    def __init__(self, node_injectors: list[NodeInjector]) -> None:
        self._map = {ni.node.id: ni for ni in node_injectors}
        # topic is the first node's topic (satisfies TrafficGenerator.topic attr)
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
            "total_sent": state.generator.total_sent if state.generator else 0,
            "uptime": elapsed,
            "zone": state.cfg.zone.name,
            "node_count": len(state.nodes),
        }

    def _node_list() -> list[dict]:
        board_map = {ni.node.id: ni for ni in state.node_injectors}
        return [
            {
                "id": n.id,
                "longname": n.longname,
                "shortname": n.shortname,
                "lat": round(n.lat, 6),
                "lon": round(n.lon, 6),
                "alt": n.alt,
                "sent": state.sent_per_node.get(n.id, 0),
                "is_rogue": n.is_rogue,
                "topic": board_map[n.id].topic if n.id in board_map else None,
                "board_connected": board_map[n.id].connected if n.id in board_map else False,
            }
            for n in state.nodes
        ]

    # ── on_send callback ───────────────────────────────────────────────────────

    def _on_send(node: VirtualNode, payload: dict, topic: str) -> None:
        state.sent_per_node[node.id] = state.sent_per_node.get(node.id, 0) + 1
        ts = time.time()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        loop.create_task(manager.broadcast({
            "type": "node_update",
            "node_id": node.id,
            "sent": state.sent_per_node[node.id],
            "lat": round(node.lat, 6),
            "lon": round(node.lon, 6),
        }))

        ptype = payload.get("type")
        if ptype == "sendtext":
            loop.create_task(manager.broadcast({
                "type": "log",
                "level": "text",
                "node": node.longname,
                "node_id": node.id,
                "text": str(payload.get("payload", "")),
                "ts": ts,
            }))
        elif ptype == "sendposition":
            loop.create_task(manager.broadcast({
                "type": "log",
                "level": "position",
                "node": node.longname,
                "node_id": node.id,
                "lat": round(node.lat, 6),
                "lon": round(node.lon, 6),
                "ts": ts,
            }))

    # ── traffic loop ───────────────────────────────────────────────────────────

    async def _traffic_loop() -> None:
        while state.running:
            if not state.paused and state.generator:
                scenario = state.active_scenario
                if scenario == "idle":
                    state.generator.idle_round()
                elif scenario == "chat":
                    state.generator.chat_round(vocabulary=_CHAT_VOCAB)
                elif scenario == "walk":
                    state.generator.walk_round(speed_kmh=3.6, heading_deg=0)
                elif scenario == "burst":
                    state.generator.burst_round(count=3)
                else:
                    state.generator.send_text_round(msg_prefix=scenario)

                await manager.broadcast({"type": "status", **_status_dict()})

            await asyncio.sleep(2.0)

    # ── routes ─────────────────────────────────────────────────────────────────

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
        """Return per-node board / gateway info."""
        return state.board_info()

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

        # Build one NodeInjector per virtual node (multi-board)
        state.node_injectors = [NodeInjector(n, state.cfg) for n in state.nodes]
        state.proxy_injector = _ProxyInjector(state.node_injectors)
        state.generator = TrafficGenerator(
            state.proxy_injector, state.nodes, on_send=_on_send
        )

        try:
            state.proxy_injector.connect()
            state.mqtt_connected = True
        except Exception as exc:
            return {"ok": False, "reason": f"MQTT connect failed: {exc}"}

        state.generator.announce_nodes()
        state.running = True
        state._start_time = time.time()
        state._loop_task = asyncio.create_task(_traffic_loop())

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
        if state._loop_task and not state._loop_task.done():
            state._loop_task.cancel()
            state._loop_task = None
        if state.proxy_injector:
            state.proxy_injector.disconnect()
            state.mqtt_connected = False
        await manager.broadcast({"type": "status", **_status_dict()})
        return {"ok": True}

    @app.post("/api/scenario/{name}")
    async def set_scenario(name: str) -> dict:
        valid = {"idle", "chat", "walk", "burst"}
        if name not in valid:
            return {"ok": False, "reason": f"unknown scenario; valid: {sorted(valid)}"}
        state.active_scenario = name
        await manager.broadcast({"type": "status", **_status_dict()})
        return {"ok": True, "scenario": name}

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
