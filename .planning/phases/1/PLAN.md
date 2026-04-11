# Phase 1: Foundation & Critical Fixes — Execution Plan

## Overview
**Goal:** Make the app stable and safe to build on. Every piece of code should have documented defaults, a single source of truth for paths, and no silent failure modes.

**Exit criteria:** App starts, runs a session, and saves settings without any silent failures. All settings have documented defaults. SharedState has no dynamic attributes.

---

## Task 1.1 — Settings Schema Validation + Defaults

### Problem
`settings.json` is a raw dict with no schema. Missing keys cause `KeyError` crashes or `None` propagation. Every consumer must manually handle missing keys with `.get()` and hope they used the right default.

### Plan

**Create `blink_guard/defaults.py`** — Single source of truth for all settings:

```python
SETTINGS_SCHEMA = {
    # Phase & adaptive
    "phase": {"default": "observing", "type": str},
    "baseline_interval": {"default": None, "type": (float, type(None))},
    "current_threshold": {"default": None, "type": (float, type(None))},
    "sessions_completed": {"default": 0, "type": int},
    "total_sessions_planned": {"default": 14, "type": int},
    "target_threshold": {"default": 4.0, "type": float},
    "maintenance_sessions": {"default": 0, "type": int},
    
    # User preferences
    "sound_enabled": {"default": True, "type": bool},
    "launch_on_startup": {"default": True, "type": bool},
    "volume": {"default": 75, "type": int},
    "camera_index": {"default": 0, "type": int},
    "show_landmarks": {"default": True, "type": bool},
    
    # Calibration
    "calibrated": {"default": False, "type": bool},
    "calibration_date": {"default": None, "type": (str, type(None))},
    "ear_blink_threshold": {"default": 0.2, "type": float},
    "ear_open_threshold": {"default": None, "type": (float, type(None))},
    
    # Alerts
    "alert_sound": {"default": "default", "type": str},
    "custom_sound_path": {"default": None, "type": (str, type(None))},
    
    # DND
    "dnd_enabled": {"default": False, "type": bool},
    "dnd_schedule": {"default": [], "type": list},
    
    # Data
    "session_history": {"default": [], "type": list},
    "hourly_data": {"default": {}, "type": dict},
}

def apply_defaults(settings: dict) -> dict:
    """Fill in missing keys from schema. Returns mutated dict."""

def validate_settings(settings: dict) -> list[str]:
    """Return list of warning messages for invalid values."""
```

**Modify `state.py`** — Call `apply_defaults()` in `load_settings()` after loading JSON.

### Files
| Action | File | Lines |
|--------|------|-------|
| CREATE | `blink_guard/defaults.py` | ~80 |
| MODIFY | `blink_guard/state.py` | L136-145 (`load_settings`) |

### Verification
- Delete `settings.json`, start app → should create one with all defaults
- Corrupt a key (e.g. `"volume": "abc"`), start app → should log warning, use default

---

## Task 1.2 — Move Dynamic Attributes into SharedState Constructor

### Problem
`main.py` sets attributes on `SharedState` at runtime (`shared.ear_left`, `shared.escalation_level`, etc.) and `detector.py` checks them with `hasattr()`. This is fragile — if `main.py` changes, detector silently stops working.

### Plan
Move all 8 dynamic attributes into `SharedState.__init__()`:

```python
# In __init__():
self.ear_left: float = 0.0
self.ear_right: float = 0.0
self.ear_history: list = []
self.last_jpeg_frame: bytes | None = None
self.escalation_level: int = 0
self.escalation_counts: dict = {}
self.dnd_active: bool = False
self.dnd_end_time: str | None = None
```

Then remove:
- 8 lines from `main.py` (L515-522) that set these attributes
- 11 `hasattr()` checks from `detector.py` (L183, 195, 198, 238, 267, 271, 293, 305, 316, 332)

### Files
| Action | File | Lines |
|--------|------|-------|
| MODIFY | `blink_guard/state.py` | `__init__()` — add 8 attributes |
| MODIFY | `blink_guard/main.py` | L514-522 — remove 8 lines |
| MODIFY | `blink_guard/detector.py` | 11 locations — remove `hasattr()` guards |

### Verification
- Start app → no `AttributeError` crashes
- Dashboard receives EAR data, escalation data, DND status correctly

---

## Task 1.3 — Centralize `_settings_path()`

### Problem
`_settings_path()` is duplicated in **6 files** with identical logic. Any path change must be made 6 times.

