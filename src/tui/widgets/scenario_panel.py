from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label

_SCENARIOS = [
    ("idle",  "Idle (positions only)"),
    ("chat",  "Chat (random text)"),
    ("walk",  "Walk (move + position)"),
    ("burst", "Burst (high-rate text)"),
]


class ScenarioPanel(Widget):
    """Panel listing clickable scenarios with configurable parameters."""

    DEFAULT_CSS = """
    ScenarioPanel {
        height: auto;
        border: solid $primary;
        padding: 0 1;
    }
    ScenarioPanel .scenario-btn {
        width: 100%;
        margin-bottom: 1;
    }
    ScenarioPanel .param-row {
        height: 3;
        layout: horizontal;
    }
    ScenarioPanel .param-label {
        width: 14;
        height: 3;
        content-align: left middle;
    }
    ScenarioPanel .param-input {
        width: 1fr;
    }
    ScenarioPanel .active-scenario {
        background: $accent;
    }
    """

    class ScenarioActivated(Message):
        """Posted when the user selects a scenario."""
        def __init__(self, name: str, params: dict) -> None:
            super().__init__()
            self.name = name
            self.params = params

    active_scenario: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        yield Label("Scenarios", id="scenario-panel-title")
        for key, label in _SCENARIOS:
            yield Button(label, id=f"scenario-{key}", classes="scenario-btn")
        # Shared parameters
        with Widget(classes="param-row"):
            yield Label("Jitter ms", classes="param-label")
            yield Input(value="0", id="param-jitter", classes="param-input",
                        placeholder="delay jitter ms")
        with Widget(classes="param-row"):
            yield Label("Speed km/h", classes="param-label")
            yield Input(value="3.6", id="param-speed", classes="param-input",
                        placeholder="walk speed km/h")
        with Widget(classes="param-row"):
            yield Label("Burst count", classes="param-label")
            yield Input(value="3", id="param-burst", classes="param-input",
                        placeholder="burst message count")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id: str = event.button.id or ""
        if not btn_id.startswith("scenario-"):
            return
        name = btn_id.removeprefix("scenario-")
        # Remove active class from all buttons, add to selected
        for key, _ in _SCENARIOS:
            btn = self.query_one(f"#scenario-{key}", Button)
            btn.remove_class("active-scenario")
        event.button.add_class("active-scenario")
        self.active_scenario = name

        params = self._collect_params()
        self.post_message(self.ScenarioActivated(name, params))

    def _collect_params(self) -> dict:
        try:
            jitter = int(self.query_one("#param-jitter", Input).value)
        except ValueError:
            jitter = 0
        try:
            speed = float(self.query_one("#param-speed", Input).value)
        except ValueError:
            speed = 3.6
        try:
            burst = int(self.query_one("#param-burst", Input).value)
        except ValueError:
            burst = 3
        return {"jitter_ms": jitter, "speed_kmh": speed, "burst_count": burst}
