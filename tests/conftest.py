"""
conftest.py — Shared test fixtures for BlinkGuard tests.
"""

import json
import pytest


@pytest.fixture
def tmp_settings_dir(tmp_path, monkeypatch):
    """Redirect settings_path() to a temp directory.

    All tests using this fixture get an isolated settings.json location
    so they never touch the real user config.
    """
    settings_file = str(tmp_path / "settings.json")
    monkeypatch.setattr(
        "blink_guard.defaults.settings_path", lambda: settings_file
    )
    return tmp_path


@pytest.fixture
def fresh_settings(tmp_settings_dir):
    """Return a default settings dict backed by the tmp dir."""
    from blink_guard.defaults import apply_defaults
    return apply_defaults({})


@pytest.fixture
def shared_state(tmp_settings_dir):
    """Create a SharedState with settings pointing to the tmp dir."""
    from blink_guard.state import SharedState
    state = SharedState()
    state.load_settings()
    return state
