import pytest
from textual.app import App, ComposeResult

from src.tui.widgets.node_table import NodeTable
from src.tui.widgets.message_log import MessageLog
from src.virtual_node import VirtualNode


# ── helpers ────────────────────────────────────────────────────────────────────

def make_node(suffix="1", lat=45.4629, lon=9.1910, alt=122) -> VirtualNode:
    hex_id = suffix * 8
    return VirtualNode(
        id=f"!{hex_id}",
        longname=f"Node-{suffix}",
        shortname=suffix.upper(),
        lat=lat,
        lon=lon,
        alt=alt,
    )


class NodeTableApp(App):
    def compose(self) -> ComposeResult:
        yield NodeTable()


class MessageLogApp(App):
    def compose(self) -> ComposeResult:
        yield MessageLog()


# ── NodeTable tests ────────────────────────────────────────────────────────────

async def test_node_table_has_six_columns():
    async with NodeTableApp().run_test() as pilot:
        table = pilot.app.query_one(NodeTable)
        assert len(table.ordered_columns) == 6


async def test_add_node_increments_row_count():
    async with NodeTableApp().run_test() as pilot:
        table = pilot.app.query_one(NodeTable)
        assert table.row_count == 0
        table.add_node(make_node("1"))
        assert table.row_count == 1


async def test_add_two_nodes_shows_two_rows():
    async with NodeTableApp().run_test() as pilot:
        table = pilot.app.query_one(NodeTable)
        table.add_node(make_node("1"))
        table.add_node(make_node("2"))
        assert table.row_count == 2


async def test_update_sent_changes_cell_value():
    async with NodeTableApp().run_test() as pilot:
        table = pilot.app.query_one(NodeTable)
        node = make_node("a")
        table.add_node(node)
        assert table.get_cell(node.id, "sent") == "0"
        table.update_sent(node.id, 42)
        assert table.get_cell(node.id, "sent") == "42"


# ── MessageLog tests ───────────────────────────────────────────────────────────

async def test_log_text_appends_entry():
    async with MessageLogApp().run_test() as pilot:
        log = pilot.app.query_one(MessageLog)
        assert len(log.entries) == 0
        log.log_text(make_node("1"), "hello mesh")
        assert len(log.entries) == 1


async def test_log_position_appends_entry():
    async with MessageLogApp().run_test() as pilot:
        log = pilot.app.query_one(MessageLog)
        log.log_position(make_node("2"))
        assert len(log.entries) == 1


async def test_log_text_entry_has_correct_type_and_node():
    async with MessageLogApp().run_test() as pilot:
        log = pilot.app.query_one(MessageLog)
        node = make_node("b")
        log.log_text(node, "test message")
        entry = log.entries[0]
        assert entry["type"] == "text"
        assert entry["node_id"] == node.id
        assert entry["text"] == "test message"


async def test_log_position_entry_has_correct_coords():
    async with MessageLogApp().run_test() as pilot:
        log = pilot.app.query_one(MessageLog)
        node = make_node("c", lat=45.4629, lon=9.1910, alt=200)
        log.log_position(node)
        entry = log.entries[0]
        assert entry["type"] == "position"
        assert entry["node_id"] == node.id
        assert entry["lat"] == node.lat
        assert entry["alt"] == 200
