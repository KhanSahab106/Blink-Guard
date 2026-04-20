"""
test_risk.py — Unit tests for blink_guard.risk.
"""

import pytest
from blink_guard.risk import compute_risk_score, get_band


# ---------------------------------------------------------------------------
# compute_risk_score
# ---------------------------------------------------------------------------

class TestComputeRiskScore:
    def test_null_threshold_returns_low(self):
        score, band, color = compute_risk_score(5.0, None, 3, 30.0)
        assert score == 0
        assert band == "Low"

    def test_zero_threshold_returns_low(self):
        score, band, color = compute_risk_score(5.0, 0, 3, 30.0)
        assert score == 0
        assert band == "Low"

    def test_low_risk(self):
        # Low interval ratio, few alerts, short session
        score, band, _ = compute_risk_score(2.0, 5.0, 0, 10.0)
        assert score <= 25
        assert band == "Low"

    def test_high_risk_many_alerts(self):
        # High interval ratio + many alerts → high score
        score, band, _ = compute_risk_score(8.0, 4.0, 20, 10.0)
        assert score > 50

    def test_severe_risk(self):
        score, band, _ = compute_risk_score(15.0, 4.0, 50, 5.0)
        assert band == "Severe"
        assert score >= 75

    def test_score_clamped_to_100(self):
        score, _, _ = compute_risk_score(100.0, 4.0, 1000, 1.0)
        assert score <= 100

    def test_score_clamped_to_0(self):
        score, _, _ = compute_risk_score(0, 5.0, 0, 10.0)
        assert score >= 0

    def test_duration_penalty_short(self):
        # <30 min → no penalty
        score_short, _, _ = compute_risk_score(3.0, 5.0, 1, 20.0)
        score_long, _, _ = compute_risk_score(3.0, 5.0, 1, 60.0)
        assert score_long > score_short

    def test_duration_penalty_very_long(self):
        # >120 min → max penalty (25). Use 0 alerts to isolate the penalty.
        score_long, _, _ = compute_risk_score(3.0, 5.0, 0, 150.0)
        score_short, _, _ = compute_risk_score(3.0, 5.0, 0, 10.0)
        assert score_long - score_short == 25

    def test_none_avg_interval(self):
        # avg_interval=None → treated as 0
        score, band, _ = compute_risk_score(None, 5.0, 0, 10.0)
        assert score >= 0
        assert band == "Low"


# ---------------------------------------------------------------------------
# get_band
# ---------------------------------------------------------------------------

class TestGetBand:
    def test_low_boundary(self):
        name, color = get_band(0)
        assert name == "Low"

    def test_low_upper(self):
        name, _ = get_band(25)
        assert name == "Low"

    def test_moderate(self):
        name, _ = get_band(26)
        assert name == "Moderate"

    def test_moderate_upper(self):
        name, _ = get_band(50)
        assert name == "Moderate"

    def test_high(self):
        name, _ = get_band(51)
        assert name == "High"

    def test_severe(self):
        name, _ = get_band(76)
        assert name == "Severe"

    def test_max(self):
        name, _ = get_band(100)
        assert name == "Severe"
