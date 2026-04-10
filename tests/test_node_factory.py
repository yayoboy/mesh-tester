import pytest
from src.config import AppConfig, ZoneConfig, NodePoolConfig
from src.node_factory import NodeFactory
from src.zone import ITALY_PRESETS


def test_factory_generate_returns_correct_count():
    cfg = AppConfig()
    cfg.nodes.count = 6
    factory = NodeFactory(cfg.zone, cfg.nodes)
    nodes = factory.generate()
    assert len(nodes) == 6


def test_factory_ids_are_unique():
    cfg = AppConfig()
    cfg.nodes.count = 10
    factory = NodeFactory(cfg.zone, cfg.nodes)
    nodes = factory.generate()
    ids = [n.id for n in nodes]
    assert len(ids) == len(set(ids))


def test_factory_ids_start_with_bang():
    factory = NodeFactory(ITALY_PRESETS["Milano"], NodePoolConfig(count=3))
    for node in factory.generate():
        assert node.id.startswith("!")
        assert len(node.id) == 9  # ! + 8 hex chars


def test_factory_longname_contains_prefix():
    pool = NodePoolConfig(count=4, prefix="MIL")
    factory = NodeFactory(ITALY_PRESETS["Milano"], pool)
    for node in factory.generate():
        assert "MIL" in node.longname


def test_factory_same_seed_same_nodes():
    zone = ITALY_PRESETS["Roma"]
    pool = NodePoolConfig(count=5, prefix="ROM")
    a = NodeFactory(zone, pool, seed=7).generate()
    b = NodeFactory(zone, pool, seed=7).generate()
    assert [n.id for n in a] == [n.id for n in b]
    assert [round(n.lat, 6) for n in a] == [round(n.lat, 6) for n in b]


def test_factory_different_seeds_different_positions():
    zone = ITALY_PRESETS["Napoli"]
    pool = NodePoolConfig(count=5)
    a = NodeFactory(zone, pool, seed=1).generate()
    b = NodeFactory(zone, pool, seed=2).generate()
    assert [n.lat for n in a] != [n.lat for n in b]