Found in:
- `state.py:21`
- `weekly.py:45`
- `ui/tab_settings.py:54`
- `ui/tab_progress.py:50`
- `ui/tab_history.py:49`
- `ui/calibration.py:49`

### Plan
1. Move the canonical `_settings_path()` from `state.py` to `defaults.py` (alongside the schema) and rename to `settings_path()` (public)
2. Also add `load_settings_from_disk()` and `save_settings_to_disk()` helpers to `defaults.py`
3. In all 6 files: replace the local `_settings_path()` / `_load_settings()` / `_save_settings()` with imports from `defaults`

### Files
| Action | File | Change |
|--------|------|--------|
| MODIFY | `blink_guard/defaults.py` | Add `settings_path()`, `load_settings_from_disk()`, `save_settings_to_disk()` |
| MODIFY | `blink_guard/state.py` | Remove `_settings_path()`, import from defaults |
| MODIFY | `blink_guard/weekly.py` | Remove `_settings_path()` + `_load_settings()`, import |
| MODIFY | `blink_guard/ui/tab_settings.py` | Remove `_settings_path()` + helpers, import |
| MODIFY | `blink_guard/ui/tab_progress.py` | Remove `_settings_path()` + `_load_settings()`, import |
| MODIFY | `blink_guard/ui/tab_history.py` | Remove `_settings_path()` + `_load_settings()`, import |
| MODIFY | `blink_guard/ui/calibration.py` | Remove `_settings_path()` + helpers, import |

### Verification
- `grep -r "_settings_path" blink_guard/` returns only the canonical definition in `defaults.py`
- App starts, settings load/save correctly
- Dashboard tabs all read the correct settings

---

## Task 1.4 — Bound Session History

### Problem
`session_history` grows unbounded. After a year of daily 2-hour sessions, this list will have 365+ records bloating `settings.json`.

### Plan
Add a `MAX_SESSION_HISTORY = 365` constant to `defaults.py`.

In `load_settings()` (state.py), after applying defaults:
```python
history = settings.get("session_history", [])
if len(history) > MAX_SESSION_HISTORY:
    settings["session_history"] = history[-MAX_SESSION_HISTORY:]
```

### Files
| Action | File | Change |
|--------|------|--------|
| MODIFY | `blink_guard/defaults.py` | Add `MAX_SESSION_HISTORY = 365` |
| MODIFY | `blink_guard/state.py` | Prune in `load_settings()` |

### Verification
- Create a settings.json with 500 fake sessions → after load, only 365 remain

---

## Task 1.5 — Add Version String

### Problem
No version identifier anywhere. Users (future) can't tell what version they're running. Tray tooltip just says "BlinkGuard".

### Plan
1. Add `__version__ = "1.0.0-dev"` to `blink_guard/__init__.py`
2. Update tray tooltip: `title=f"BlinkGuard v{__version__}"`  in `tray.py`
3. Update dashboard title bar: `self.title(f"BlinkGuard Dashboard v{__version__}")` in `ui/app.py`

### Files
| Action | File | Change |
|--------|------|--------|
| MODIFY | `blink_guard/__init__.py` | Add `__version__` |
| MODIFY | `blink_guard/tray.py` | Use version in icon title |
| MODIFY | `blink_guard/ui/app.py` | Use version in window title |

### Verification
- Tray icon tooltip shows "BlinkGuard v1.0.0-dev"
- Dashboard title bar shows "BlinkGuard Dashboard v1.0.0-dev"

---

## Execution Order

```
1.1 (defaults.py)  ← foundation, everything depends on this
        │
        ├── 1.2 (SharedState cleanup)  ← depends on defaults being in place
        ├── 1.3 (centralize paths)     ← depends on defaults.py existing
        └── 1.4 (bound history)        ← trivial, depends on defaults.py
                │
                └── 1.5 (version string)  ← independent, do last
```

Tasks 1.2, 1.3, and 1.4 can be done in parallel after 1.1 is complete.

---

## Risk Assessment
| Risk | Mitigation |
|------|------------|
| Settings migration breaks existing users | `apply_defaults()` only adds missing keys, never removes |
| Removing hasattr breaks detector | Test immediately after change — attributes are now guaranteed |
| Import cycle from defaults.py | defaults.py has zero local imports — pure data + stdlib only |

---

**Ready to execute.** Run `/gsd:execute-phase 1` to begin.
