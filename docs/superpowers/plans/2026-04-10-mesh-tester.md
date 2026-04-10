# Mesh Tester Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python TUI tool that creates virtual Meshtastic nodes via MQTT injection, generating configurable traffic (messages, GPS positions, nodeinfo) to test a LoRa mesh network. Board A (USB+WiFi) transmits, Board B (standalone) receives and verifies visually.

**Architecture:** Python publishes virtual node JSON packets to Mosquitto (localhost). Board A (WiFi+MQTT downlink) receives and retransmits via LoRa. Board B (standalone) receives — user verifies nodes appear with correct names, positions, messages. TUI built with Textual for real-time control.

**Tech Stack:** Python 3.14 | paho-mqtt | PyYAML | textual | rich | meshtastic (optional, for Board A serial config)

---

## File Structure

```
mesh-tester/
├── config/
│   └── test_config.yaml          # Test configuration (nodes, scenarios, MQTT)
├── src/
│   ├── __init__.py               # Package init
│   ├── config.py                 # YAML config loader + validation
│   ├── virtual_node.py           # VirtualNode dataclass
│   ├── mqtt_injector.py          # MQTT client, publishes virtual node packets
│   ├── traffic_generator.py      # Generates configurable traffic patterns
│   └── tui/
│       ├── __init__.py
│       ├── app.py                # MeshTesterApp - main Textual application
│       └── widgets/
│           ├── __init__.py
│           ├── node_table.py     # Virtual nodes table widget
│           ├── traffic_ctrl.py   # Traffic control panel widget
│           ├── message_log.py    # Real-time message log widget
│           └── status_bar.py     # Connection status bar widget
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_virtual_node.py
│   ├── test_mqtt_injector.py
│   └── test_traffic_generator.py
├── requirements.txt
└── main.py                       # Entry point
```

---

### Task 1: Project Scaffold + Config Loader

**Files:**
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `config/test_config.yaml`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`
- Create: `.gitignore`

- [ ] **Step 1: Initialize git repo and create .gitignore**

```bash
cd /Users/yayoboy/Desktop/GitHub/mesh-tester
git init
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
reports/
.DS_Store
.omc/
.claude/
```

- [ ] **Step 2: Create requirements.txt**

```
meshtastic>=2.3.0
paho-mqtt>=2.0.0
PyYAML>=6.0
textual>=0.50.0
rich>=13.0.0
pytest>=8.0.0
```

- [ ] **Step 3: Create virtual environment and install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 4: Write the failing test for config loader**

`tests/__init__.py`: empty file

`tests/test_config.py`:
```python
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
```

- [ ] **Step 5: Run test to verify it fails**

```bash
source .venv/bin/activate
pytest tests/test_config.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 6: Implement config loader**

`src/__init__.py`: empty file

`src/config.py`:
```python
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
```

- [ ] **Step 7: Run tests and verify they pass**

```bash
pytest tests/test_config.py -v
```
Expected: 4 PASS

- [ ] **Step 8: Create default test_config.yaml**

`config/test_config.yaml`:
```yaml
mqtt:
  broker: "localhost"
  port: 1883
  topic_root: "msh/EU_868/2"
  channel: "LongFast"

# Board A - Transmitter (USB + WiFi, MQTT downlink gateway)
board_a:
  gateway_id: "!aabbccdd"  # CHANGE THIS to Board A's real node ID
  serial_port: "/dev/cu.usbserial-XXXX"  # Optional: for serial config

virtual_nodes:
  - id: "!11111111"
    longname: "VNode-Alpha"
    shortname: "VA"
    lat: 45.4642
    lon: 9.1900
    alt: 120

  - id: "!22222222"
    longname: "VNode-Beta"
    shortname: "VB"
    lat: 45.4700
    lon: 9.1950
    alt: 130

  - id: "!33333333"
    longname: "VNode-Gamma"
    shortname: "VG"
    lat: 45.4580
    lon: 9.1850
    alt: 115

scenarios:
  stress_test:
    type: "burst"
    messages_per_node: 100
    interval_ms: 500

  topology_sim:
    type: "continuous"
    send_position: true
    send_text: true
    position_interval_s: 30
    text_interval_s: 10

  mixed_traffic:
    type: "continuous"
    send_position: true
    send_text: true
    position_interval_s: 15
    text_interval_s: 5
```

