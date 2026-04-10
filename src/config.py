from __future__ import annotations

import dataclasses
import json
import typing
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    pass


# ── dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class MqttConfig:
    broker: str = "localhost"
    port: int = 1883
    topic_root: str = "msh/EU_868/2"
    channel: str = "LongFast"
    gateway_ids: list[str] = field(default_factory=lambda: ["!00000000"])


@dataclass
class ZoneConfig:
    name: str = "Milano"
    center_lat: float = 45.4654
    center_lon: float = 9.1859
    radius_km: float = 5.0


@dataclass
class NodePoolConfig:
    count: int = 5
    prefix: str = "TST"
    alt_min: int = 50
    alt_max: int = 200


@dataclass
class AppConfig:
    mqtt: MqttConfig = field(default_factory=MqttConfig)
    zone: ZoneConfig = field(default_factory=ZoneConfig)
    nodes: NodePoolConfig = field(default_factory=NodePoolConfig)
    log_to_file: bool = False
    log_path: str = "logs/session.jsonl"


# ── serialization helpers ──────────────────────────────────────────────────────

def _from_dict(cls: type, data: dict):
    """Recursively construct a dataclass from a plain dict."""
    hints = typing.get_type_hints(cls)
    kwargs: dict = {}
    for f in dataclasses.fields(cls):
        if f.name not in data:
            continue
        val = data[f.name]
        field_type = hints.get(f.name)
        if field_type and dataclasses.is_dataclass(field_type) and isinstance(val, dict):
            val = _from_dict(field_type, val)
        kwargs[f.name] = val
    return cls(**kwargs)


# ── public API ─────────────────────────────────────────────────────────────────

def load_config(path: str | None = None) -> AppConfig:
    """Return an AppConfig from a JSON file, or pure defaults if *path* is None."""
    if path is None:
        return AppConfig()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        with open(p) as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config file: {exc}") from exc
    return _from_dict(AppConfig, data)


def save_config(cfg: AppConfig, path: str) -> None:
    """Serialize *cfg* to JSON at *path* (creates parent dirs if needed)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(dataclasses.asdict(cfg), f, indent=2)
