import pytest
from src.virtual_node import VirtualNode
from src.tui.app import MeshTesterApp
from src.tui.widgets.node_table import NodeTable


# ── main.py dry-run ────────────────────────────────────────────────────────────

def test_dry_run_prints_topic_and_nodes(capsys):
    from main import dry_run
    cfg = {
        "mqtt": {
            "broker": "localhost",
            "port": 1883,
            "topic_root": "msh/EU_868/2",
            "channel": "LongFast",
        },
        "board_a": {"gateway_id": "!aabbccdd"},
        "virtual_nodes": [
            {
                "id": "!11111111", "longname": "Alpha", "shortname": "A",
                "lat": 45.0, "lon": 9.0, "alt": 100,
            },
        ],
    }
    dry_run(cfg)
    out = capsys.readouterr().out
    assert "!aabbccdd" in out
    assert "!11111111" in out
    assert "msh/EU_868/2/json/LongFast/!aabbccdd" in out


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
