"""
test_dnd.py — Unit tests for blink_guard.dnd.
"""

import datetime
import pytest
from unittest.mock import patch

from blink_guard.dnd import is_dnd_active, validate_rule


# ---------------------------------------------------------------------------
# validate_rule
# ---------------------------------------------------------------------------

class TestValidateRule:
    def test_valid_rule(self):
        rule = {"days": ["mon", "wed"], "start": "09:00", "end": "10:00"}
        assert validate_rule(rule) is None

    def test_no_days(self):
        rule = {"days": [], "start": "09:00", "end": "10:00"}
        assert "No days" in validate_rule(rule)

    def test_invalid_day(self):
        rule = {"days": ["xyz"], "start": "09:00", "end": "10:00"}
        assert "Invalid day" in validate_rule(rule)

    def test_missing_start(self):
        rule = {"days": ["mon"], "start": "", "end": "10:00"}
        assert "required" in validate_rule(rule)

    def test_missing_end(self):
        rule = {"days": ["mon"], "start": "09:00", "end": ""}
        assert "required" in validate_rule(rule)

    def test_bad_time_format(self):
        rule = {"days": ["mon"], "start": "9am", "end": "10:00"}
        assert "format" in validate_rule(rule).lower()

    def test_start_after_end(self):
        rule = {"days": ["mon"], "start": "14:00", "end": "10:00"}
        assert "before" in validate_rule(rule).lower()

    def test_start_equals_end(self):
        rule = {"days": ["mon"], "start": "10:00", "end": "10:00"}
        assert validate_rule(rule) is not None

    def test_all_days_valid(self):
        for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
            rule = {"days": [day], "start": "08:00", "end": "09:00"}
            assert validate_rule(rule) is None


# ---------------------------------------------------------------------------
# is_dnd_active
# ---------------------------------------------------------------------------

class TestIsDndActive:
    def test_dnd_disabled(self):
        settings = {"dnd_enabled": False, "dnd_schedule": [
            {"days": ["mon"], "start": "00:00", "end": "23:59"}
        ]}
        active, end = is_dnd_active(settings)
        assert active is False
        assert end is None

    def test_no_schedule(self):
        settings = {"dnd_enabled": True, "dnd_schedule": []}
        active, end = is_dnd_active(settings)
        assert active is False

    def test_matching_rule(self):
        # Mock: Wednesday 10:30
        fake_now = datetime.datetime(2026, 4, 22, 10, 30)  # Wed
        with patch("blink_guard.dnd.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fake_now
            mock_dt.datetime.strptime = datetime.datetime.strptime

            settings = {
                "dnd_enabled": True,
                "dnd_schedule": [
                    {"days": ["wed"], "start": "10:00", "end": "11:00"},
                ],
            }
            active, end = is_dnd_active(settings)
            assert active is True
            assert end == "11:00"

    def test_non_matching_day(self):
        # Mock: Tuesday 10:30 — but rule is for Wednesday
        fake_now = datetime.datetime(2026, 4, 21, 10, 30)  # Tue
        with patch("blink_guard.dnd.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fake_now
            mock_dt.datetime.strptime = datetime.datetime.strptime

            settings = {
                "dnd_enabled": True,
                "dnd_schedule": [
                    {"days": ["wed"], "start": "10:00", "end": "11:00"},
                ],
            }
            active, _ = is_dnd_active(settings)
            assert active is False

    def test_outside_time_window(self):
        # Mock: Wednesday 12:00 — outside 10:00-11:00 window
        fake_now = datetime.datetime(2026, 4, 22, 12, 0)  # Wed
        with patch("blink_guard.dnd.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fake_now
            mock_dt.datetime.strptime = datetime.datetime.strptime

            settings = {
                "dnd_enabled": True,
                "dnd_schedule": [
                    {"days": ["wed"], "start": "10:00", "end": "11:00"},
                ],
            }
            active, _ = is_dnd_active(settings)
            assert active is False

    def test_multiple_rules_second_matches(self):
        # Mock: Friday 15:30
        fake_now = datetime.datetime(2026, 4, 24, 15, 30)  # Fri
        with patch("blink_guard.dnd.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fake_now
            mock_dt.datetime.strptime = datetime.datetime.strptime

            settings = {
                "dnd_enabled": True,
                "dnd_schedule": [
                    {"days": ["mon"], "start": "09:00", "end": "10:00"},
                    {"days": ["fri"], "start": "15:00", "end": "16:00"},
                ],
            }
            active, end = is_dnd_active(settings)
            assert active is True
            assert end == "16:00"

    def test_malformed_rule_skipped(self):
        # Rule with empty days/times should be skipped gracefully
        fake_now = datetime.datetime(2026, 4, 22, 10, 30)
        with patch("blink_guard.dnd.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fake_now
            mock_dt.datetime.strptime = datetime.datetime.strptime

            settings = {
                "dnd_enabled": True,
                "dnd_schedule": [
                    {"days": [], "start": "", "end": ""},
                ],
            }
            active, _ = is_dnd_active(settings)
            assert active is False
