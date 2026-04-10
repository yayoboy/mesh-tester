from unittest.mock import MagicMock, patch
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


# ── existing tests (unchanged) ─────────────────────────────────────────────────

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
    gen.announce_nodes()
    assert gen.total_sent == 2
    gen.send_text_round()
    assert gen.total_sent == 4
    gen.send_position_round()
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


# ── Task D: new scenarios ──────────────────────────────────────────────────────

def test_idle_round_publishes_position_per_node():
    gen = TrafficGenerator(make_injector(), make_nodes())
    gen.idle_round()
    assert gen.total_sent == len(gen.nodes)
    for call in gen._injector.publish.call_args_list:
        assert call[0][1]["type"] == "sendposition"


def test_chat_round_publishes_text_per_node():
    gen = TrafficGenerator(make_injector(), make_nodes())
    gen.chat_round(vocabulary=["ciao", "hello", "test"])
    assert gen.total_sent == len(gen.nodes)
    for call in gen._injector.publish.call_args_list:
        assert call[0][1]["type"] == "sendtext"
        assert call[0][1]["payload"] in ["ciao", "hello", "test"]


def test_walk_round_moves_nodes_and_publishes_position():
    nodes = make_nodes()
    lat0 = [n.lat for n in nodes]
    gen = TrafficGenerator(make_injector(), nodes)
    gen.walk_round(speed_kmh=3.6, heading_deg=0)
    assert gen.total_sent == len(nodes)
    # nodes should have moved north
    for node, old_lat in zip(gen.nodes, lat0):
        assert node.lat > old_lat


def test_burst_round_publishes_n_texts_per_node():
    gen = TrafficGenerator(make_injector(), make_nodes())
    gen.burst_round(count=3)
    assert gen.total_sent == len(gen.nodes) * 3


def test_delay_jitter_accepted_without_error():
    gen = TrafficGenerator(make_injector(), make_nodes())
    # jitter is respected by the generator; we just check it doesn't raise
    gen.send_text_round(msg_prefix="jitter", delay_jitter_ms=0)
    assert gen.total_sent == len(gen.nodes)
