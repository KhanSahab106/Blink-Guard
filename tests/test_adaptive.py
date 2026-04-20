"""
test_adaptive.py — Unit tests for blink_guard.adaptive.
"""

import pytest
from blink_guard.adaptive import (
    compute_baseline,
    compute_threshold,
    get_total_sessions,
    should_count_session,
    update_phase,
    MIN_BASELINE,
    MAX_BASELINE,
    OUTLIER_CEILING,
    SHORT_SESSION_MINUTES,
    MAINTENANCE_GOAL,
)


# ---------------------------------------------------------------------------
# compute_baseline
# ---------------------------------------------------------------------------

class TestComputeBaseline:
    def test_normal_intervals(self):
        result = compute_baseline([5.0, 6.0, 7.0, 4.0])
        assert result == pytest.approx(5.5)

    def test_clamps_to_min(self):
        result = compute_baseline([0.1, 0.2, 0.3])
        assert result == MIN_BASELINE

    def test_clamps_to_max(self):
        # All values above MAX_BASELINE individually but mean is clamped
        result = compute_baseline([26.0, 28.0, 29.0])
        assert result == MAX_BASELINE

    def test_all_outliers_returns_max(self):
        result = compute_baseline([35.0, 40.0, 50.0])
        assert result == MAX_BASELINE

    def test_empty_list_returns_max(self):
        result = compute_baseline([])
        assert result == MAX_BASELINE

    def test_single_item(self):
        result = compute_baseline([8.0])
        assert result == 8.0

    def test_mixed_with_outliers(self):
        # Outliers (>30s) are filtered; only 5.0 and 10.0 remain
        result = compute_baseline([5.0, 10.0, 35.0, 50.0])
        assert result == pytest.approx(7.5)


# ---------------------------------------------------------------------------
# compute_threshold
# ---------------------------------------------------------------------------

class TestComputeThreshold:
    def test_zero_sessions(self):
        # 0 progress → threshold == baseline
        result = compute_threshold(12.0, 0, 14, 4.0)
        assert result == 12.0

    def test_at_completion(self):
        # Full progress → threshold == target
        result = compute_threshold(12.0, 14, 14, 4.0)
        assert result == 4.0

    def test_mid_progress(self):
        # 50% → midpoint between baseline and target
        result = compute_threshold(12.0, 7, 14, 4.0)
        assert result == pytest.approx(8.0)

    def test_overshoot_capped(self):
        # More sessions than planned → still capped at target
        result = compute_threshold(12.0, 20, 14, 4.0)
        assert result == 4.0

    def test_zero_planned_returns_target(self):
        result = compute_threshold(12.0, 5, 0, 4.0)
        assert result == 4.0


# ---------------------------------------------------------------------------
# get_total_sessions
# ---------------------------------------------------------------------------

class TestGetTotalSessions:
    def test_healthy_baseline(self):
        assert get_total_sessions(4.0) == 7
        assert get_total_sessions(5.0) == 7

    def test_unhealthy_baseline(self):
        assert get_total_sessions(6.0) == 14
        assert get_total_sessions(15.0) == 14


# ---------------------------------------------------------------------------
# should_count_session
# ---------------------------------------------------------------------------

class TestShouldCountSession:
    def test_too_short(self):
        assert should_count_session(4.9) is False

    def test_exactly_min(self):
        assert should_count_session(SHORT_SESSION_MINUTES) is True

    def test_long_session(self):
        assert should_count_session(60.0) is True


# ---------------------------------------------------------------------------
# update_phase
# ---------------------------------------------------------------------------

class TestUpdatePhase:
    def test_observing_stays_without_baseline(self):
        settings = {"phase": "observing", "baseline_interval": None}
        result = update_phase(settings)
        assert result["phase"] == "observing"

    def test_observing_to_active(self):
        settings = {"phase": "observing", "baseline_interval": 10.0}
        result = update_phase(settings)
        assert result["phase"] == "active"
        assert "current_threshold" in result
        assert "total_sessions_planned" in result

    def test_active_stays_below_target(self):
        settings = {
            "phase": "active",
            "sessions_completed": 3,
            "total_sessions_planned": 14,
            "baseline_interval": 12.0,
            "target_threshold": 4.0,
        }
        result = update_phase(settings)
        assert result["phase"] == "active"

    def test_active_to_maintenance(self):
        settings = {
            "phase": "active",
            "sessions_completed": 14,
            "total_sessions_planned": 14,
            "baseline_interval": 12.0,
            "target_threshold": 4.0,
        }
        result = update_phase(settings)
        assert result["phase"] == "maintenance"
        assert result["current_threshold"] == 4.0

    def test_maintenance_stays_below_goal(self):
        settings = {
            "phase": "maintenance",
            "maintenance_sessions": 3,
        }
        result = update_phase(settings)
        assert result["phase"] == "maintenance"

    def test_maintenance_to_wean_off(self):
        settings = {
            "phase": "maintenance",
            "maintenance_sessions": MAINTENANCE_GOAL,
        }
        result = update_phase(settings)
        assert result["phase"] == "wean_off"

    def test_wean_off_stays(self):
        settings = {"phase": "wean_off"}
        result = update_phase(settings)
        assert result["phase"] == "wean_off"