- [ ] **Step 9: Commit**

```bash
git add .gitignore requirements.txt config/ src/__init__.py src/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: project scaffold with config loader and validation"
```

---

### Task 2: VirtualNode Dataclass

**Files:**
- Create: `src/virtual_node.py`
- Create: `tests/test_virtual_node.py`

- [ ] **Step 1: Write the failing test**

`tests/test_virtual_node.py`:
```python
from src.virtual_node import VirtualNode


def test_create_virtual_node():
    node = VirtualNode(
        id="!11111111", longname="VNode-Alpha", shortname="VA",
        lat=45.4642, lon=9.1900, alt=120,
    )
    assert node.id == "!11111111"
    assert node.longname == "VNode-Alpha"


def test_node_id_decimal():
    node = VirtualNode(
        id="!11111111", longname="Test", shortname="T",
        lat=0.0, lon=0.0, alt=0,
    )
    assert node.id_decimal == 0x11111111


def test_lat_lon_integer_format():
    node = VirtualNode(
        id="!11111111", longname="Test", shortname="T",
        lat=45.4642, lon=9.1900, alt=120,
    )
    assert node.latitude_i == 454642000
    assert node.longitude_i == 91900000


def test_create_from_config():
    cfg = {"id": "!11111111", "longname": "VNode-Alpha", "shortname": "VA",
           "lat": 45.4642, "lon": 9.1900, "alt": 120}
    node = VirtualNode.from_config(cfg)
    assert node.id == "!11111111"
    assert node.longname == "VNode-Alpha"


def test_mqtt_text_payload():
    node = VirtualNode(
        id="!11111111", longname="Test", shortname="T",
        lat=0.0, lon=0.0, alt=0,
    )
    payload = node.text_payload("hello mesh")
    assert payload == {"from": 0x11111111, "type": "sendtext", "payload": "hello mesh"}


def test_mqtt_position_payload():
    node = VirtualNode(
        id="!11111111", longname="Test", shortname="T",
        lat=45.4642, lon=9.1900, alt=120,
    )
    payload = node.position_payload()
    assert payload["from"] == 0x11111111
    assert payload["type"] == "sendposition"
    assert payload["payload"]["latitude_i"] == 454642000
    assert payload["payload"]["longitude_i"] == 91900000
    assert payload["payload"]["altitude"] == 120


def test_mqtt_dm_payload():
    node = VirtualNode(
        id="!11111111", longname="Test", shortname="T",
        lat=0.0, lon=0.0, alt=0,
    )
    payload = node.text_payload("hello", to_node_id="!aabbccdd")
    assert payload["to"] == 0xAABBCCDD
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_virtual_node.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement VirtualNode**

`src/virtual_node.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
import time


@dataclass
class VirtualNode:
    id: str
    longname: str
    shortname: str
    lat: float
    lon: float
    alt: int

    @classmethod
    def from_config(cls, cfg: dict) -> VirtualNode:
        return cls(
            id=cfg["id"], longname=cfg["longname"], shortname=cfg["shortname"],
            lat=cfg["lat"], lon=cfg["lon"], alt=cfg["alt"],
        )

    @property
    def id_decimal(self) -> int:
        return int(self.id[1:], 16)

    @property
    def latitude_i(self) -> int:
        return int(self.lat * 1e7)

    @property
    def longitude_i(self) -> int:
        return int(self.lon * 1e7)

    def text_payload(self, text: str, to_node_id: str | None = None) -> dict:
        payload = {"from": self.id_decimal, "type": "sendtext", "payload": text}
        if to_node_id is not None:
            payload["to"] = int(to_node_id[1:], 16)
        return payload

    def position_payload(self) -> dict:
        return {
            "from": self.id_decimal,
            "type": "sendposition",
            "payload": {
                "latitude_i": self.latitude_i,
                "longitude_i": self.longitude_i,
                "altitude": self.alt,
                "time": int(time.time()),
            },
        }
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
pytest tests/test_virtual_node.py -v
```
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add src/virtual_node.py tests/test_virtual_node.py
git commit -m "feat: VirtualNode dataclass with MQTT payload builders"
```

---

### Task 3: MQTT Injector

**Files:**
- Create: `src/mqtt_injector.py`
- Create: `tests/test_mqtt_injector.py`

- [ ] **Step 1: Write the failing test**

