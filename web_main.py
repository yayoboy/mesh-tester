#!/usr/bin/env python3
"""Mesh Tester — Web entrypoint.

Usage:
    python web_main.py [--config PATH] [--host HOST] [--port PORT]
                       [--zone PRESET] [--count N] [--prefix PREFIX]

Environment variables (override CLI defaults):
    MQTT_BROKER   — MQTT broker hostname  (default: localhost)
    MQTT_PORT     — MQTT broker port      (default: 1883)
    MESH_ZONE     — Zone preset name      (default: config value)
    MESH_COUNT    — Node count            (default: config value)
    MESH_PREFIX   — Node name prefix      (default: config value)
    WEB_HOST      — Bind host             (default: 0.0.0.0)
    WEB_PORT      — Bind port             (default: 8080)
"""
from __future__ import annotations

import argparse
import os
import sys

import uvicorn

from src.config import AppConfig, ConfigError, load_config
from src.zone import ITALY_PRESETS


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mesh-tester-web",
        description="Mesh Tester — web dashboard (FastAPI + WebSocket)",
    )
    p.add_argument("--config", default=None, metavar="PATH",
                   help="JSON config file (default: built-in defaults)")
    p.add_argument("--host", default=None, metavar="HOST",
                   help="Bind host (default: $WEB_HOST or 0.0.0.0)")
    p.add_argument("--port", type=int, default=None, metavar="PORT",
                   help="Bind port (default: $WEB_PORT or 8080)")
    p.add_argument("--zone", default=None, metavar="PRESET",
                   help=f"Zone preset: {', '.join(ITALY_PRESETS)}")
    p.add_argument("--count", type=int, default=None, metavar="N",
                   help="Number of virtual nodes")
    p.add_argument("--prefix", default=None, metavar="PREFIX",
                   help="Node name prefix (e.g. TST)")
    return p


def _apply_env_and_args(cfg: AppConfig, args: argparse.Namespace) -> None:
    """Apply env-var and CLI overrides onto cfg in-place."""
    # MQTT broker / port from env
    broker = os.environ.get("MQTT_BROKER")
    if broker:
        cfg.mqtt.broker = broker
    port_env = os.environ.get("MQTT_PORT")
    if port_env:
        cfg.mqtt.port = int(port_env)

    # Zone: CLI > env > config
    zone_name = args.zone or os.environ.get("MESH_ZONE")
    if zone_name:
        if zone_name in ITALY_PRESETS:
            cfg.zone = ITALY_PRESETS[zone_name]
        else:
            print(f"Warning: unknown zone '{zone_name}'. "
                  f"Available: {', '.join(ITALY_PRESETS)}", file=sys.stderr)

    count = args.count or (int(os.environ["MESH_COUNT"]) if "MESH_COUNT" in os.environ else None)
    if count is not None:
        cfg.nodes.count = count

    prefix = args.prefix or os.environ.get("MESH_PREFIX")
    if prefix:
        cfg.nodes.prefix = prefix


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, ConfigError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    _apply_env_and_args(cfg, args)

    # Import here so the app is built after config is ready
    from src.web.app import create_app
    app = create_app(cfg)

    host = args.host or os.environ.get("WEB_HOST", "0.0.0.0")
    port = args.port or int(os.environ.get("WEB_PORT", "8080"))

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
