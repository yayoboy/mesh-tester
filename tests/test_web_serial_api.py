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


def test_manual_send_from_virtual_node_after_start():
    from unittest.mock import MagicMock, patch
    with patch("src.mqtt_injector.mqtt.Client") as mock_mqtt_cls:
        mock_client = MagicMock()
        mock_mqtt_cls.return_value = mock_client
        mock_client.connect.return_value = None
        mock_client.loop_start.return_value = None
        mock_client.publish.return_value = MagicMock(rc=0)
        client = make_client()
        client.post("/api/start")
        nodes = client.get("/api/nodes").json()
        virtual_node = next(n for n in nodes if n["kind"] == "virtual")
        nid = virtual_node["id"]
        resp = client.post(f"/api/nodes/{nid}/send", json={"type": "text", "text": "hi"})
        assert resp.json()["ok"] is True
