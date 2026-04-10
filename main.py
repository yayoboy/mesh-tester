#!/usr/bin/env python3
"""Mesh Tester — CLI entrypoint.

Usage:
    python main.py [--config PATH] [--scenario NAME] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys

from src.config import AppConfig, ConfigError, load_config
from src.mqtt_injector import MqttInjector
from src.node_factory import NodeFactory
from src.tui.app import MeshTesterApp
from src.virtual_node import VirtualNode


def _make_nodes(cfg: AppConfig) -> list[VirtualNode]:
    """Generate virtual nodes via NodeFactory (deterministic, seed=42)."""
    return NodeFactory(cfg.zone, cfg.nodes, seed=42).generate()


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mesh-tester",
        description="Inject virtual Meshtastic nodes into a mesh via MQTT.",
    )
    p.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="JSON config file (default: built-in defaults)",
    )
    p.add_argument(
        "--scenario",
        default=None,
        metavar="NAME",
        help="Scenario to activate on start",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved config and exit without connecting to MQTT",
    )
    return p


def dry_run(cfg: AppConfig, nodes: list[VirtualNode]) -> None:
    """Print a human-readable summary of the resolved config and node list."""
    gw = cfg.mqtt.gateway_ids[0]
    topic = f"{cfg.mqtt.topic_root}/json/{cfg.mqtt.channel}/{gw}"

    print("=== Mesh Tester — Dry Run ===")
    print(f"\n  MQTT broker  : {cfg.mqtt.broker}:{cfg.mqtt.port}")
    print(f"  Topic        : {topic}")
    print(f"  Gateway IDs  : {', '.join(cfg.mqtt.gateway_ids)}")
    print(f"  Zone         : {cfg.zone.name}"
          f" ({cfg.zone.center_lat:.4f}, {cfg.zone.center_lon:.4f}"
          f" r={cfg.zone.radius_km} km)")
    print(f"\n  Virtual nodes ({len(nodes)}):")
    for n in nodes:
        print(
            f"    {n.id:13s}  {n.longname:28s}"
            f"  lat={n.lat:.4f}  lon={n.lon:.4f}  alt={n.alt} m"
        )
    print()


def main(argv=None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, ConfigError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    nodes = _make_nodes(cfg)

    if args.dry_run:
        dry_run(cfg, nodes)
        return

    injector = MqttInjector(
        broker=cfg.mqtt.broker,
        port=cfg.mqtt.port,
        topic_root=cfg.mqtt.topic_root,
        channel=cfg.mqtt.channel,
        gateway_id=cfg.mqtt.gateway_ids[0],
    )
    initial_scenario = args.scenario or cfg.zone.name

    app = MeshTesterApp(
        injector=injector,
        nodes=nodes,
        initial_scenario=initial_scenario,
    )
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        if injector.connected:
            injector.disconnect()


if __name__ == "__main__":
    main()
