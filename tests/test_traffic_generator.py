from unittest.mock import MagicMock
from src.traffic_generator import TrafficGenerator
from src.virtual_node import VirtualNode


def make_nodes():
    return [
        VirtualNode(id="!11111111", longname="Alpha", shortname="A",
                    lat=45.0, lon=9.0, alt=100),
        VirtualNode(id="!22222222", longname="Beta", shortname="B",
                    lat=45.1, lon=9.1, alt=110),
    ]


def make_injector():
    inj = MagicMock()
    inj.topic = "msh/EU_868/2/json/LongFast/!aabbccdd"
    return inj


def test_announce_nodes_publishes_one_position_per_node():
    nodes = make_nodes()
    inj = make_injector()
    gen = TrafficGenerator(inj, nodes)
    gen.announce_nodes()
    assert inj.publish.call_count == len(nodes)
    for i, node in enumerate(nodes):
        call_args = inj.publish.call_args_list[i]
        assert call_args[0][0] is node
        assert call_args[0][1]["type"] == "sendposition"


def test_send_text_round_publishes_one_text_per_node():
    nodes = make_nodes()
    inj = make_injector()
    gen = TrafficGenerator(inj, nodes)
    gen.send_text_round(msg_prefix="hello")
    assert inj.publish.call_count == len(nodes)
    for i, node in enumerate(nodes):
        call_args = inj.publish.call_args_list[i]
        assert call_args[0][0] is node
        assert call_args[0][1]["type"] == "sendtext"
        assert "hello" in call_args[0][1]["payload"]


def test_send_position_round_publishes_one_position_per_node():
    nodes = make_nodes()
    inj = make_injector()
    gen = TrafficGenerator(inj, nodes)
    gen.send_position_round()
    assert inj.publish.call_count == len(nodes)
    for i, node in enumerate(nodes):
        call_args = inj.publish.call_args_list[i]
        assert call_args[0][0] is node
        assert call_args[0][1]["type"] == "sendposition"


def test_total_sent_counter_increments():
    nodes = make_nodes()
    inj = make_injector()
    gen = TrafficGenerator(inj, nodes)
    assert gen.total_sent == 0
    gen.announce_nodes()        # 2 publishes
    assert gen.total_sent == 2
    gen.send_text_round()       # 2 more
    assert gen.total_sent == 4
    gen.send_position_round()   # 2 more
    assert gen.total_sent == 6


def test_on_send_callback_receives_node_and_payload():
    nodes = make_nodes()
    inj = make_injector()
    callback = MagicMock()
    gen = TrafficGenerator(inj, nodes, on_send=callback)
    gen.announce_nodes()
    assert callback.call_count == len(nodes)
    for i, node in enumerate(nodes):
        call_args = callback.call_args_list[i]
        assert call_args[0][0] is node
        assert call_args[0][1]["type"] == "sendposition"
        assert call_args[0][2] == inj.topic