`tests/test_mqtt_injector.py`:
```python
import json
from unittest.mock import MagicMock, patch
from src.mqtt_injector import MqttInjector
from src.virtual_node import VirtualNode


@patch("src.mqtt_injector.mqtt.Client")
def test_connect(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    injector = MqttInjector(broker="localhost", port=1883,
                            topic_root="msh/EU_868/2", channel="LongFast",
                            gateway_id="!aabbccdd")
    injector.connect()
    mock_client.connect.assert_called_once_with("localhost", 1883, keepalive=60)
    mock_client.loop_start.assert_called_once()


@patch("src.mqtt_injector.mqtt.Client")
def test_disconnect(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    injector = MqttInjector(broker="localhost", port=1883,
                            topic_root="msh/EU_868/2", channel="LongFast",
                            gateway_id="!aabbccdd")
    injector.connect()
    injector.disconnect()
    mock_client.loop_stop.assert_called_once()
    mock_client.disconnect.assert_called_once()


@patch("src.mqtt_injector.mqtt.Client")
def test_publish_text(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    injector = MqttInjector(broker="localhost", port=1883,
                            topic_root="msh/EU_868/2", channel="LongFast",
                            gateway_id="!aabbccdd")
    injector.connect()
    node = VirtualNode(id="!11111111", longname="Test", shortname="T",
                       lat=0.0, lon=0.0, alt=0)
    injector.publish(node, node.text_payload("hello"))
    expected_topic = "msh/EU_868/2/json/LongFast/!aabbccdd"
    expected_payload = json.dumps({"from": 0x11111111, "type": "sendtext", "payload": "hello"})
    mock_client.publish.assert_called_once_with(expected_topic, expected_payload)


@patch("src.mqtt_injector.mqtt.Client")
def test_topic_format(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    injector = MqttInjector(broker="192.168.1.100", port=1884,
                            topic_root="msh/US/2", channel="MyChannel",
                            gateway_id="!deadbeef")
    assert injector.topic == "msh/US/2/json/MyChannel/!deadbeef"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_mqtt_injector.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement MqttInjector**

`src/mqtt_injector.py`:
```python
from __future__ import annotations
import json
import time
import paho.mqtt.client as mqtt
from src.virtual_node import VirtualNode


class MqttInjector:
    def __init__(self, broker: str, port: int, topic_root: str,
                 channel: str, gateway_id: str):
        self.broker = broker
        self.port = port
        self.topic = f"{topic_root}/json/{channel}/{gateway_id}"
        self._client = mqtt.Client()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self._client.connect(self.broker, self.port, keepalive=60)
        self._client.loop_start()
        self._connected = True

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    def publish(self, node: VirtualNode, payload: dict) -> float:
        ts = time.time()
        self._client.publish(self.topic, json.dumps(payload))
        return ts
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
pytest tests/test_mqtt_injector.py -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/mqtt_injector.py tests/test_mqtt_injector.py
git commit -m "feat: MQTT injector for publishing virtual node packets"
```

---

### Task 4: Traffic Generator

**Files:**
- Create: `src/traffic_generator.py`
- Create: `tests/test_traffic_generator.py`

- [ ] **Step 1: Write the failing test**

`tests/test_traffic_generator.py`:
```python
import time
from unittest.mock import MagicMock
from src.traffic_generator import TrafficGenerator
from src.virtual_node import VirtualNode


def _make_nodes():
    return [
        VirtualNode(id="!11111111", longname="Alpha", shortname="VA",
                     lat=45.46, lon=9.19, alt=120),
        VirtualNode(id="!22222222", longname="Beta", shortname="VB",
                     lat=45.47, lon=9.20, alt=130),
    ]


def test_announce_nodes():
    injector = MagicMock()
    injector.publish.return_value = time.time()
    nodes = _make_nodes()
    gen = TrafficGenerator(injector=injector, nodes=nodes)
    gen.announce_nodes()
    assert injector.publish.call_count == 2
    for c in injector.publish.call_args_list:
        payload = c[0][1]
        assert payload["type"] == "sendposition"


def test_send_text_burst():
    injector = MagicMock()
    injector.publish.return_value = time.time()
    nodes = _make_nodes()
    gen = TrafficGenerator(injector=injector, nodes=nodes)
    sent = gen.send_text_round(msg_prefix="test")
    assert injector.publish.call_count == 2
    assert sent == 2


