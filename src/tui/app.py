from __future__ import annotations

from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, VerticalScroll
from textual.timer import Timer
from textual.widgets import Footer, Header, Label, Static

from src.mqtt_injector import MqttInjector
from src.recorder import Recorder
from src.traffic_generator import TrafficGenerator
from src.tui.widgets.message_log import MessageLog
from src.tui.widgets.node_table import NodeTable
from src.tui.widgets.status_bar import StatusBar
from src.virtual_node import VirtualNode


class MeshTesterApp(App[None]):
    """Meshtastic mesh network tester — virtual-node traffic injector."""

    TITLE = "Mesh Tester"
    SUB_TITLE = "Meshtastic virtual-node injector"

    BINDINGS = [
        Binding("s", "start", "Start"),
        Binding("p", "pause", "Pause"),
        Binding("x", "stop", "Stop"),
        Binding("q", "quit", "Quit"),
        Binding("tab", "focus_next", "Next panel", show=False),
        Binding("1", "set_scenario('1')", "Scenario 1", show=False),
        Binding("2", "set_scenario('2')", "Scenario 2", show=False),
        Binding("3", "set_scenario('3')", "Scenario 3", show=False),
    ]

    DEFAULT_CSS = """
    /* ── main grid: 2 cols, 2 rows ───────────────────────────────────────── */
    #main-grid {
        grid-size: 2 2;
        grid-columns: 3fr 1fr;
        grid-rows: 3fr 2fr;
        height: 1fr;
    }

    /* ── panel borders ───────────────────────────────────────────────────── */
    #nodes-panel   { border: solid $primary; }
    #traffic-panel { border: solid $accent; }
    #log-panel     { border: solid $secondary; column-span: 2; }

    .panel-title {
        background: $panel;
        color: $text-muted;
        text-style: bold;
        padding: 0 1;
        width: 100%;
        height: 1;
        border-bottom: solid $background;
    }
    #traffic-help {
        color: $text-disabled;
        padding: 1 2;
    }
    """

    def __init__(
        self,
        injector: Optional[MqttInjector] = None,
        nodes: Optional[list[VirtualNode]] = None,
        scenarios: Optional[dict] = None,
        initial_scenario: Optional[str] = None,
        recorder: Optional[Recorder] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._injector = injector
        self._recorder = recorder
        self._virtual_nodes: list[VirtualNode] = list(nodes or [])
        self._scenarios: dict = scenarios or {}
        self._initial_scenario = (
            initial_scenario
            or (next(iter(scenarios)) if scenarios else "LongFast")
        )
        self._generator: Optional[TrafficGenerator] = None
        self._sent_per_node: dict[str, int] = {}
        self._traffic_timer: Optional[Timer] = None

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid(id="main-grid"):
            with VerticalScroll(id="nodes-panel"):
                yield Label("NODES", classes="panel-title")
                yield NodeTable(id="node-table")
            with VerticalScroll(id="traffic-panel"):
                yield Label("TRAFFIC", classes="panel-title")
                yield Static(
                    "s  start\np  pause\nx  stop\n\n1/2/3  scenario",
                    id="traffic-help",
                )
            with VerticalScroll(id="log-panel"):
                yield Label("LOG", classes="panel-title")
                yield MessageLog(id="message-log", markup=False)
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        # Set initial scenario label in status bar
        self.query_one(StatusBar).scenario = self._initial_scenario

        # Populate node table
        table = self.query_one(NodeTable)
        for node in self._virtual_nodes:
            table.add_node(node)
            self._sent_per_node[node.id] = 0

        # Build TrafficGenerator wired to this app's callback
        if self._injector is not None:
            self._generator = TrafficGenerator(
                self._injector, self._virtual_nodes, on_send=self._on_send
            )

    def on_unmount(self) -> None:
        """Clean up timer and MQTT connection on exit."""
        if self._traffic_timer is not None:
            self._traffic_timer.stop()
        if self._injector is not None and self._injector.connected:
            self._injector.disconnect()

    # ── on_send callback ──────────────────────────────────────────────────────

    def _on_send(self, node: VirtualNode, payload: dict, topic: str) -> None:
        """Called by TrafficGenerator for every published message."""
        if self._recorder is not None:
            self._recorder.record(node, payload)
        self._sent_per_node[node.id] = self._sent_per_node.get(node.id, 0) + 1
        self.query_one(NodeTable).update_sent(node.id, self._sent_per_node[node.id])
        log = self.query_one(MessageLog)
        if payload.get("type") == "sendtext":
            log.log_text(node, payload["payload"])
        elif payload.get("type") == "sendposition":
            log.log_position(node)

    # ── traffic round ─────────────────────────────────────────────────────────

    def _traffic_round(self) -> None:
        if self._generator is not None:
            self._generator.send_text_round()
            self._generator.send_position_round()

    # ── actions ───────────────────────────────────────────────────────────────

    def action_start(self) -> None:
        status = self.query_one(StatusBar)
        status.running = True

        if self._injector is None:
            self.notify("Running in UI-only mode (no injector)", severity="warning")
            return

        if not self._injector.connected:
            try:
                self._injector.connect()
            except Exception as exc:
                self.notify(f"MQTT connect failed: {exc}", severity="error")
                status.running = False
                return

        status.mqtt_connected = True

        if self._generator is not None:
            self._generator.announce_nodes()

        if self._traffic_timer is None:
            self._traffic_timer = self.set_interval(2.0, self._traffic_round)
        else:
            self._traffic_timer.resume()

        self.notify("Traffic generation started", severity="information")

    def action_pause(self) -> None:
        if self._traffic_timer is not None:
            self._traffic_timer.pause()
        self.notify("Traffic generation paused", severity="warning")

    def action_stop(self) -> None:
        if self._traffic_timer is not None:
            self._traffic_timer.stop()
            self._traffic_timer = None
        status = self.query_one(StatusBar)
        status.running = False
        if self._injector is not None and self._injector.connected:
            self._injector.disconnect()
            status.mqtt_connected = False
        self.notify("Traffic generation stopped")

    def action_set_scenario(self, scenario_id: str) -> None:
        names = list(self._scenarios.keys())
        idx = int(scenario_id) - 1
        if 0 <= idx < len(names):
            name = names[idx]
            self.query_one(StatusBar).scenario = name
            self.notify(f"Scenario: {name}")
        else:
            self.notify(f"Scenario {scenario_id} not configured", severity="warning")
