"""Web API tests — FastAPI TestClient (no real MQTT broker needed)."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import AppConfig
from src.web.app import ConnectionManager, MeshState, _ProxyInjector, create_app


def make_client(cfg: AppConfig | None = None) -> TestClient:
    if cfg is None:
        cfg = AppConfig()
        cfg.nodes.count = 3  # small set for speed
    return TestClient(create_app(cfg))


# ── Dashboard HTML ─────────────────────────────────────────────────────────────

def test_dashboard_returns_html():
    client = make_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Mesh Tester" in resp.text
    assert "Alpine" in resp.text or "alpinejs" in resp.text


# ── /api/status ────────────────────────────────────────────────────────────────

def test_status_initial_state():
    client = make_client()
    data = client.get("/api/status").json()
    assert data["running"] is False
    assert data["mqtt_connected"] is False
    assert data["total_sent"] == 0
    assert data["scenario"] == "idle"
    assert "zone" in data
    assert "node_count" in data


# ── /api/nodes ─────────────────────────────────────────────────────────────────

def test_nodes_returns_list_with_required_fields():
    client = make_client()
    nodes = client.get("/api/nodes").json()
    assert isinstance(nodes, list)
    assert len(nodes) == 3
    n = nodes[0]
    for field in ("id", "longname", "shortname", "lat", "lon", "alt", "sent", "is_rogue"):
        assert field in n, f"missing field: {field}"


def test_nodes_have_topic_field():
    """Each node exposes its dedicated MQTT topic (multi-board mode)."""
    client = make_client()
    nodes = client.get("/api/nodes").json()
    # topic is None when not yet started (no injectors built)
    for n in nodes:
        assert "topic" in n


# ── /api/zones ────────────────────────────────────────────────────────────────

def test_zones_returns_italy_presets():
    client = make_client()
    zones = client.get("/api/zones").json()
    names = [z["name"] for z in zones]
    assert "Milano" in names
    assert "Roma" in names


# ── /api/scenario ─────────────────────────────────────────────────────────────

def test_set_valid_scenario():
    client = make_client()
    resp = client.post("/api/scenario/chat")
    assert resp.json() == {"ok": True, "scenario": "chat"}
    assert client.get("/api/status").json()["scenario"] == "chat"


def test_set_invalid_scenario():
    client = make_client()
    resp = client.post("/api/scenario/teleport")
    assert resp.json()["ok"] is False
    assert "reason" in resp.json()


# ── /api/zone ─────────────────────────────────────────────────────────────────

def test_set_valid_zone_rebuilds_nodes():
    client = make_client()
    old_nodes = client.get("/api/nodes").json()
    resp = client.post("/api/zone/Roma")
    assert resp.json()["ok"] is True
    new_nodes = client.get("/api/nodes").json()
    # Positions should differ (different zone)
    assert old_nodes[0]["lat"] != new_nodes[0]["lat"]


def test_set_invalid_zone():
    client = make_client()
    resp = client.post("/api/zone/Atlantide")
    assert resp.json()["ok"] is False


# ── /api/stop ─────────────────────────────────────────────────────────────────

def test_stop_when_not_running():
    client = make_client()
    resp = client.post("/api/stop")
    assert resp.json()["ok"] is True


def test_pause_when_not_running():
    client = make_client()
    resp = client.post("/api/pause")
    assert resp.json()["ok"] is False  # "not running"


# ── /api/start (mocked MQTT) ──────────────────────────────────────────────────

@patch("src.mqtt_injector.mqtt.Client")
def test_start_connects_mqtt_and_returns_ok(mock_client_cls):
    mock_client_cls.return_value = MagicMock()
    client = make_client()
    resp = client.post("/api/start")
    data = resp.json()
    assert data["ok"] is True
    assert "boards" in data          # multi-board: N injectors created
    assert data["boards"] == 3       # matches cfg.nodes.count
    # Status should reflect running
    status = client.get("/api/status").json()
    assert status["running"] is True
    assert status["mqtt_connected"] is True
    # Clean up
    client.post("/api/stop")


@patch("src.mqtt_injector.mqtt.Client")
def test_start_twice_returns_already_running(mock_client_cls):
    mock_client_cls.return_value = MagicMock()
    client = make_client()
    client.post("/api/start")
    resp = client.post("/api/start")
    assert resp.json()["ok"] is False
    client.post("/api/stop")


# ── /api/boards ───────────────────────────────────────────────────────────────

def test_boards_endpoint_exists():
    client = make_client()
    resp = client.get("/api/boards")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── WebSocket initial snapshot ─────────────────────────────────────────────────

def test_websocket_sends_status_then_nodes_snapshot():
    client = make_client()
    with client.websocket_connect("/ws") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "status"
        assert "running" in msg1
        msg2 = ws.receive_json()
        assert msg2["type"] == "nodes_snapshot"
        assert isinstance(msg2["nodes"], list)


# ── ConnectionManager unit ────────────────────────────────────────────────────

def test_connection_manager_disconnect_idempotent():
    mgr = ConnectionManager()
    fake_ws = MagicMock()
    mgr.disconnect(fake_ws)  # should not raise even if not in list


# ── Telemetry scenario ─────────────────────────────────────────────────────────

def test_telemetry_scenario_available():
    client = make_client()
    scenarios = client.get("/api/status").json()["scenarios"]
    assert "telemetry" in scenarios
    resp = client.post("/api/scenario/telemetry")
    assert resp.json() == {"ok": True, "scenario": "telemetry"}


def test_telemetry_metrics_within_plausible_range():
    from src.web.app import _telemetry_metrics
    for _ in range(20):
        m = _telemetry_metrics()
        assert 20 <= m["battery_level"] <= 100
        assert 3.2 <= m["voltage"] <= 4.2
        assert {"battery_level", "voltage", "snr", "rssi"} <= set(m)


# ── Recorder wiring ────────────────────────────────────────────────────────────

@patch("src.mqtt_injector.mqtt.Client")
def test_recorder_writes_session_when_enabled(mock_client_cls, tmp_path):
    """With log_to_file=True, the initial position announce is recorded to JSONL."""
    mock_client_cls.return_value = MagicMock()
    cfg = AppConfig()
    cfg.nodes.count = 3
    cfg.log_to_file = True
    cfg.log_path = str(tmp_path / "logs" / "session.jsonl")

    client = TestClient(create_app(cfg))
    client.post("/api/start")
    client.post("/api/stop")

    log_file = Path(cfg.log_path)
    assert log_file.exists()
    lines = log_file.read_text().splitlines()
    assert len(lines) >= 3  # >= one position announce per node
    entry = json.loads(lines[0])
    assert entry["type"] == "sendposition"
    assert "payload" in entry and "node_id" in entry


def test_recorder_disabled_by_default():
    """No recorder is created unless log_to_file is set."""
    state = MeshState(AppConfig())
    assert state.recorder is None


# ── _ProxyInjector unit ────────────────────────────────────────────────────────

def test_proxy_injector_topic_from_first_node():
    from src.web.app import NodeInjector
    from src.virtual_node import VirtualNode
    cfg = AppConfig()

    node = VirtualNode(id="!aabbccdd", longname="Test", shortname="T",
                       lat=0.0, lon=0.0, alt=0)
    with patch("src.mqtt_injector.mqtt.Client"):
        ni = NodeInjector(node, cfg)
        proxy = _ProxyInjector([ni])
    assert "!aabbccdd" in proxy.topic


def test_nodes_report_kind_virtual():
    client = make_client()
    nodes = client.get("/api/nodes").json()
    assert all(n["kind"] == "virtual" for n in nodes)
    assert all("port" in n for n in nodes)