def test_send_position_round():
    injector = MagicMock()
    injector.publish.return_value = time.time()
    nodes = _make_nodes()
    gen = TrafficGenerator(injector=injector, nodes=nodes)
    sent = gen.send_position_round()
    assert injector.publish.call_count == 2
    for c in injector.publish.call_args_list:
        payload = c[0][1]
        assert payload["type"] == "sendposition"


def test_message_counter_increments():
    injector = MagicMock()
    injector.publish.return_value = time.time()
    nodes = _make_nodes()
    gen = TrafficGenerator(injector=injector, nodes=nodes)
    gen.send_text_round(msg_prefix="test")
    gen.send_text_round(msg_prefix="test")
    assert gen.total_sent == 4


def test_log_callback():
    injector = MagicMock()
    injector.publish.return_value = time.time()
    nodes = _make_nodes()
    logs = []
    gen = TrafficGenerator(injector=injector, nodes=nodes, on_send=logs.append)
    gen.send_text_round(msg_prefix="hello")
    assert len(logs) == 2
    assert "Alpha" in logs[0]["node_name"]
    assert logs[0]["type"] == "text"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_traffic_generator.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement TrafficGenerator**

`src/traffic_generator.py`:
```python
from __future__ import annotations
import time
from typing import Callable
from src.virtual_node import VirtualNode
from src.mqtt_injector import MqttInjector


class TrafficGenerator:
    def __init__(self, injector: MqttInjector, nodes: list[VirtualNode],
                 on_send: Callable[[dict], None] | None = None):
        self._injector = injector
        self._nodes = nodes
        self._on_send = on_send
        self._msg_counter = 0
        self._total_sent = 0
        self._running = False

    @property
    def total_sent(self) -> int:
        return self._total_sent

    @property
    def running(self) -> bool:
        return self._running

    @property
    def nodes(self) -> list[VirtualNode]:
        return self._nodes

    def add_node(self, node: VirtualNode) -> None:
        self._nodes.append(node)

    def remove_node(self, node_id: str) -> None:
        self._nodes = [n for n in self._nodes if n.id != node_id]

    def announce_nodes(self) -> None:
        for node in self._nodes:
            payload = node.position_payload()
            self._injector.publish(node, payload)
            self._total_sent += 1
            self._emit_log(node, "position", payload)
            time.sleep(0.1)

    def send_text_round(self, msg_prefix: str = "mesh-test") -> int:
        sent = 0
        for node in self._nodes:
            self._msg_counter += 1
            text = f"{msg_prefix} #{self._msg_counter} from {node.shortname}"
            payload = node.text_payload(text)
            self._injector.publish(node, payload)
            self._total_sent += 1
            sent += 1
            self._emit_log(node, "text", payload)
        return sent

    def send_position_round(self) -> int:
        sent = 0
        for node in self._nodes:
            payload = node.position_payload()
            self._injector.publish(node, payload)
            self._total_sent += 1
            sent += 1
            self._emit_log(node, "position", payload)
        return sent

    def _emit_log(self, node: VirtualNode, msg_type: str, payload: dict) -> None:
        if self._on_send:
            self._on_send({
                "timestamp": time.time(),
                "node_id": node.id,
                "node_name": node.longname,
                "shortname": node.shortname,
                "type": msg_type,
                "payload": payload,
            })
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
pytest tests/test_traffic_generator.py -v
```
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/traffic_generator.py tests/test_traffic_generator.py
git commit -m "feat: traffic generator with configurable text and position rounds"
```

---

### Task 5: TUI - Main App Shell

**Files:**
- Create: `src/tui/__init__.py`
- Create: `src/tui/app.py`
- Create: `src/tui/widgets/__init__.py`
- Create: `src/tui/widgets/status_bar.py`

- [ ] **Step 1: Create TUI package structure**

```bash
mkdir -p src/tui/widgets
touch src/tui/__init__.py src/tui/widgets/__init__.py
```

- [ ] **Step 2: Implement status bar widget**

`src/tui/widgets/status_bar.py`:
```python
from textual.widgets import Static
from textual.reactive import reactive


