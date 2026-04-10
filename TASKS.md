# Mesh Tester - Task List

> **Last updated:** 2026-04-10 (Redesign v2 in progress)
> **Plan:** `docs/superpowers/plans/2026-04-10-mesh-tester.md`
> **Linear project:** [Mesh Tester](https://linear.app/yayoboy/project/mesh-tester-add1c613c89b)

Detailed task breakdown for the Meshtastic mesh network tester. Each task follows
TDD (write failing test → implement → run → commit) and is executed task-by-task
via subagent-driven development.

---

## Progress summary — v1 (complete)

| # | Task | Linear | Status | Commit |
|---|------|--------|--------|--------|
| 1 | Scaffold + Config loader | YAY-200 | done | `9efed0a` |
| 2 | VirtualNode dataclass | YAY-201 | done | `8d99438` |
| 3 | MQTT Injector | YAY-202 | done | `6b9311d` |
| 4 | Traffic Generator | YAY-203 | done | `257f253` |
| 5 | TUI App Shell | YAY-205 | done | `f873672` |
| 6 | TUI Node Table + Message Log widgets | YAY-205 | done | `0e5e37b` |
| 7 | TUI wire-up + `main.py` CLI | YAY-204 | done | `0ac9623` |
| H | Hardware bring-up (Board A + Mosquitto) | YAY-206 | todo | — |

## Progress summary — v2 redesign

| # | Task | Description | Status | Commit |
|---|------|-------------|--------|--------|
| A | Config refactor | `config.py` → dataclasses, no YAML, JSON save/load | done | pending |
| B | Zone + Factory | `zone.py` presets Italia + `node_factory.py` scatter | todo | — |
| C | VirtualNode v2 | walk, telemetry, rogue mode, prefix | todo | — |
| D | Scenarios v2 | idle / chat / walk / burst / replay in TrafficGenerator | todo | — |
| E | Recorder | `recorder.py` — registra sessione reale, replay | todo | — |
| F | TUI v2 | ZonePicker, ScenarioPanel, NodeDetail popup, mouse | todo | — |
| G | main.py v2 | multi-gateway, new config API, zone/factory wiring | todo | — |

**Tests passing (v1):** 35 / 35
**Tests passing (v2):** 38 / 38 (Task A done)

---

## Task 1 — Scaffold + Config loader ✅

**Linear:** YAY-200 · **Commit:** `9efed0a`

- [x] `git init`, `.gitignore`, `requirements.txt`
- [x] Package layout `src/`, `tests/`, `config/`
- [x] `src/config.py` with `load_config(path)`, `ConfigError`, deep-merge of defaults
- [x] Validation: required sections (`mqtt`, `board_a`, `virtual_nodes`), required fields on nodes
- [x] `config/test_config.yaml` with 3 virtual nodes (Alpha/Beta/Gamma, Milano GPS)
- [x] 4 tests in `tests/test_config.py` — all passing

## Task 2 — VirtualNode dataclass ✅

**Linear:** YAY-201 · **Commit:** `8d99438`

- [x] `src/virtual_node.py` — `@dataclass VirtualNode`
- [x] Fields: `id` (hex string `!xxxxxxxx`), `longname`, `shortname`, `lat`, `lon`, `alt`
- [x] `id_decimal` property (hex → int)
- [x] `latitude_i` / `longitude_i` properties (×1e7 integer format)
- [x] `text_payload(text, to_node_id=None)` — Meshtastic `sendtext` JSON
- [x] `position_payload()` — Meshtastic `sendposition` JSON
- [x] `from_config(dict)` factory
- [x] 7 tests in `tests/test_virtual_node.py` — all passing

## Task 3 — MQTT Injector ✅

**Linear:** YAY-202 · **Commit:** `6b9311d`

- [x] `src/mqtt_injector.py` — `MqttInjector(broker, port, topic_root, channel, gateway_id)`
- [x] Builds topic: `{topic_root}/json/{channel}/{gateway_id}`
- [x] `connect()` / `disconnect()` wrap paho `Client` + `loop_start/stop`
- [x] `connected` property
- [x] `publish(node, payload)` serializes JSON and returns timestamp
- [x] 4 tests in `tests/test_mqtt_injector.py` using a fake paho client — all passing

---

## Task 4 — Traffic Generator ✅

**Linear:** YAY-203 · **Files:** `src/traffic_generator.py`, `tests/test_traffic_generator.py`

Class `TrafficGenerator(injector, nodes, on_send=None)` that orchestrates virtual-node traffic.

- [x] Write failing tests (5):
  - [x] `test_announce_nodes_publishes_one_position_per_node`
  - [x] `test_send_text_round_publishes_one_text_per_node`
  - [x] `test_send_position_round_publishes_one_position_per_node`
  - [x] `test_total_sent_counter_increments`
  - [x] `test_on_send_callback_receives_node_and_payload`
- [x] Implement `TrafficGenerator` with:
  - [x] `announce_nodes()` — position burst for all nodes
  - [x] `send_text_round(msg_prefix="test")` — one text per node, incrementing counter
  - [x] `send_position_round()`
  - [x] `add_node(node)` / `remove_node(node_id)`
  - [x] `total_sent` (int), `running` (bool), `nodes` (list) properties
  - [x] `on_send(node, payload, topic)` callback fires per publish
- [x] Run full suite (20 / 20 passing)
- [x] Commit: `feat: traffic generator with configurable text and position rounds`

## Task 5 — TUI App shell ✅

**Linear:** YAY-205 · **Files:** `src/tui/__init__.py`, `src/tui/app.py`, `src/tui/widgets/__init__.py`, `src/tui/widgets/status_bar.py`

- [x] `MeshTesterApp(App)` Textual app with 4-region grid (nodes, traffic, log, status)
- [x] Key bindings: `s` start, `p` pause, `x` stop, `q` quit, `tab` focus cycle
- [x] Scenario switch on `1/2/3` keys (action_set_scenario)
- [x] `StatusBar` widget — MQTT state (●/○), Board A (●/○), run state, scenario, uptime ticker
- [x] Smoke tests using Textual `App.run_test()` — 5 tests: mount, panels, bindings, start/stop actions
- [x] Commit: `feat: TUI app shell with key bindings and status bar`

## Task 6 — TUI widgets: Node Table + Message Log ✅

**Linear:** YAY-205 · **Files:** `src/tui/widgets/node_table.py`, `src/tui/widgets/message_log.py`

- [x] `NodeTable(DataTable)` — columns ID/Name/Lat/Lon/Alt/Sent, `add_node(node)`, `update_sent(node_id, count)`
- [x] `MessageLog(RichLog)` — `log_text(node, text)`, `log_position(node)`, Rich colorized output + `entries` list
- [x] 8 unit tests: column count, row add×2, cell update, text/position entry type and coords
- [x] Commit: `feat: TUI node table and message log widgets`

## Task 7 — TUI wire-up + `main.py` CLI ✅

**Linear:** YAY-204, YAY-205 · **Files:** `main.py`, `src/tui/app.py` (updated)

- [x] `main.py` with argparse: `--config`, `--scenario`, `--dry-run`
- [x] Dry-run prints resolved config + nodes + MQTT topic, no connection
- [x] `MeshTesterApp` accepts `injector`, `nodes`, `scenarios`, `initial_scenario`
- [x] `on_mount` creates `TrafficGenerator` wired to `_on_send` callback
- [x] `_on_send` updates `NodeTable.update_sent` + `MessageLog.log_text/log_position`
- [x] `action_start`: connect MQTT, announce nodes, start 2s interval timer
- [x] `action_pause` / `action_stop`: pause/stop timer, disconnect on stop
- [x] Scenario switch on `1/2/3` keys → updates `StatusBar.scenario`
- [x] Graceful shutdown via `on_unmount`: stops timer + disconnects injector
- [x] Manual smoke test: pending hardware (YAY-206)
- [x] Commit: `feat: wire TUI to injector+generator, add main CLI entrypoint`

---

## Hardware bring-up (out-of-band) ⏳

**Linear:** YAY-206 — not a Python task, needed before end-to-end run.

- [ ] `brew install mosquitto` and start service
- [ ] Board A: flash Meshtastic firmware, join WiFi
- [ ] Board A: enable MQTT module → point to PC IP, JSON enabled, encryption off
- [ ] Board A + Board B: same channel + PSK, `downlink_enabled=true` on ch 0
- [ ] Capture Board A node ID → update `config/test_config.yaml:board_a.gateway_id`
- [ ] Verify with `mosquitto_pub` that Board A retransmits on LoRa (Board B shows message)

---

---

## Task A — Config refactor ✅

**Files:** `src/config.py` (rewrite), `tests/test_config.py` (rewrite), `main.py` (update)

- [x] Replace YAML-based `load_config` with dataclasses: `MqttConfig`, `ZoneConfig`, `NodePoolConfig`, `AppConfig`
- [x] `load_config(path=None)` → returns `AppConfig` from JSON or pure defaults (no file required)
- [x] `save_config(cfg, path)` → serializes `AppConfig` to JSON
- [x] `ConfigError` kept for JSON parse errors
- [x] 7 new tests replacing old 4 (defaults, roundtrip, file-not-found, etc.)
- [x] Update `main.py`: new config API + `_make_nodes()` temporary generation (seed=42)
- [x] Update `test_main.py`: `dry_run()` now takes `AppConfig` + nodes list
- [x] Commit: `refactor: config.py → dataclasses, JSON save/load, no YAML required`

## Task B — Zone + Node Factory ⏳

**Files:** `src/zone.py` (new), `src/node_factory.py` (new), `tests/test_zone.py`, `tests/test_node_factory.py`

- [ ] `ZoneConfig` presets Italia: Milano, Roma, Napoli, Torino, Bologna, Custom
- [ ] `scatter_nodes(zone, pool)` → distribuzione gaussiana centrata (realistica)
- [ ] `NodeFactory(zone, pool)` → `generate()` lista di `VirtualNode` con prefix, ID deterministici
- [ ] Replace temporary node gen in `main.py` with `NodeFactory`
- [ ] Tests: preset coords, scatter within radius, prefix in longname/shortname

## Task C — VirtualNode v2 ⏳

**Files:** `src/virtual_node.py` (extend), `tests/test_virtual_node.py` (extend)

- [ ] `step(speed_kmh, heading_deg)` → aggiorna `lat/lon` incrementalmente
- [ ] `telemetry_payload(battery_level, voltage, snr, rssi)` → payload telemetria
- [ ] `prefix` field opzionale; `longname = f"{prefix}_{base}"` se impostato
- [ ] `is_rogue: bool = False` → se True, `text_payload` produce payload malformato
- [ ] Tests: step sposta coordinate, telemetry ha campi corretti, rogue produce payload invalido

## Task D — Scenari v2 ⏳

**Files:** `src/traffic_generator.py` (extend), `tests/test_traffic_generator.py` (extend)

- [ ] `idle_round(beacon_interval_s)` — solo position ogni N sec
- [ ] `chat_round(vocabulary, rate)` — testo casuale tra nodi
- [ ] `walk_round(speed_kmh)` — chiama `node.step()` + invia position
- [ ] `burst_round(duration_s)` — max frequency per N sec
- [ ] `delay_jitter_ms` param su tutti i round (ritardo realistico LoRa)
- [ ] Tests per ogni nuovo scenario

## Task E — Recorder ⏳

**Files:** `src/recorder.py` (new), `tests/test_recorder.py`

- [ ] `Recorder(path)` — registra eventi `{ts, node_id, type, payload}` in JSONL
- [ ] `record(node, payload)` — appende riga
- [ ] `replay(path, injector, speed_multiplier=1.0)` — riproduce sessione registrata
- [ ] Tests: record scrive file, replay chiama publish nell'ordine corretto

## Task F — TUI v2 ⏳

**Files:** `src/tui/widgets/zone_picker.py`, `src/tui/widgets/scenario_panel.py`, `src/tui/widgets/node_detail.py`, update `src/tui/app.py`

- [ ] `ZonePicker` — dropdown preset Italia + input lat/lon/radius + "Scatter nodes"
- [ ] `ScenarioPanel` — lista scenari cliccabili + parametri (rate, jitter, speed)
- [ ] `NodeDetail` — popup su click riga NodeTable: campi, storico, telemetria, Pin/Mute/Rogue
- [ ] Scroll mouse in MessageLog
- [ ] MQTT dot in StatusBar cliccabile (connect/disconnect)
- [ ] Tests: smoke mount + interazioni base

## Task G — main.py v2 ⏳

**Files:** `main.py` (update), `src/mqtt_injector.py` (extend multi-gateway)

- [ ] `MqttInjector` supporta `gateway_ids: list[str]` → pubblica su topic per ogni gateway
- [ ] `main.py`: usa `NodeFactory`, nuovi scenari, `--zone`, `--count`, `--prefix` argomenti
- [ ] `--save-config PATH` → salva config corrente in JSON
- [ ] Tests: multi-gateway pubblica N volte, argomenti CLI

## Resuming

1. `python -m pytest -v` — verifica tutto verde
2. Leggi questa sezione + progress summary
3. Task corrente: **Task A — Config refactor**
