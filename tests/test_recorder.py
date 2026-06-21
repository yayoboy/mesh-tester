import json
import tempfile
import os
from unittest.mock import MagicMock
from src.recorder import Recorder
from src.virtual_node import VirtualNode


def make_node(node_id="!11111111", longname="Alpha", shortname="A"):
    return VirtualNode(id=node_id, longname=longname, shortname=shortname,
                       lat=45.0, lon=9.0, alt=100)


def make_injector():
    inj = MagicMock()
    inj.topic = "msh/EU_868/2/json/LongFast/!aabbccdd"
    return inj


def test_record_writes_jsonl_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        rec = Recorder(path)
        node = make_node()
        payload = node.text_payload("hello")
        rec.record(node, payload)
        with open(path) as fh:
            lines = fh.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["node_id"] == node.id
        assert entry["type"] == "sendtext"
        assert "ts" in entry
    finally:
        os.unlink(path)


def test_record_multiple_events():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        rec = Recorder(path)
        node = make_node()
        rec.record(node, node.text_payload("msg1"))
        rec.record(node, node.position_payload())
        with open(path) as fh:
            lines = fh.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["type"] == "sendtext"
        assert json.loads(lines[1])["type"] == "sendposition"
    finally:
        os.unlink(path)


def test_replay_calls_publish_in_order():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        node = make_node()
        rec = Recorder(path)
        rec.record(node, node.text_payload("first"))
        rec.record(node, node.text_payload("second"))

        inj = make_injector()
        Recorder.replay(path, inj, speed_multiplier=0)  # speed_multiplier=0 skips delays

        assert inj.publish.call_count == 2
        first_payload = inj.publish.call_args_list[0][0][1]
        second_payload = inj.publish.call_args_list[1][0][1]
        assert first_payload["payload"] == "first"
        assert second_payload["payload"] == "second"
    finally:
        os.unlink(path)


def test_recorder_creates_missing_parent_dir(tmp_path):
    """A relative/nested log path works without manual mkdir."""
    path = tmp_path / "logs" / "nested" / "session.jsonl"
    rec = Recorder(str(path))
    rec.record(make_node(), make_node().position_payload())
    assert path.exists()
    assert len(path.read_text().splitlines()) == 1


def test_replay_preserves_node_id():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        node = make_node("!aabbccdd")
        rec = Recorder(path)
        rec.record(node, node.position_payload())

        inj = make_injector()
        Recorder.replay(path, inj, speed_multiplier=0)

        assert inj.publish.call_count == 1
        replayed_node = inj.publish.call_args_list[0][0][0]
        assert replayed_node.id == "!aabbccdd"
    finally:
        os.unlink(path)
