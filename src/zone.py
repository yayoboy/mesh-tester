from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from src.config import NodePoolConfig, ZoneConfig
from src.virtual_node import VirtualNode

if TYPE_CHECKING:
    pass

# ── Italian city presets ───────────────────────────────────────────────────────

ITALY_PRESETS: dict[str, ZoneConfig] = {
    "Milano":  ZoneConfig("Milano",  45.4654,  9.1859, 5.0),
    "Roma":    ZoneConfig("Roma",    41.9028, 12.4964, 5.0),
    "Napoli":  ZoneConfig("Napoli",  40.8522, 14.2681, 5.0),
    "Torino":  ZoneConfig("Torino",  45.0703,  7.6869, 5.0),
    "Bologna": ZoneConfig("Bologna", 44.4949, 11.3426, 5.0),
}

_NODE_NAMES = [
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon",
    "Zeta", "Eta", "Theta", "Iota", "Kappa",
    "Lambda", "Mu", "Nu", "Xi", "Omicron",
]


def _km_to_deg_lat(km: float) -> float:
    return km / 111.0


def _km_to_deg_lon(km: float, lat: float) -> float:
    return km / (111.0 * math.cos(math.radians(lat)))


def scatter_nodes(
    zone: ZoneConfig,
    pool: NodePoolConfig,
    seed: int = 42,
) -> list[VirtualNode]:
    """Scatter *pool.count* virtual nodes inside *zone* using a Gaussian distribution.

    Nodes cluster toward the zone centre (realistic city topology).
    The same *seed* always produces the same layout.
    """
    import hashlib

    rng = random.Random(seed)
    sigma_lat = _km_to_deg_lat(zone.radius_km / 3)
    sigma_lon = _km_to_deg_lon(zone.radius_km / 3, zone.center_lat)
    max_r_lat = _km_to_deg_lat(zone.radius_km * 1.5)
    max_r_lon = _km_to_deg_lon(zone.radius_km * 1.5, zone.center_lat)

    nodes: list[VirtualNode] = []
    for i in range(pool.count):
        base_name = _NODE_NAMES[i % len(_NODE_NAMES)]
        raw = f"{pool.prefix}-{seed}-{i}".encode()
        node_id = "!" + hashlib.sha1(raw).hexdigest()[:8]

        # Gaussian scatter clamped to 1.5× radius
        lat = rng.gauss(zone.center_lat, sigma_lat)
        lon = rng.gauss(zone.center_lon, sigma_lon)
        lat = max(zone.center_lat - max_r_lat, min(zone.center_lat + max_r_lat, lat))
        lon = max(zone.center_lon - max_r_lon, min(zone.center_lon + max_r_lon, lon))

        nodes.append(VirtualNode(
            id=node_id,
            longname=f"{pool.prefix}_{base_name}",
            shortname=f"{pool.prefix[:2].upper()}{i + 1}",
            lat=round(lat, 6),
            lon=round(lon, 6),
            alt=rng.randint(pool.alt_min, pool.alt_max),
        ))
    return nodes
