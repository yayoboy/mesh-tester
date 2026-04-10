import pytest
from src.virtual_node import VirtualNode
from src.config import AppConfig, MqttConfig
from src.tui.app import MeshTesterApp
from src.tui.widgets.node_table import NodeTable


# ── dry_run output ─────────────────────────────────────────────────────────────

def test_dry_run_prints_broker_and_topic(capsys):
    from main import dry_run, _make_nodes
    cfg = AppConfig()
    cfg.mqtt.broker = "testbroker"
    cfg.mqtt.gateway_ids = ["!aabbccdd"]
    nodes = _make_nodes(cfg)
    dry_run(cfg, nodes)
    out = capsys.readouterr().out
    assert "testbroker" in out
    assert "!aabbccdd" in out
    assert "msh/EU_868/2/json/LongFast/!aabbccdd" in out
    assert f"nodes ({cfg.nodes.count})" in out


# ── app wires nodes into NodeTable on mount ────────────────────────────────────

async def test_app_with_nodes_populates_node_table():
    nodes = [
        VirtualNode(id="!11111111", longname="Alpha", shortname="A",
                    lat=45.0, lon=9.0, alt=100),
        VirtualNode(id="!22222222", longname="Beta", shortname="B",
                    lat=45.1, lon=9.1, alt=110),
    ]
    async with MeshTesterApp(nodes=nodes).run_test() as pilot:
        table = pilot.app.query_one(NodeTable)
        assert table.row_count == 2
