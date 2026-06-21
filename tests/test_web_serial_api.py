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
