import math
import pytest
from src.config import ZoneConfig, NodePoolConfig
from src.zone import ITALY_PRESETS, scatter_nodes


def test_italy_presets_exist():
    for city in ("Milano", "Roma", "Napoli", "Torino", "Bologna"):
        assert city in ITALY_PRESETS
        zone = ITALY_PRESETS[city]
        assert isinstance(zone, ZoneConfig)


def test_milano_preset_coords():
    z = ITALY_PRESETS["Milano"]
    assert z.center_lat == pytest.approx(45.4654, abs=0.01)
    assert z.center_lon == pytest.approx(9.1859, abs=0.01)
    assert z.radius_km == pytest.approx(5.0)


def test_scatter_nodes_returns_correct_count():
    zone = ITALY_PRESETS["Milano"]
    pool = NodePoolConfig(count=8)
    nodes = scatter_nodes(zone, pool)
    assert len(nodes) == 8


def test_scatter_nodes_stay_within_radius():
    zone = ITALY_PRESETS["Roma"]
    pool = NodePoolConfig(count=20)
    nodes = scatter_nodes(zone, pool)
    for node in nodes:
        # Haversine approx: 1 deg lat ≈ 111 km
        dlat_km = abs(node.lat - zone.center_lat) * 111.0
        dlon_km = abs(node.lon - zone.center_lon) * 111.0 * math.cos(math.radians(zone.center_lat))
        dist_km = math.sqrt(dlat_km**2 + dlon_km**2)
        assert dist_km <= zone.radius_km * 2, f"Node {node.id} too far: {dist_km:.2f} km"


def test_scatter_nodes_altitude_in_range():
    zone = ITALY_PRESETS["Milano"]
    pool = NodePoolConfig(count=10, alt_min=50, alt_max=200)
    nodes = scatter_nodes(zone, pool)
    for node in nodes:
        assert pool.alt_min <= node.alt <= pool.alt_max


def test_scatter_nodes_prefix_in_longname():
    zone = ITALY_PRESETS["Torino"]
    pool = NodePoolConfig(count=3, prefix="TRN")
    nodes = scatter_nodes(zone, pool)
    for node in nodes:
        assert "TRN" in node.longname


def test_scatter_nodes_deterministic_with_same_seed():
    zone = ITALY_PRESETS["Bologna"]
    pool = NodePoolConfig(count=5)
    a = scatter_nodes(zone, pool, seed=99)
    b = scatter_nodes(zone, pool, seed=99)
    assert [n.id for n in a] == [n.id for n in b]
    assert [n.lat for n in a] == [n.lat for n in b]
