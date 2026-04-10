from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


class StatusBar(Widget):
    """Bottom status bar: MQTT connection, Board A, scenario, uptime."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        layout: horizontal;
        background: $panel;
        color: $text-muted;
        padding: 0 1;
        border-top: solid $primary-darken-2;
    }
    StatusBar Label {
        height: 1;
        padding: 0 2;
        width: auto;
    }
    StatusBar #status-spacer {
        width: 1fr;
    }
    StatusBar #status-uptime {
        width: auto;
        color: $text-muted;
    }
    """

    mqtt_connected: reactive[bool] = reactive(False)
    board_a_connected: reactive[bool] = reactive(False)
    scenario: reactive[str] = reactive("LongFast")
    running: reactive[bool] = reactive(False)

    _start_time: float = 0.0

    def on_mount(self) -> None:
        self._start_time = time.monotonic()
        self.set_interval(1.0, self._tick_uptime)
        self._refresh_all()

    def compose(self) -> ComposeResult:
        yield Label("", id="status-mqtt")
        yield Label("", id="status-board")
        yield Label("", id="status-run")
        yield Label("", id="status-scenario")
        yield Label("", id="status-spacer")
        yield Label("", id="status-uptime")

    # ── reactive watchers ──────────────────────────────────────────────────────

    def watch_mqtt_connected(self, value: bool) -> None:
        dot = "[green]●[/]" if value else "[red]○[/]"
        self.query_one("#status-mqtt", Label).update(f"{dot} MQTT")

    def watch_board_a_connected(self, value: bool) -> None:
        dot = "[green]●[/]" if value else "[yellow]○[/]"
        self.query_one("#status-board", Label).update(f"{dot} Board A")

    def watch_running(self, value: bool) -> None:
        text = "[green bold]▶ running[/]" if value else "[dim]■ idle[/]"
        self.query_one("#status-run", Label).update(text)

    def watch_scenario(self, value: str) -> None:
        self.query_one("#status-scenario", Label).update(f"[bold cyan]{value}[/]")

    # ── helpers ────────────────────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        self.watch_mqtt_connected(self.mqtt_connected)
        self.watch_board_a_connected(self.board_a_connected)
        self.watch_running(self.running)
        self.watch_scenario(self.scenario)
        self._tick_uptime()

    def _tick_uptime(self) -> None:
        elapsed = int(time.monotonic() - self._start_time)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.query_one("#status-uptime", Label).update(
            f"[dim]⏱ {h:02d}:{m:02d}:{s:02d}[/]"
        )
