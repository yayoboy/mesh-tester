from pathlib import Path
import yaml

class ConfigError(Exception):
    pass

DEFAULTS = {
    "mqtt": {"port": 1883, "topic_root": "msh/EU_868/2", "channel": "LongFast"},
    "output": {"console": True},
}

def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def _validate(config: dict) -> None:
    required_sections = ["mqtt", "board_a", "virtual_nodes"]
    for section in required_sections:
        if section not in config:
            raise ConfigError(f"Missing required section: {section}")
    if not isinstance(config["virtual_nodes"], list) or len(config["virtual_nodes"]) == 0:
        raise ConfigError("virtual_nodes must be a non-empty list")
    if "broker" not in config["mqtt"]:
        raise ConfigError("mqtt.broker is required")
    if "gateway_id" not in config["board_a"]:
        raise ConfigError("board_a.gateway_id is required")
    for i, node in enumerate(config["virtual_nodes"]):
        for field in ("id", "longname", "shortname", "lat", "lon", "alt"):
            if field not in node:
                raise ConfigError(f"virtual_nodes[{i}] missing required field: {field}")

def load_config(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    config = _deep_merge(DEFAULTS, raw)
    _validate(config)
    return config
