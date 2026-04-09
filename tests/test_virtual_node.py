from src.virtual_node import VirtualNode

def test_create_virtual_node():
    node = VirtualNode(
        id="!11111111", longname="VNode-Alpha", shortname="VA",
        lat=45.4642, lon=9.1900, alt=120,
    )
    assert node.id == "!11111111"
    assert node.longname == "VNode-Alpha"

def test_node_id_decimal():
    node = VirtualNode(
        id="!11111111", longname="Test", shortname="T",
        lat=0.0, lon=0.0, alt=0,
    )
    assert node.id_decimal == 0x11111111

def test_lat_lon_integer_format():
    node = VirtualNode(
        id="!11111111", longname="Test", shortname="T",
        lat=45.4642, lon=9.1900, alt=120,
    )
    assert node.latitude_i == 454642000
    assert node.longitude_i == 91900000

def test_create_from_config():
    cfg = {"id": "!11111111", "longname": "VNode-Alpha", "shortname": "VA",
           "lat": 45.4642, "lon": 9.1900, "alt": 120}
    node = VirtualNode.from_config(cfg)
    assert node.id == "!11111111"
    assert node.longname == "VNode-Alpha"

def test_mqtt_text_payload():
    node = VirtualNode(
        id="!11111111", longname="Test", shortname="T",
        lat=0.0, lon=0.0, alt=0,
    )
    payload = node.text_payload("hello mesh")
    assert payload == {"from": 0x11111111, "type": "sendtext", "payload": "hello mesh"}

def test_mqtt_position_payload():
    node = VirtualNode(
        id="!11111111", longname="Test", shortname="T",
        lat=45.4642, lon=9.1900, alt=120,
    )
    payload = node.position_payload()
    assert payload["from"] == 0x11111111
    assert payload["type"] == "sendposition"
    assert payload["payload"]["latitude_i"] == 454642000
    assert payload["payload"]["longitude_i"] == 91900000
    assert payload["payload"]["altitude"] == 120

def test_mqtt_dm_payload():
    node = VirtualNode(
        id="!11111111", longname="Test", shortname="T",
        lat=0.0, lon=0.0, alt=0,
    )
    payload = node.text_payload("hello", to_node_id="!aabbccdd")
    assert payload["to"] == 0xAABBCCDD
