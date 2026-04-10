"""Task G — multi-gateway MqttInjector tests."""
import json
from unittest.mock import MagicMock, patch, call
from src.mqtt_injector import MqttInjector
from src.virtual_node import VirtualNode


def make_node():
    return VirtualNode(id="!11111111", longname="Test", shortname="T",
                       lat=0.0, lon=0.0, alt=0)


@patch("src.mqtt_injector.mqtt.Client")
def test_multi_gateway_publish_sends_to_all_topics(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    injector = MqttInjector(
        broker="localhost", port=1883,
        topic_root="msh/EU_868/2", channel="LongFast",
        gateway_ids=["!aabb0001", "!aabb0002", "!aabb0003"],
    )
    injector.connect()
    node = make_node()
    injector.publish(node, node.text_payload("hi"))

    # publish called once per gateway
    assert mock_client.publish.call_count == 3
    published_topics = {c.args[0] for c in mock_client.publish.call_args_list}
    assert published_topics == {
        "msh/EU_868/2/json/LongFast/!aabb0001",
        "msh/EU_868/2/json/LongFast/!aabb0002",
        "msh/EU_868/2/json/LongFast/!aabb0003",
    }


@patch("src.mqtt_injector.mqtt.Client")
def test_gateway_ids_property(mock_client_cls):
    mock_client_cls.return_value = MagicMock()
    injector = MqttInjector(
        broker="localhost", port=1883,
        topic_root="msh/EU_868/2", channel="LongFast",
        gateway_ids=["!aa", "!bb"],
    )
    assert injector.gateway_ids == ["!aa", "!bb"]


@patch("src.mqtt_injector.mqtt.Client")
def test_topics_property_returns_all(mock_client_cls):
    mock_client_cls.return_value = MagicMock()
    injector = MqttInjector(
        broker="localhost", port=1883,
        topic_root="msh/EU_868/2", channel="LongFast",
        gateway_ids=["!aa", "!bb"],
    )
    assert "msh/EU_868/2/json/LongFast/!aa" in injector.topics
    assert "msh/EU_868/2/json/LongFast/!bb" in injector.topics


@patch("src.mqtt_injector.mqtt.Client")
def test_single_gateway_via_gateway_id_kwarg(mock_client_cls):
    mock_client_cls.return_value = MagicMock()
    injector = MqttInjector(
        broker="localhost", port=1883,
        topic_root="msh/EU_868/2", channel="LongFast",
        gateway_id="!single",
    )
    assert injector.topic == "msh/EU_868/2/json/LongFast/!single"
    assert len(injector.gateway_ids) == 1
