"""
test_state.py — Integration tests for blink_guard.state.SharedState.
"""

import time
import pytest

from blink_guard.state import SharedState, Phase, DetectorState


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestSharedStateInit:
    def test_all_attrs_initialized(self, shared_state):
        s = shared_state
        assert s.detector_state == DetectorState.FACE_NOT_VISIBLE
        assert s.phase == Phase.OBSERVING
        assert s.blink_timestamps == []
        assert s.session_blink_count == 0
        assert s.session_alerts_fired == 0
        assert s.current_threshold is None
        assert s.baseline_interval is None
        assert s.ear_left == 0.0
        assert s.ear_right == 0.0
        assert s.escalation_level == 0
        assert s.dnd_active is False
        assert s.last_jpeg_frame is None

    def test_settings_loaded(self, shared_state):
        assert isinstance(shared_state.settings, dict)
        assert "phase" in shared_state.settings


# ---------------------------------------------------------------------------
# record_blink
# ---------------------------------------------------------------------------

class TestRecordBlink:
    def test_increments_count(self, shared_state):
        shared_state.record_blink()
        assert shared_state.session_blink_count == 1

    def test_appends_timestamp(self, shared_state):
        shared_state.record_blink()
        assert len(shared_state.blink_timestamps) == 1

    def test_sets_blink_detected(self, shared_state):
        shared_state.record_blink()
        assert shared_state.detector_state == DetectorState.BLINK_DETECTED

    def test_resets_consecutive_misses(self, shared_state):
        shared_state.consecutive_misses = 5
        shared_state.record_blink()
        assert shared_state.consecutive_misses == 0

    def test_multiple_blinks(self, shared_state):
        for _ in range(5):
            shared_state.record_blink()
        assert shared_state.session_blink_count == 5
        assert len(shared_state.blink_timestamps) == 5


# ---------------------------------------------------------------------------
# set_detector_state / get_detector_state
# ---------------------------------------------------------------------------

class TestDetectorState:
    def test_set_and_get(self, shared_state):
        shared_state.set_detector_state(DetectorState.WATCHING)
        assert shared_state.get_detector_state() == DetectorState.WATCHING

    def test_paused(self, shared_state):
        shared_state.set_detector_state(DetectorState.PAUSED)
        assert shared_state.get_detector_state() == DetectorState.PAUSED


# ---------------------------------------------------------------------------
# increment_alerts
# ---------------------------------------------------------------------------

class TestIncrementAlerts:
    def test_increments(self, shared_state):
        shared_state.increment_alerts()
        assert shared_state.session_alerts_fired == 1
        assert shared_state.consecutive_misses == 1

    def test_multiple(self, shared_state):
        for _ in range(3):
            shared_state.increment_alerts()
        assert shared_state.session_alerts_fired == 3
        assert shared_state.consecutive_misses == 3


# ---------------------------------------------------------------------------
# reset_session
# ---------------------------------------------------------------------------

class TestResetSession:
    def test_clears_session_counters(self, shared_state):
        shared_state.record_blink()
        shared_state.record_blink()
        shared_state.increment_alerts()
        shared_state.escalation_level = 2
        shared_state.escalation_counts = {"1": 3}

        shared_state.reset_session()

        assert shared_state.session_blink_count == 0
        assert shared_state.session_alerts_fired == 0
        assert shared_state.blink_timestamps == []
        assert shared_state.escalation_level == 0
        assert shared_state.escalation_counts == {}
        assert shared_state.consecutive_misses == 0
        assert shared_state.ear_history == []


# ---------------------------------------------------------------------------
# get_avg_blink_interval
# ---------------------------------------------------------------------------

class TestGetAvgBlinkInterval:
    def test_less_than_two_blinks_returns_none(self, shared_state):
        shared_state.record_blink()
        assert shared_state.get_avg_blink_interval() is None

    def test_zero_blinks_returns_none(self, shared_state):
        assert shared_state.get_avg_blink_interval() is None

    def test_normal_average(self, shared_state):
        # Inject timestamps directly for deterministic testing
        now = time.time()
        shared_state.blink_timestamps = [now, now + 5.0, now + 10.0]
        avg = shared_state.get_avg_blink_interval()
        assert avg == pytest.approx(5.0, rel=0.01)

    def test_outliers_discarded(self, shared_state):
        now = time.time()
        # Two 5s intervals and one 35s outlier
        shared_state.blink_timestamps = [now, now + 5.0, now + 10.0, now + 45.0]
        avg = shared_state.get_avg_blink_interval()
        # Only the two 5s intervals should count
        assert avg == pytest.approx(5.0, rel=0.01)


# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_load_round_trip(self, shared_state):
        shared_state.phase = Phase.ACTIVE
        shared_state.baseline_interval = 8.5
        shared_state.current_threshold = 5.0
        shared_state.sound_enabled = False

        shared_state.save_settings()
        shared_state.load_settings()

        assert shared_state.phase == Phase.ACTIVE
        assert shared_state.baseline_interval == 8.5
        assert shared_state.current_threshold == 5.0
        assert shared_state.sound_enabled is False

    def test_settings_dict_synced(self, shared_state):
        shared_state.phase = Phase.MAINTENANCE
        shared_state.save_settings()

        assert shared_state.settings["phase"] == "maintenance"
