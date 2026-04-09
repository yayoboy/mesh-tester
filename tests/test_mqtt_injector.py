import json
from unittest.mock import MagicMock, patch
from src.mqtt_injector import MqttInjector
from src.virtual_node import VirtualNode

@patch("src.mqtt_injector.mqtt.Client")
def test_connect(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    injector = MqttInjector(broker="localhost", port=1883,
                            topic_root="msh/EU_868/2", channel="LongFast",
                            gateway_id="!aabbccdd")
    injector.connect()
    mock_client.connect.assert_called_once_with("localhost", 1883, keepalive=60)
    mock_client.loop_start.assert_called_once()

@patch("src.mqtt_injector.mqtt.Client")
def test_disconnect(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    injector = MqttInjector(broker="localhost", port=1883,
                            topic_root="msh/EU_868/2", channel="LongFast",
                            gateway_id="!aabbccdd")
    injector.connect()
    injector.disconnect()
    mock_client.loop_stop.assert_called_once()
    mock_client.disconnect.assert_called_once()

@patch("src.mqtt_injector.mqtt.Client")
def test_publish_text(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    injector = MqttInjector(broker="localhost", port=1883,
                            topic_root="msh/EU_868/2", channel="LongFast",
                            gateway_id="!aabbccdd")
    injector.connect()
    node = VirtualNode(id="!11111111", longname="Test", shortname="T",
                       lat=0.0, lon=0.0, alt=0)
    injector.publish(node, node.text_payload("hello"))
    expected_topic = "msh/EU_868/2/json/LongFast/!aabbccdd"
    expected_payload = json.dumps({"from": 0x11111111, "type": "sendtext", "payload": "hello"})
    mock_client.publish.assert_called_once_with(expected_topic, expected_payload)

@patch("src.mqtt_injector.mqtt.Client")
def test_topic_format(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    injector = MqttInjector(broker="192.168.1.100", port=1884,
                            topic_root="msh/US/2", channel="MyChannel",
                            gateway_id="!deadbeef")
    assert injector.topic == "msh/US/2/json/MyChannel/!deadbeef"
