from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select

from src.config import ZoneConfig
from src.zone import ITALY_PRESETS


class ZonePicker(Widget):
    """Widget for selecting a zone preset or entering custom lat/lon/radius."""

    DEFAULT_CSS = """
    ZonePicker {
        height: auto;
        border: solid $accent;
        padding: 0 1;
    }
    ZonePicker .picker-row {
        height: 3;
        layout: horizontal;
    }
    ZonePicker Label {
        width: 12;
        height: 3;
        content-align: left middle;
    }
    ZonePicker Input {
        width: 1fr;
    }
    ZonePicker Select {
        width: 1fr;
    }
    ZonePicker Button {
        width: 100%;
        margin-top: 1;
    }
    """

    class ZoneSelected(Message):
        """Posted when the user confirms a zone selection."""
        def __init__(self, zone: ZoneConfig) -> None:
            super().__init__()
            self.zone = zone

    _preset_options = [(name, name) for name in ITALY_PRESETS] + [("Custom", "Custom")]

    current_zone: reactive[str] = reactive("Milano")

    def compose(self) -> ComposeResult:
        yield Label("Zone Picker", id="zone-picker-title")
        with Widget(classes="picker-row"):
            yield Label("Preset")
            yield Select(
                [(name, name) for name in ITALY_PRESETS] + [("Custom", "Custom")],
                value="Milano",
                id="zone-preset",
            )
        with Widget(classes="picker-row"):
            yield Label("Lat")
            yield Input(value="45.4654", id="zone-lat", placeholder="latitude")
        with Widget(classes="picker-row"):
            yield Label("Lon")
            yield Input(value="9.1859", id="zone-lon", placeholder="longitude")
        with Widget(classes="picker-row"):
            yield Label("Radius km")
            yield Input(value="5.0", id="zone-radius", placeholder="radius (km)")
        yield Button("Scatter nodes", id="zone-scatter", variant="primary")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "zone-preset":
            return
        name = str(event.value)
        if name in ITALY_PRESETS:
            zone = ITALY_PRESETS[name]
            self.query_one("#zone-lat", Input).value = str(zone.center_lat)
            self.query_one("#zone-lon", Input).value = str(zone.center_lon)
            self.query_one("#zone-radius", Input).value = str(zone.radius_km)
        self.current_zone = name

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "zone-scatter":
            return
        try:
            lat = float(self.query_one("#zone-lat", Input).value)
            lon = float(self.query_one("#zone-lon", Input).value)
            radius = float(self.query_one("#zone-radius", Input).value)
        except ValueError:
            return
        name = str(self.query_one("#zone-preset", Select).value)
        zone = ZoneConfig(name=name, center_lat=lat, center_lon=lon, radius_km=radius)
        self.post_message(self.ZoneSelected(zone))
