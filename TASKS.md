# Mesh Tester - Task List

> **Last updated:** 2026-04-10 (Task 7 done — software complete)
> **Plan:** `docs/superpowers/plans/2026-04-10-mesh-tester.md`
> **Linear project:** [Mesh Tester](https://linear.app/yayoboy/project/mesh-tester-add1c613c89b)

Detailed task breakdown for the Meshtastic mesh network tester. Each task follows
TDD (write failing test → implement → run → commit) and is executed task-by-task
via subagent-driven development.

---

## Progress summary

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

**Tests passing:** 35 / 35 (config 4 + virtual_node 7 + mqtt_injector 4 + traffic_generator 5 + tui_app 5 + tui_widgets 8 + main 2)

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

## Resuming tomorrow

1. Activate venv: `source .venv/bin/activate`
2. Read this file + `docs/superpowers/plans/2026-04-10-mesh-tester.md`
3. **All software tasks complete** — next step: Hardware bring-up (YAY-206)
4. Continue subagent-driven dispatch (implementer → spec review → code review → commit)
