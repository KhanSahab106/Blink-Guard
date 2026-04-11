"""
defaults.py — Settings schema, defaults, and path utilities.

Single source of truth for:
  • All settings keys and their default values
  • Settings file path resolution
  • Settings load / save / validate helpers
  • Session history cap
"""

import json
import os
import sys
import logging

logger = logging.getLogger("BlinkGuard")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SESSION_HISTORY = 365  # cap session_history to prevent unbounded growth

# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------

def settings_path() -> str:
    """Return the absolute path to settings.json next to the running script/exe."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "settings.json")


# ---------------------------------------------------------------------------
# Schema — every settings key, its default, and expected type
# ---------------------------------------------------------------------------

SETTINGS_SCHEMA: dict[str, dict] = {
    # Phase & adaptive
    "phase":                  {"default": "observing",  "type": (str,)},
    "baseline_interval":      {"default": None,         "type": (float, int, type(None))},
    "current_threshold":      {"default": None,         "type": (float, int, type(None))},
    "sessions_completed":     {"default": 0,            "type": (int,)},
    "total_sessions_planned": {"default": 14,           "type": (int,)},
    "target_threshold":       {"default": 4.0,          "type": (float, int)},
    "maintenance_sessions":   {"default": 0,            "type": (int,)},

    # User preferences
    "sound_enabled":          {"default": True,         "type": (bool,)},
    "launch_on_startup":      {"default": True,         "type": (bool,)},
    "volume":                 {"default": 75,           "type": (int,)},
    "camera_index":           {"default": 0,            "type": (int,)},
    "show_landmarks":         {"default": True,         "type": (bool,)},

    # Calibration
    "calibrated":             {"default": False,        "type": (bool,)},
    "calibration_date":       {"default": None,         "type": (str, type(None))},
    "ear_blink_threshold":    {"default": 0.2,          "type": (float, int)},
    "ear_open_threshold":     {"default": None,         "type": (float, int, type(None))},

    # Alerts
    "alert_sound":            {"default": "default",    "type": (str,)},
    "custom_sound_path":      {"default": None,         "type": (str, type(None))},

    # DND
    "dnd_enabled":            {"default": False,        "type": (bool,)},
    "dnd_schedule":           {"default": [],           "type": (list,)},

    # Data (containers — not type-checked deeply)
    "session_history":        {"default": [],           "type": (list,)},
    "hourly_data":            {"default": {},           "type": (dict,)},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_defaults(settings: dict) -> dict:
    """Fill in missing keys with schema defaults. Mutates and returns settings."""
    for key, spec in SETTINGS_SCHEMA.items():
        if key not in settings:
            # Deep-copy mutable defaults to avoid shared references
            default = spec["default"]
            if isinstance(default, (list, dict)):
                import copy
                default = copy.deepcopy(default)
            settings[key] = default
    return settings


def validate_settings(settings: dict) -> list[str]:
    """Check types of all known keys. Returns list of warning strings."""
    warnings = []
    for key, spec in SETTINGS_SCHEMA.items():
        if key not in settings:
            continue
        value = settings[key]
        expected_types = spec["type"]
        if not isinstance(value, expected_types):
            warnings.append(
                f"Setting '{key}' has unexpected type {type(value).__name__} "
                f"(expected {'/'.join(t.__name__ for t in expected_types)}), "
                f"resetting to default"
            )
            default = spec["default"]
            if isinstance(default, (list, dict)):
                import copy
                default = copy.deepcopy(default)
            settings[key] = default
    return warnings


def prune_session_history(settings: dict) -> int:
    """Cap session_history to MAX_SESSION_HISTORY entries. Returns count pruned."""
    history = settings.get("session_history", [])
    if len(history) > MAX_SESSION_HISTORY:
        pruned = len(history) - MAX_SESSION_HISTORY
        settings["session_history"] = history[-MAX_SESSION_HISTORY:]
        return pruned
    return 0


def load_settings_from_disk() -> dict:
    """Load settings.json, apply defaults, validate, prune. Returns dict."""
    path = settings_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("settings.json not found or invalid, using defaults.")
        data = {}

    apply_defaults(data)
    warnings = validate_settings(data)
    for w in warnings:
        logger.warning(w)
    pruned = prune_session_history(data)
    if pruned:
        logger.info("Pruned %d old session records (cap: %d).", pruned, MAX_SESSION_HISTORY)
    return data


def save_settings_to_disk(settings: dict) -> None:
    """Persist settings dict to settings.json."""
    path = settings_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        logger.exception("Failed to write settings.json")
