import pytest
from src.config import load_config, ConfigError

VALID_YAML = """
mqtt:
  broker: "localhost"
  port: 1883
  topic_root: "msh/EU_868/2"
  channel: "LongFast"

board_a:
  gateway_id: "!aabbccdd"

virtual_nodes:
  - id: "!11111111"
    longname: "VNode-Alpha"
    shortname: "VA"
    lat: 45.4642
    lon: 9.1900
    alt: 120

scenarios:
  stress_test:
    type: "burst"
    messages_per_node: 10
    interval_ms: 500

output:
  console: true
"""

MISSING_NODES_YAML = """
mqtt:
  broker: "localhost"
board_a:
  gateway_id: "!aabbccdd"
"""

def test_load_valid_config(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(VALID_YAML)
    config = load_config(str(cfg_file))
    assert config["mqtt"]["broker"] == "localhost"
    assert config["mqtt"]["port"] == 1883
    assert len(config["virtual_nodes"]) == 1
    assert config["virtual_nodes"][0]["id"] == "!11111111"
    assert config["board_a"]["gateway_id"] == "!aabbccdd"

def test_load_config_missing_virtual_nodes(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(MISSING_NODES_YAML)
    with pytest.raises(ConfigError, match="virtual_nodes"):
        load_config(str(cfg_file))

def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path.yaml")

def test_load_config_defaults(tmp_path):
    minimal = """
mqtt:
  broker: "localhost"
board_a:
  gateway_id: "!aabbccdd"
virtual_nodes:
  - id: "!11111111"
    longname: "Test"
    shortname: "T"
    lat: 0.0
    lon: 0.0
    alt: 0
"""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(minimal)
    config = load_config(str(cfg_file))
    assert config["mqtt"]["port"] == 1883
    assert config["mqtt"]["channel"] == "LongFast"