class StatusBar(Static):
    mqtt_status = reactive("disconnected")
    scenario_name = reactive("none")
    total_sent = reactive(0)

    def render(self) -> str:
        mqtt_icon = "✓" if self.mqtt_status == "connected" else "✗"
        return (
            f" MQTT: {mqtt_icon} {self.mqtt_status}"
            f" | Scenario: {self.scenario_name}"
            f" | Sent: {self.total_sent} msgs"
        )
```

- [ ] **Step 3: Implement main app shell**

`src/tui/app.py`:
```python
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Log
from textual.binding import Binding
from src.tui.widgets.status_bar import StatusBar


class MeshTesterApp(App):
    TITLE = "Mesh Tester"
    CSS = """
    #main {
        height: 1fr;
    }
    #left-panel {
        width: 1fr;
        border: solid green;
    }
    #right-panel {
        width: 40;
        border: solid cyan;
    }
    #log-panel {
        height: 1fr;
        border: solid yellow;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text;
    }
    .panel-title {
        text-style: bold;
        color: $accent;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("s", "start_traffic", "Start"),
        Binding("p", "pause_traffic", "Pause"),
        Binding("x", "stop_traffic", "Stop"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="left-panel"):
                yield Static("Virtual Nodes", classes="panel-title")
                yield Static("No nodes loaded", id="node-table")
            with Vertical(id="right-panel"):
                yield Static("Traffic Control", classes="panel-title")
                yield Static("Status: STOPPED", id="traffic-status")
                yield Static("Sent: 0 msgs", id="traffic-count")
        yield Static("Message Log", classes="panel-title")
        yield Log(id="log-panel")
        yield StatusBar(id="status-bar")
        yield Footer()

    def action_start_traffic(self) -> None:
        self.query_one("#traffic-status", Static).update("Status: ▶ RUNNING")
        self.query_one("#log-panel", Log).write_line("[green]Traffic started[/]")

    def action_pause_traffic(self) -> None:
        self.query_one("#traffic-status", Static).update("Status: ⏸ PAUSED")
        self.query_one("#log-panel", Log).write_line("[yellow]Traffic paused[/]")

    def action_stop_traffic(self) -> None:
        self.query_one("#traffic-status", Static).update("Status: ⏹ STOPPED")
        self.query_one("#log-panel", Log).write_line("[red]Traffic stopped[/]")
```

- [ ] **Step 4: Test the TUI shell launches**

```bash
source .venv/bin/activate
python -c "from src.tui.app import MeshTesterApp; print('TUI app imports OK')"
```
Expected: `TUI app imports OK`

- [ ] **Step 5: Commit**

```bash
git add src/tui/
git commit -m "feat: TUI app shell with Textual - layout, status bar, key bindings"
```

---

### Task 6: TUI - Node Table + Message Log Widgets

**Files:**
- Create: `src/tui/widgets/node_table.py`
- Create: `src/tui/widgets/message_log.py`
- Modify: `src/tui/app.py`

- [ ] **Step 1: Implement node table widget**

`src/tui/widgets/node_table.py`:
```python
from textual.widgets import DataTable
from src.virtual_node import VirtualNode


class NodeTable(DataTable):
    def on_mount(self) -> None:
        self.add_columns("ID", "Name", "Short", "Lat", "Lon", "Alt", "Sent")
        self.cursor_type = "row"

    def load_nodes(self, nodes: list[VirtualNode]) -> None:
        self.clear()
        for node in nodes:
            self.add_row(
                node.id, node.longname, node.shortname,
                f"{node.lat:.4f}", f"{node.lon:.4f}", str(node.alt),
                "0",
                key=node.id,
            )

    def update_sent_count(self, node_id: str, count: int) -> None:
        row_key = self.get_row(node_id) if node_id in self.rows else None
        if row_key is not None:
            col_idx = 6  # "Sent" column
            self.update_cell(node_id, self.columns[col_idx].key, str(count))
```

- [ ] **Step 2: Implement message log widget**

`src/tui/widgets/message_log.py`:
```python
from datetime import datetime
from textual.widgets import RichLog


class MessageLog(RichLog):
    def log_sent(self, node_name: str, shortname: str, msg_type: str,
                 detail: str = "") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        color = "green" if msg_type == "position" else "white"
        type_label = "📍" if msg_type == "position" else "💬"
        text = f"[dim]{ts}[/] [{color}]{shortname}[/] {type_label} {msg_type}"
        if detail:
            text += f" | {detail}"
        self.write(text)

    def log_event(self, message: str, style: str = "yellow") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.write(f"[dim]{ts}[/] [{style}]{message}[/]")
```

- [ ] **Step 3: Update app.py to use real widgets**

`src/tui/app.py`:
```python
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from src.tui.widgets.status_bar import StatusBar
from src.tui.widgets.node_table import NodeTable
from src.tui.widgets.message_log import MessageLog


class MeshTesterApp(App):
    TITLE = "Mesh Tester"
    CSS = """
    #main {
        height: 1fr;
    }
    #left-panel {
        width: 1fr;
        border: solid green;
    }
    #right-panel {
        width: 40;
        border: solid cyan;
    }
    #log-panel {
        height: 2fr;
        border: solid yellow;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text;
    }
    .panel-title {
        text-style: bold;
        color: $accent;
        padding: 0 1;
        height: 1;
    }
    #node-table {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("s", "start_traffic", "Start"),
        Binding("p", "pause_traffic", "Pause"),
        Binding("x", "stop_traffic", "Stop"),
        Binding("a", "add_node", "Add Node"),
        Binding("d", "remove_node", "Remove Node"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config: dict | None = None):
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="left-panel"):
                yield Static("Virtual Nodes", classes="panel-title")
                yield NodeTable(id="node-table")
            with Vertical(id="right-panel"):
                yield Static("Traffic Control", classes="panel-title")
                yield Static("Status: ⏹ STOPPED", id="traffic-status")
                yield Static("Sent: 0 msgs", id="traffic-count")
                yield Static("Interval: --", id="traffic-interval")
                yield Static("Scenario: --", id="traffic-scenario")
        yield Static("Message Log", classes="panel-title")
        yield MessageLog(id="log-panel", max_lines=500)
        yield StatusBar(id="status-bar")
        yield Footer()

    @property
    def log_panel(self) -> MessageLog:
        return self.query_one("#log-panel", MessageLog)

    @property
    def node_table(self) -> NodeTable:
        return self.query_one("#node-table", NodeTable)

    @property
    def status_bar(self) -> StatusBar:
        return self.query_one("#status-bar", StatusBar)

    def action_start_traffic(self) -> None:
        self.query_one("#traffic-status", Static).update("Status: ▶ RUNNING")
        self.log_panel.log_event("Traffic started", "green")

    def action_pause_traffic(self) -> None:
        self.query_one("#traffic-status", Static).update("Status: ⏸ PAUSED")
        self.log_panel.log_event("Traffic paused", "yellow")

    def action_stop_traffic(self) -> None:
        self.query_one("#traffic-status", Static).update("Status: ⏹ STOPPED")
        self.log_panel.log_event("Traffic stopped", "red")

    def action_add_node(self) -> None:
        self.log_panel.log_event("Add node: not yet implemented", "yellow")

    def action_remove_node(self) -> None:
        self.log_panel.log_event("Remove node: not yet implemented", "yellow")
