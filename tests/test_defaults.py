"""
test_defaults.py — Unit tests for blink_guard.defaults.
"""

import json
import pytest

from blink_guard.defaults import (
    apply_defaults,
    validate_settings,
    prune_session_history,
    load_settings_from_disk,
    save_settings_to_disk,
    SETTINGS_SCHEMA,
    MAX_SESSION_HISTORY,
)


# ---------------------------------------------------------------------------
# apply_defaults
# ---------------------------------------------------------------------------

class TestApplyDefaults:
    def test_empty_dict_gets_all_defaults(self):
        settings = apply_defaults({})
        for key in SETTINGS_SCHEMA:
            assert key in settings

    def test_existing_values_preserved(self):
        settings = apply_defaults({"volume": 42})
        assert settings["volume"] == 42

    def test_missing_keys_filled(self):
        settings = apply_defaults({"volume": 50})
        assert "phase" in settings
        assert settings["phase"] == "observing"

    def test_mutable_defaults_are_copies(self):
        s1 = apply_defaults({})
        s2 = apply_defaults({})
        # Mutating one should not affect the other
        s1["session_history"].append("test")
        assert len(s2["session_history"]) == 0


# ---------------------------------------------------------------------------
# validate_settings
# ---------------------------------------------------------------------------

class TestValidateSettings:
    def test_correct_types_no_warnings(self):
        settings = apply_defaults({})
        warnings = validate_settings(settings)
        assert warnings == []

    def test_wrong_type_resets_to_default(self):
        settings = {"volume": "not_an_int"}
        warnings = validate_settings(settings)
        assert len(warnings) == 1
        assert settings["volume"] == 75  # default

    def test_none_where_allowed(self):
        settings = {"baseline_interval": None}
        warnings = validate_settings(settings)
        assert warnings == []

    def test_multiple_bad_keys(self):
        settings = {"volume": "bad", "sound_enabled": "bad"}
        warnings = validate_settings(settings)
        assert len(warnings) == 2


# ---------------------------------------------------------------------------
# prune_session_history
# ---------------------------------------------------------------------------

class TestPruneSessionHistory:
    def test_under_cap_not_pruned(self):
        history = [{"date": f"d{i}"} for i in range(10)]
        settings = {"session_history": history}
        pruned = prune_session_history(settings)
        assert pruned == 0
        assert len(settings["session_history"]) == 10

    def test_over_cap_trimmed(self):
        history = [{"date": f"d{i}"} for i in range(400)]
        settings = {"session_history": history}
        pruned = prune_session_history(settings)
        assert pruned == 400 - MAX_SESSION_HISTORY
        assert len(settings["session_history"]) == MAX_SESSION_HISTORY
        # Should keep the most recent entries
        assert settings["session_history"][-1]["date"] == "d399"

    def test_exactly_at_cap(self):
        history = [{"date": f"d{i}"} for i in range(MAX_SESSION_HISTORY)]
        settings = {"session_history": history}
        pruned = prune_session_history(settings)
        assert pruned == 0

    def test_empty_history(self):
        settings = {"session_history": []}
        pruned = prune_session_history(settings)
        assert pruned == 0


# ---------------------------------------------------------------------------
# load / save round-trip
# ---------------------------------------------------------------------------

class TestLoadSave:
    def test_missing_file_returns_defaults(self, tmp_settings_dir):
        settings = load_settings_from_disk()
        assert settings["phase"] == "observing"
        assert settings["volume"] == 75

    def test_round_trip(self, tmp_settings_dir):
        original = apply_defaults({"volume": 42, "phase": "active"})
        save_settings_to_disk(original)
        loaded = load_settings_from_disk()
        assert loaded["volume"] == 42
        assert loaded["phase"] == "active"

    def test_corrupt_json_returns_defaults(self, tmp_settings_dir):
        path = str(tmp_settings_dir / "settings.json")
        with open(path, "w") as f:
            f.write("{bad json!!")
        settings = load_settings_from_disk()
        assert settings["phase"] == "observing"

    def test_partial_file_fills_missing(self, tmp_settings_dir):
        path = str(tmp_settings_dir / "settings.json")
        with open(path, "w") as f:
            json.dump({"volume": 99}, f)
        settings = load_settings_from_disk()
        assert settings["volume"] == 99
        assert settings["phase"] == "observing"  # default applied
