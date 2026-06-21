# Mesh Tester

Virtual-node Meshtastic traffic injector. Spins up *fake* Meshtastic nodes,
scatters them across a geographic zone, and publishes Meshtastic JSON payloads
over MQTT — so you can load-test, observe, and debug a real mesh **without any
extra hardware**.

Two front-ends share the same core:

- **Web dashboard** (`web_main.py`) — FastAPI + WebSocket live map (Leaflet),
  per-node scheduler, scenario controls. This is the default Docker entrypoint.
- **Terminal UI** (`main.py`) — Textual TUI with node table, message log, and
  keyboard-driven scenario switching.

---

## Quick start

### Docker (broker + app, recommended)

```bash
docker compose up --build
# dashboard → http://localhost:8080
```

Compose starts an `eclipse-mosquitto` broker and the web app wired to it.
Override node generation via env vars:

```bash
MESH_ZONE=Roma MESH_COUNT=10 MESH_PREFIX=TST docker compose up
```

### Local (Python 3.11+)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # or: pip install -e ".[dev]"

python web_main.py                        # web dashboard on :8080
python main.py --zone Milano --count 5    # terminal UI
python main.py --dry-run                  # print resolved config, no MQTT
```

You need an MQTT broker reachable at `MQTT_BROKER:MQTT_PORT`
(default `localhost:1883`). With Docker, the bundled Mosquitto handles this.

---

## Architecture

```
src/
├── virtual_node.py      # VirtualNode dataclass: payloads, mobility, rogue mode
├── zone.py              # Italy presets + deterministic gaussian scatter
├── node_factory.py      # builds VirtualNode lists from zone + pool config
├── mqtt_injector.py     # paho-mqtt 2.x wrapper (single- or multi-gateway)
├── traffic_generator.py # synchronous scenario rounds (used by the TUI)
├── recorder.py          # record traffic to JSONL + replay
├── config.py            # nested dataclasses, JSON load/save
├── tui/                 # Textual terminal UI
└── web/                 # FastAPI app + static dashboard
```

### Two injection models

The two front-ends map virtual nodes onto MQTT differently — pick based on what
you're emulating:

| Front-end | Model | MQTT shape |
|-----------|-------|-----------|
| **TUI** (`main.py`) | **Multi-gateway** | one `MqttInjector`, one client, publishes each payload to *N* gateway topics. Emulates several gateways relaying the same virtual node. |
| **Web** (`web_main.py`) | **Multi-board** | one `MqttInjector` *per node* (`NodeInjector`), each with its own MQTT client and dedicated topic. Emulates *N* independent boards, one per node. |

> Multi-board mode opens one TCP connection to the broker per node, so a run
> with `count=50` uses 50 connections. This is intentional — it makes each
> virtual node indistinguishable from a real, separately-connected device.

### MQTT topic & payload

Topics follow Meshtastic's JSON convention:

```
{topic_root}/json/{channel}/{gateway_id}
e.g.  msh/EU_868/2/json/LongFast/!a1b2c3d4
```

Payloads are Meshtastic JSON: `sendtext`, `sendposition`, `telemetry`.

---

## Scenarios

Each node runs an **independent loop**: it sleeps `interval_s · (1 ± jitter_pct)`
then emits, so higher-jitter scenarios look visibly more chaotic. Defaults:

| Scenario | Interval | Jitter | Emits |
|----------|----------|--------|-------|
| `idle` | 60 s | 50% | position beacon |
| `chat` | 15 s | 70% | random text |
| `walk` | 8 s | 20% | move + position |
| `burst` | 6 s | 10% | 5× text |
| `telemetry` | 30 s | 40% | device metrics (battery, voltage, SNR, RSSI) |

Switch live from the dashboard, or with `--scenario` (TUI). Interval, jitter,
and burst size are tunable at runtime via the sliders / `/api/config/scenario`.

**Zones:** `Milano`, `Roma`, `Napoli`, `Torino`, `Bologna`, plus custom
lat/lon/radius from the map picker (`/api/zone/custom`).

**Rogue mode:** flip a node to `is_rogue` to emit spoofed/malformed traffic
(source ID `0xDEADBEEF`) for security testing.

---

## Recording sessions

Set `log_to_file: true` (and optionally `log_path`) in a JSON config to capture
every emitted payload to JSONL. The parent directory is created automatically.

```bash
python main.py --config myconfig.json    # records to logs/session.jsonl
```

Replay a recorded session through any injector:

```python
from src.recorder import Recorder
from src.mqtt_injector import MqttInjector

inj = MqttInjector("localhost", 1883, "msh/EU_868/2", "LongFast", gateway_id="!a1b2c3d4")
inj.connect()
Recorder.replay("logs/session.jsonl", inj, speed_multiplier=2.0)  # 2× real-time
```

In Docker the `mesh-logs` volume persists recordings at `/app/logs`.

---

## Configuration

CLI flags override the config file, which overrides built-in defaults.

**`main.py`:** `--config PATH` · `--scenario NAME` · `--dry-run` ·
`--zone PRESET` · `--count N` · `--prefix PREFIX` · `--save-config PATH`

**`web_main.py` env vars:** `MQTT_BROKER` · `MQTT_PORT` · `MESH_ZONE` ·
`MESH_COUNT` · `MESH_PREFIX` · `WEB_HOST` · `WEB_PORT`

Save the current resolved config to JSON: `python main.py --zone Roma --count 8 --save-config myconfig.json`

---

## Testing

```bash
pip install -e ".[dev]"
python -m pytest -q          # 106 tests
```

Tests mock the MQTT client, so no broker is required.
See `TASKS.md` for the task-by-task TDD history.
