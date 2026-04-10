import pytest
from src.tui.app import MeshTesterApp
from src.tui.widgets.status_bar import StatusBar


# ── key binding registration (sync, no app run needed) ────────────────────────

def test_key_bindings_registered():
    bound_keys = {b.key for b in MeshTesterApp.BINDINGS}
    assert "s" in bound_keys
    assert "p" in bound_keys
    assert "x" in bound_keys
    assert "q" in bound_keys
    assert "tab" in bound_keys


# ── async smoke tests via Textual run_test() ───────────────────────────────────

async def test_app_mounts_status_bar():
    async with MeshTesterApp().run_test() as pilot:
        assert pilot.app.query_one(StatusBar) is not None


async def test_app_has_required_panels():
    async with MeshTesterApp().run_test() as pilot:
        app = pilot.app
        assert app.query_one("#nodes-panel") is not None
        assert app.query_one("#traffic-panel") is not None
        assert app.query_one("#log-panel") is not None


async def test_start_action_sets_running():
    async with MeshTesterApp().run_test() as pilot:
        status_bar = pilot.app.query_one(StatusBar)
        assert not status_bar.running
        await pilot.press("s")
        assert status_bar.running


async def test_stop_action_clears_running():
    async with MeshTesterApp().run_test() as pilot:
        status_bar = pilot.app.query_one(StatusBar)
        await pilot.press("s")
        assert status_bar.running
        await pilot.press("x")
        assert not status_bar.running