```

- [ ] **Step 4: Test import**

```bash
python -c "from src.tui.app import MeshTesterApp; print('Widgets OK')"
```
Expected: `Widgets OK`

- [ ] **Step 5: Commit**

```bash
git add src/tui/
git commit -m "feat: TUI node table and message log widgets"
```

---

### Task 7: TUI - Wire Up Traffic Generator + MQTT

**Files:**
- Modify: `src/tui/app.py`
- Create: `main.py`

- [ ] **Step 1: Update app.py to wire MQTT + traffic generator**

`src/tui/app.py` — replace the full file:
```python
from __future__ import annotations
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from textual.worker import Worker
from src.config import load_config
from src.virtual_node import VirtualNode
from src.mqtt_injector import MqttInjector
from src.traffic_generator import TrafficGenerator
from src.tui.widgets.status_bar import StatusBar
from src.tui.widgets.node_table import NodeTable
from src.tui.widgets.message_log import MessageLog


class MeshTesterApp(App):
    TITLE = "Mesh Tester"
    CSS = """
    #main { height: 1fr; }
    #left-panel { width: 1fr; border: solid green; }
    #right-panel { width: 40; border: solid cyan; }
    #log-panel { height: 2fr; border: solid yellow; }
    #status-bar { dock: bottom; height: 1; background: $surface; color: $text; }
    .panel-title { text-style: bold; color: $accent; padding: 0 1; height: 1; }
    #node-table { height: 1fr; }
    """

    BINDINGS = [
        Binding("s", "start_traffic", "Start"),
        Binding("p", "pause_traffic", "Pause"),
        Binding("x", "stop_traffic", "Stop"),
        Binding("a", "add_node", "Add Node"),
        Binding("d", "remove_node", "Remove Node"),
        Binding("1", "scenario_stress", "Stress"),
        Binding("2", "scenario_topology", "Topology"),
        Binding("3", "scenario_mixed", "Mixed"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config_path: str = "config/test_config.yaml"):
        super().__init__()
        self._config_path = config_path
        self._config: dict = {}
        self._injector: MqttInjector | None = None
        self._generator: TrafficGenerator | None = None
        self._nodes: list[VirtualNode] = []
        self._traffic_running = False
        self._traffic_paused = False
        self._current_scenario = "stress_test"
        self._traffic_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="left-panel"):
                yield Static("Virtual Nodes", classes="panel-title")
                yield NodeTable(id="node-table")
            with Vertical(id="right-panel"):
                yield Static("Traffic Control", classes="panel-title")
                yield Static("Status: ⏹ STOPPED", id="traffic-status")
                yield Static("Sent: 0 msgs", id="traffic-count")
                yield Static("Scenario: stress_test", id="traffic-scenario")
        yield Static("Message Log", classes="panel-title")
        yield MessageLog(id="log-panel", max_lines=500)
        yield StatusBar(id="status-bar")
        yield Footer()

    @property
    def log_panel(self) -> MessageLog:
        return self.query_one("#log-panel", MessageLog)

    @property
    def node_table(self) -> NodeTable:
        return self.query_one("#node-table", NodeTable)

    @property
    def status_bar(self) -> StatusBar:
        return self.query_one("#status-bar", StatusBar)

    def on_mount(self) -> None:
        try:
            self._config = load_config(self._config_path)
        except Exception as e:
            self.log_panel.log_event(f"Config error: {e}", "red")
            return

        self._nodes = [VirtualNode.from_config(n) for n in self._config["virtual_nodes"]]
        self.node_table.load_nodes(self._nodes)

        mqtt_cfg = self._config["mqtt"]
        self._injector = MqttInjector(
            broker=mqtt_cfg["broker"], port=mqtt_cfg["port"],
            topic_root=mqtt_cfg["topic_root"], channel=mqtt_cfg["channel"],
            gateway_id=self._config["board_a"]["gateway_id"],
        )

        self._generator = TrafficGenerator(
            injector=self._injector, nodes=self._nodes,
            on_send=self._on_message_sent,
        )

        try:
            self._injector.connect()
            self.status_bar.mqtt_status = "connected"
            self.log_panel.log_event("MQTT connected", "green")
        except Exception as e:
            self.status_bar.mqtt_status = "error"
            self.log_panel.log_event(f"MQTT error: {e}", "red")

    def _on_message_sent(self, info: dict) -> None:
        self.call_from_thread(
            self.log_panel.log_sent,
            info["node_name"], info["shortname"], info["type"],
        )
        self.call_from_thread(self._update_counts)

    def _update_counts(self) -> None:
        if self._generator:
            count = self._generator.total_sent
            self.query_one("#traffic-count", Static).update(f"Sent: {count} msgs")
            self.status_bar.total_sent = count

    def _traffic_loop(self) -> None:
        if not self._generator or not self._injector:
            return
        self._generator.announce_nodes()

        scenario = self._config.get("scenarios", {}).get(self._current_scenario, {})
        scenario_type = scenario.get("type", "burst")
        interval_s = scenario.get("interval_ms", 500) / 1000.0 if scenario_type == "burst" else scenario.get("text_interval_s", 5)
        messages_per_node = scenario.get("messages_per_node", 0)
        send_position = scenario.get("send_position", True)
        position_interval = scenario.get("position_interval_s", 30)

        msg_count = 0
        last_position_time = 0.0
        import time

        while self._traffic_running:
            if self._traffic_paused:
                time.sleep(0.5)
                continue

            self._generator.send_text_round(msg_prefix=self._current_scenario)
            msg_count += 1

            now = time.time()
            if send_position and (now - last_position_time) >= position_interval:
                self._generator.send_position_round()
                last_position_time = now

            if scenario_type == "burst" and messages_per_node > 0 and msg_count >= messages_per_node:
                self._traffic_running = False
                self.call_from_thread(
                    self.log_panel.log_event, "Burst complete", "green"
                )
                self.call_from_thread(
                    self.query_one("#traffic-status", Static).update,
                    "Status: ✓ COMPLETE"
                )
                break

            time.sleep(interval_s)

    def action_start_traffic(self) -> None:
        if self._traffic_running:
            return
        self._traffic_running = True
        self._traffic_paused = False
        self.query_one("#traffic-status", Static).update("Status: ▶ RUNNING")
        self.log_panel.log_event(f"Starting {self._current_scenario}", "green")
        self._traffic_worker = self.run_worker(self._traffic_loop, thread=True)

    def action_pause_traffic(self) -> None:
        if not self._traffic_running:
            return
        self._traffic_paused = not self._traffic_paused
        status = "⏸ PAUSED" if self._traffic_paused else "▶ RUNNING"
        self.query_one("#traffic-status", Static).update(f"Status: {status}")
        state = "paused" if self._traffic_paused else "resumed"
        self.log_panel.log_event(f"Traffic {state}", "yellow")

    def action_stop_traffic(self) -> None:
        self._traffic_running = False
        self._traffic_paused = False
        self.query_one("#traffic-status", Static).update("Status: ⏹ STOPPED")
        self.log_panel.log_event("Traffic stopped", "red")

    def _set_scenario(self, name: str) -> None:
        self._current_scenario = name
        self.query_one("#traffic-scenario", Static).update(f"Scenario: {name}")
        self.status_bar.scenario_name = name
        self.log_panel.log_event(f"Scenario: {name}", "cyan")

    def action_scenario_stress(self) -> None:
        self._set_scenario("stress_test")

    def action_scenario_topology(self) -> None:
        self._set_scenario("topology_sim")

    def action_scenario_mixed(self) -> None:
        self._set_scenario("mixed_traffic")

    def action_add_node(self) -> None:
        self.log_panel.log_event("Add node: not yet implemented", "yellow")

    def action_remove_node(self) -> None:
        self.log_panel.log_event("Remove node: not yet implemented", "yellow")

    def on_unmount(self) -> None:
        self._traffic_running = False
        if self._injector:
            self._injector.disconnect()
