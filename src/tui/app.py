from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, VerticalScroll
from textual.widgets import Footer, Header, Label, Static

from src.tui.widgets.status_bar import StatusBar


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

    /* ── panel borders & titles ──────────────────────────────────────────── */
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
    .panel-placeholder {
        color: $text-disabled;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid(id="main-grid"):
            with VerticalScroll(id="nodes-panel"):
                yield Label("NODES", classes="panel-title")
                yield Static(
                    "Node table will appear here (Task 6)",
                    classes="panel-placeholder",
                    id="node-table-placeholder",
                )
            with VerticalScroll(id="traffic-panel"):
                yield Label("TRAFFIC", classes="panel-title")
                yield Static(
                    "Traffic control panel (Task 7)",
                    classes="panel-placeholder",
                    id="traffic-placeholder",
                )
            with VerticalScroll(id="log-panel"):
                yield Label("LOG", classes="panel-title")
                yield Static(
                    "Message log will appear here (Task 6)",
                    classes="panel-placeholder",
                    id="log-placeholder",
                )
        yield StatusBar()
        yield Footer()

    # ── actions ───────────────────────────────────────────────────────────────

    def action_start(self) -> None:
        self.query_one(StatusBar).running = True
        self.notify("Traffic generation started", severity="information")

    def action_pause(self) -> None:
        self.notify("Traffic generation paused", severity="warning")

    def action_stop(self) -> None:
        self.query_one(StatusBar).running = False
        self.notify("Traffic generation stopped")

    def action_set_scenario(self, scenario_id: str) -> None:
        self.query_one(StatusBar).scenario = f"Scenario {scenario_id}"
        self.notify(f"Switched to scenario {scenario_id}")
