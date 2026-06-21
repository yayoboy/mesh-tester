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


def test_send_text_publishes_text_payload():
    with patch("src.mqtt_injector.mqtt.Client") as cli:
        inst = cli.return_value
        b = VirtualBackend(_node(), AppConfig())
        b.connect()
        payload = b.send_text("hi")
    assert payload["type"] == "sendtext"
    assert payload["payload"] == "hi"
    assert inst.publish.called


def test_send_telemetry_publishes_metrics():
    with patch("src.mqtt_injector.mqtt.Client") as cli:
        inst = cli.return_value
        b = VirtualBackend(_node(), AppConfig())
        b.connect()
        payload = b.send_telemetry()
    assert payload["type"] == "telemetry"
    assert "battery_level" in payload["payload"]
    assert inst.publish.called
