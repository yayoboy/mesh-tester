import math
import pytest
from src.virtual_node import VirtualNode


def make_node(**kwargs) -> VirtualNode:
    defaults = dict(id="!11111111", longname="VNode-Alpha", shortname="VA",
                    lat=45.4642, lon=9.1900, alt=120)
    defaults.update(kwargs)
    return VirtualNode(**defaults)


# ── existing tests (unchanged) ─────────────────────────────────────────────────

def test_create_virtual_node():
    node = make_node()
    assert node.id == "!11111111"
    assert node.longname == "VNode-Alpha"

def test_node_id_decimal():
    assert make_node().id_decimal == 0x11111111

def test_lat_lon_integer_format():
    node = make_node()
    assert node.latitude_i == 454642000
    assert node.longitude_i == 91900000

def test_create_from_config():
    cfg = {"id": "!11111111", "longname": "VNode-Alpha", "shortname": "VA",
           "lat": 45.4642, "lon": 9.1900, "alt": 120}
    node = VirtualNode.from_config(cfg)
    assert node.id == "!11111111"
    assert node.longname == "VNode-Alpha"

def test_mqtt_text_payload():
    payload = make_node().text_payload("hello mesh")
    assert payload == {"from": 0x11111111, "type": "sendtext", "payload": "hello mesh"}

def test_mqtt_position_payload():
    payload = make_node().position_payload()
    assert payload["from"] == 0x11111111
    assert payload["type"] == "sendposition"
    assert payload["payload"]["latitude_i"] == 454642000
    assert payload["payload"]["longitude_i"] == 91900000
    assert payload["payload"]["altitude"] == 120

def test_mqtt_dm_payload():
    payload = make_node().text_payload("hello", to_node_id="!aabbccdd")
    assert payload["to"] == 0xAABBCCDD


# ── Task C extensions ──────────────────────────────────────────────────────────

def test_step_moves_position_north():
    node = make_node(lat=45.0, lon=9.0)
    node.step(speed_kmh=3.6, heading_deg=0)   # north, 1 m/s → ~1 m per second
    assert node.lat > 45.0
    assert abs(node.lon - 9.0) < 1e-6        # lon unchanged going north

def test_step_moves_position_east():
    node = make_node(lat=45.0, lon=9.0)
    node.step(speed_kmh=3.6, heading_deg=90)  # east
    assert node.lon > 9.0
    assert abs(node.lat - 45.0) < 1e-6

def test_step_default_interval_one_second():
    node = make_node(lat=45.0, lon=9.0)
    lat0, lon0 = node.lat, node.lon
    node.step(speed_kmh=36.0, heading_deg=0, interval_s=1.0)
    dlat_km = abs(node.lat - lat0) * 111.0
    assert dlat_km == pytest.approx(0.01, rel=0.05)   # 36 km/h for 1 s ≈ 10 m = 0.01 km

def test_telemetry_payload_has_required_fields():
    payload = make_node().telemetry_payload(battery_level=85, voltage=3.9, snr=8.5, rssi=-90)
    assert payload["type"] == "telemetry"
    assert payload["from"] == 0x11111111
    p = payload["payload"]
    assert p["battery_level"] == 85
    assert p["voltage"] == pytest.approx(3.9)
    assert p["snr"] == pytest.approx(8.5)
    assert p["rssi"] == -90

def test_rogue_text_payload_is_malformed():
    node = make_node(is_rogue=True)
    payload = node.text_payload("hello")
    # Rogue payload has a duplicate or invalid 'from' field marker
    assert payload.get("_rogue") is True

def test_non_rogue_text_payload_is_clean():
    node = make_node()
    payload = node.text_payload("hello")
    assert "_rogue" not in payload
