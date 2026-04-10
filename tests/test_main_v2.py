"""Task G — main.py v2 CLI tests."""
import json
import os
import tempfile
import pytest
from main import build_arg_parser, dry_run, _apply_cli_overrides, _make_nodes
from src.config import AppConfig


def make_cfg():
    return AppConfig()


def test_zone_override_changes_zone():
    cfg = make_cfg()
    args = build_arg_parser().parse_args(["--zone", "Roma"])
    _apply_cli_overrides(cfg, args)
    assert cfg.zone.name == "Roma"
    assert abs(cfg.zone.center_lat - 41.9028) < 0.01


def test_count_override():
    cfg = make_cfg()
    args = build_arg_parser().parse_args(["--count", "12"])
    _apply_cli_overrides(cfg, args)
    assert cfg.nodes.count == 12


def test_prefix_override():
    cfg = make_cfg()
    args = build_arg_parser().parse_args(["--prefix", "XYZ"])
    _apply_cli_overrides(cfg, args)
    assert cfg.nodes.prefix == "XYZ"


def test_prefix_appears_in_node_longname():
    cfg = make_cfg()
    args = build_arg_parser().parse_args(["--prefix", "ABC", "--count", "3"])
    _apply_cli_overrides(cfg, args)
    nodes = _make_nodes(cfg)
    assert all("ABC" in n.longname for n in nodes)


def test_save_config_writes_file(capsys):
    cfg = make_cfg()
    cfg.mqtt.broker = "save-test-broker"
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        from main import main
        main(["--save-config", path])
        with open(path) as fh:
            data = json.load(fh)
        assert "mqtt" in data
    finally:
        os.unlink(path)


def test_dry_run_with_zone_override(capsys):
    from main import main
    main(["--dry-run", "--zone", "Napoli", "--count", "3"])
    out = capsys.readouterr().out
    assert "Napoli" in out
    assert "nodes (3)" in out


def test_unknown_zone_warns(capsys):
    cfg = make_cfg()
    original_name = cfg.zone.name
    args = build_arg_parser().parse_args(["--zone", "Atlantide"])
    import sys
    from io import StringIO
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    _apply_cli_overrides(cfg, args)
    stderr_out = sys.stderr.getvalue()
    sys.stderr = old_stderr
    # Zone should not have changed to unknown preset
    assert "Atlantide" in stderr_out
    assert cfg.zone.name == original_name