```

- [ ] **Step 2: Create main.py entry point**

`main.py`:
```python
#!/usr/bin/env python3
"""Mesh Tester - Meshtastic virtual node traffic generator with TUI."""
import argparse
import sys

from src.config import load_config, ConfigError
from src.virtual_node import VirtualNode


def main() -> int:
    parser = argparse.ArgumentParser(description="Meshtastic Mesh Tester")
    parser.add_argument("-c", "--config", default="config/test_config.yaml",
                        help="Path to config YAML")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate config without launching TUI")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except (ConfigError, FileNotFoundError) as e:
        print(f"Config error: {e}")
        return 1

    if args.dry_run:
        nodes = [VirtualNode.from_config(n) for n in config["virtual_nodes"]]
        print(f"Config OK - {len(nodes)} virtual nodes:")
        for node in nodes:
            print(f"  {node.shortname} ({node.id}) - {node.longname} @ {node.lat}, {node.lon}")
        print(f"MQTT: {config['mqtt']['broker']}:{config['mqtt']['port']}")
        print(f"Gateway: {config['board_a']['gateway_id']}")
        return 0

    from src.tui.app import MeshTesterApp
    app = MeshTesterApp(config_path=args.config)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Test dry-run**

```bash
source .venv/bin/activate
python main.py --dry-run
```
Expected: Shows nodes and config, exits cleanly

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v
```
Expected: All tests pass (20 tests)

- [ ] **Step 5: Commit**

```bash
git add src/tui/app.py main.py
git commit -m "feat: wire TUI with MQTT injector and traffic generator, add CLI entry point"
```

---

## Pre-run Hardware Setup Checklist

Before running with real hardware (not part of the implementation tasks):

1. Install Mosquitto: `brew install mosquitto && brew services start mosquitto`
2. Configure Board A: WiFi + MQTT downlink (see `docs/obsidian/hardware/board-a-transmitter.md`)
3. Configure Board B: same channel/PSK as Board A
4. Update `config/test_config.yaml` with Board A's real `gateway_id`
5. Run: `python main.py` (launches TUI)
6. Press `s` to start traffic, verify on Board B
