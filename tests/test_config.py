import pytest
from src.config import (
    AppConfig, MqttConfig, ZoneConfig, NodePoolConfig,
    ConfigError, load_config, save_config,
)


def test_default_appconfig_has_sensible_values():
    cfg = AppConfig()
    assert cfg.mqtt.broker == "localhost"
    assert cfg.mqtt.port == 1883
    assert cfg.zone.name == "Milano"
    assert cfg.nodes.count == 5
    assert cfg.nodes.prefix == "TST"
    assert cfg.log_to_file is False


def test_mqtt_config_gateway_ids_default():
    cfg = MqttConfig()
    assert isinstance(cfg.gateway_ids, list)
    assert len(cfg.gateway_ids) == 1
    assert cfg.gateway_ids[0] == "!00000000"


def test_zone_config_defaults():
    zone = ZoneConfig()
    assert zone.name == "Milano"
    assert zone.center_lat == pytest.approx(45.4654, abs=1e-4)
    assert zone.center_lon == pytest.approx(9.1859, abs=1e-4)
    assert zone.radius_km == pytest.approx(5.0)


def test_node_pool_config_defaults():
    pool = NodePoolConfig()
    assert pool.count == 5
    assert pool.alt_min < pool.alt_max
    assert pool.prefix == "TST"


def test_load_config_no_path_returns_defaults():
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.mqtt.broker == "localhost"
    assert cfg.zone.name == "Milano"


def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.json")


def test_save_and_load_config_roundtrip(tmp_path):
    cfg = AppConfig()
    cfg.mqtt.broker = "192.168.1.100"
    cfg.mqtt.port = 1884
    cfg.mqtt.gateway_ids = ["!deadbeef", "!cafebabe"]
    cfg.nodes.count = 10
    cfg.nodes.prefix = "MIL"
    cfg.zone.name = "Roma"
    cfg.zone.center_lat = 41.9028
    path = str(tmp_path / "config.json")
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.mqtt.broker == "192.168.1.100"
    assert loaded.mqtt.port == 1884
    assert loaded.mqtt.gateway_ids == ["!deadbeef", "!cafebabe"]
    assert loaded.nodes.count == 10
    assert loaded.nodes.prefix == "MIL"
    assert loaded.zone.name == "Roma"
    assert loaded.zone.center_lat == pytest.approx(41.9028)
