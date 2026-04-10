"""Task F — TUI v2 widget smoke tests."""
import pytest
from src.tui.widgets.zone_picker import ZonePicker
from src.tui.widgets.scenario_panel import ScenarioPanel
from src.tui.widgets.node_detail import NodeDetailScreen
from src.virtual_node import VirtualNode


def make_node():
    return VirtualNode(id="!11111111", longname="Alpha", shortname="A",
                       lat=45.0, lon=9.0, alt=100)


# ── ZonePicker ────────────────────────────────────────────────────────────────

async def test_zone_picker_mounts():
    from textual.app import App, ComposeResult

    class _App(App):
        def compose(self) -> ComposeResult:
            yield ZonePicker()

    async with _App().run_test() as pilot:
        assert pilot.app.query_one(ZonePicker) is not None


async def test_zone_picker_has_scatter_button():
    from textual.app import App, ComposeResult
    from textual.widgets import Button

    class _App(App):
        def compose(self) -> ComposeResult:
            yield ZonePicker()

    async with _App().run_test() as pilot:
        btn = pilot.app.query_one("#zone-scatter", Button)
        assert btn is not None


# ── ScenarioPanel ─────────────────────────────────────────────────────────────

async def test_scenario_panel_mounts():
    from textual.app import App, ComposeResult

    class _App(App):
        def compose(self) -> ComposeResult:
            yield ScenarioPanel()

    async with _App().run_test() as pilot:
        assert pilot.app.query_one(ScenarioPanel) is not None


async def test_scenario_panel_has_all_scenarios():
    from textual.app import App, ComposeResult
    from textual.widgets import Button

    class _App(App):
        def compose(self) -> ComposeResult:
            yield ScenarioPanel()

    async with _App().run_test() as pilot:
        for key in ("idle", "chat", "walk", "burst"):
            btn = pilot.app.query_one(f"#scenario-{key}", Button)
            assert btn is not None


async def test_scenario_panel_click_emits_message():
    from textual.app import App, ComposeResult

    received = []

    class _App(App):
        def compose(self) -> ComposeResult:
            yield ScenarioPanel()

        def on_scenario_panel_scenario_activated(self, event: ScenarioPanel.ScenarioActivated):
            received.append(event.name)

    async with _App().run_test() as pilot:
        await pilot.click("#scenario-idle")

    assert received == ["idle"]


# ── NodeDetailScreen ──────────────────────────────────────────────────────────

async def test_node_detail_screen_mounts():
    from textual.app import App, ComposeResult

    node = make_node()

    class _App(App):
        def compose(self) -> ComposeResult:
            return iter([])

        def on_mount(self):
            self.push_screen(NodeDetailScreen(node))

    async with _App().run_test() as pilot:
        assert isinstance(pilot.app.screen, NodeDetailScreen)


async def test_node_detail_close_dismisses():
    from textual.app import App, ComposeResult

    node = make_node()

    class _App(App):
        def compose(self) -> ComposeResult:
            return iter([])

        def on_mount(self):
            self.push_screen(NodeDetailScreen(node))

    async with _App().run_test() as pilot:
        # NodeDetailScreen should be the current screen
        assert isinstance(pilot.app.screen, NodeDetailScreen)
        await pilot.click("#btn-close")
        # After closing, we should be back on the base screen
        assert not isinstance(pilot.app.screen, NodeDetailScreen)
