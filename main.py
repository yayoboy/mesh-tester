#!/usr/bin/env python3
"""Mesh Tester — CLI entrypoint.

Usage:
    python main.py [--config PATH] [--scenario NAME] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys

from src.config import ConfigError, load_config
from src.mqtt_injector import MqttInjector
from src.tui.app import MeshTesterApp
from src.virtual_node import VirtualNode


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mesh-tester",
        description="Inject virtual Meshtastic nodes into a mesh via MQTT.",
    )
    p.add_argument(
        "--config",
        default="config/test_config.yaml",
        metavar="PATH",
        help="YAML config file (default: config/test_config.yaml)",
    )
    p.add_argument(
        "--scenario",
        default=None,
        metavar="NAME",
        help="Scenario to activate on start (default: first in config)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved config and exit without connecting to MQTT",
    )
    return p


def dry_run(cfg: dict) -> None:
    """Print a human-readable summary of the resolved config to stdout."""
    mqtt = cfg["mqtt"]
    board = cfg["board_a"]
    nodes = cfg["virtual_nodes"]
    topic = f"{mqtt['topic_root']}/json/{mqtt['channel']}/{board['gateway_id']}"

    print("=== Mesh Tester — Dry Run ===")
    print(f"\n  MQTT broker : {mqtt['broker']}:{mqtt['port']}")
    print(f"  Topic       : {topic}")
    print(f"  Gateway ID  : {board['gateway_id']}")
    print(f"\n  Virtual nodes ({len(nodes)}):")
    for n in nodes:
        print(
            f"    {n['id']:13s}  {n['longname']:22s}"
            f"  lat={n['lat']:.4f}  lon={n['lon']:.4f}  alt={n['alt']} m"
        )
    scenarios = cfg.get("scenarios", {})
    if scenarios:
        print(f"\n  Scenarios: {', '.join(scenarios.keys())}")
    print()


def main(argv=None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, ConfigError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        dry_run(cfg)
        return

    nodes = [VirtualNode.from_config(nc) for nc in cfg["virtual_nodes"]]
    mqtt_cfg = cfg["mqtt"]
    injector = MqttInjector(
        broker=mqtt_cfg["broker"],
        port=mqtt_cfg["port"],
        topic_root=mqtt_cfg["topic_root"],
        channel=mqtt_cfg["channel"],
        gateway_id=cfg["board_a"]["gateway_id"],
    )
    scenarios = cfg.get("scenarios", {})
    initial_scenario = args.scenario or (next(iter(scenarios), None) or "LongFast")

    app = MeshTesterApp(
        injector=injector,
        nodes=nodes,
        scenarios=scenarios,
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
