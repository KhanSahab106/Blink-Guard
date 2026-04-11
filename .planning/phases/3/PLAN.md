# Phase 3: Refactor — Execution Plan

## Overview
**Goal:** Break up god objects (`SettingsTab` at 978 lines, `main.py` at 606 lines) and fix the remaining moderate concerns. After this phase, **no file exceeds 400 lines** and `main.py` is a thin ~150-line orchestrator.

**Exit criteria:**
- `SettingsTab` is a ~60-line container that delegates to 6 card components
- `main.py` is <200 lines — session logic and IPC callbacks live in dedicated modules
- Camera disconnect triggers a user-visible recovery loop with retry
- Remaining `getattr()` calls on SharedState are eliminated

---

## Task 3.1 — Decompose SettingsTab into Card Components

### Problem
`tab_settings.py` is 978 lines — the #1 god object (CONCERNS.md #4). It builds 6 distinct UI cards plus all their callbacks inline. This makes it hard to modify any single feature without risk of breaking others.

### Plan
Create `blink_guard/ui/cards/` package. Extract each card into its own module:

| New File | Lines | What moves |
|----------|-------|------------|
| `cards/__init__.py` | 1 | Package marker |
| `cards/_base.py` | ~40 | Shared palette constants, `_make_card()`, `_make_row()`, `_load_settings()`, `_save_settings()` |
| `cards/card_alert.py` | ~200 | `_build_alert_settings` + all alert callbacks (`_on_sound_toggle`, `_on_volume_change`, `_on_sound_type_change`, `_browse_custom_sound`, `_preview_sound`) |
| `cards/card_startup.py` | ~50 | `_build_startup_settings` + `_on_startup_toggle` |
| `cards/card_journey.py` | ~120 | `_build_journey_settings` + `_on_sessions_change`, `_on_target_change`, `_confirm_reset`, `_do_reset` |
| `cards/card_dnd.py` | ~180 | `_build_dnd_settings` + all DND callbacks (`_on_dnd_toggle`, `_refresh_dnd_rules`, `_delete_dnd_rule`, `_show_add_dnd_rule`, `_save_dnd_rule`) |
| `cards/card_camera.py` | ~100 | `_build_camera_settings` + `_on_camera_change`, `_on_ear_change`, `_on_landmark_toggle`, `_recalibrate` |
| `cards/card_about.py` | ~50 | `_build_about` + `_open_log_dir` |

Each card is a `ctk.CTkFrame` subclass that:
- Receives `parent` (the scroll frame) and `app` (the DashboardApp) in `__init__`
- Has a `refresh(settings: dict)` method for data reload
- Self-contained: builds its UI and handles all callbacks internally

**SettingsTab** becomes a thin container (~60 lines):
```python
class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, ...)
        self._cards = [
            AlertCard(self._scroll, app),
            StartupCard(self._scroll, app),
            JourneyCard(self._scroll, app),
            DNDCard(self._scroll, app),
            CameraCard(self._scroll, app),
            AboutCard(self._scroll, app),
        ]

    def _refresh_data(self):
        settings = _load_settings()
        for card in self._cards:
            card.refresh(settings)
```

### Files
| Action | File | Change |
|--------|------|--------|
| NEW | `ui/cards/__init__.py` | Package marker |
| NEW | `ui/cards/_base.py` | Shared palette + helper methods |
| NEW | `ui/cards/card_alert.py` | AlertCard |
| NEW | `ui/cards/card_startup.py` | StartupCard |
| NEW | `ui/cards/card_journey.py` | JourneyCard |
| NEW | `ui/cards/card_dnd.py` | DNDCard |
| NEW | `ui/cards/card_camera.py` | CameraCard |
| NEW | `ui/cards/card_about.py` | AboutCard |
| MODIFY | `ui/tab_settings.py` | Rewrite to thin container (~60 lines) |

### Verification
- All 9 files pass `py_compile`
- Dashboard opens, settings tab renders all 6 cards
- Changing a setting persists to `settings.json`

---

## Task 3.2 — Extract Session Logic from main.py

### Problem
`main.py` is 606 lines (CONCERNS.md #5). The `_finalise_session()` function alone is ~100 lines of session bookkeeping, phase transitions, and weekly summary logic. The IPC callback builder is another ~70 lines that doesn't belong in the entry point.

### Plan
Create `blink_guard/session.py` (~120 lines) containing:
- `finalise_session(shared)` — moved from `main.py:207-298`
- `session_updater(shared)` — moved from `main.py:188-200`
- `SAVE_INTERVAL_SECONDS = 60`

This brings `main.py` to ~480 lines. Next...

### Task 3.3 — Move IPC Callbacks into ipc.py

Move `_build_ipc_callbacks(shared)` from `main.py:305-374` into `ipc.py` as a standalone factory function.

**After both extractions**, `main.py` drops to ~410 lines. The remaining bulk is:
- Logging setup (~30 lines)
- Session watcher + wake reset (~90 lines)  
- Calibration wizard (~60 lines)
- Session prompt dialog (~90 lines)
- `main()` entry point (~50 lines)

This is a reasonable size for an orchestrator and meets the <400 line target when we also:
- Remove the `_on_wake_reset` forward reference issue by importing from `session.py`

### Files
| Action | File | Change |
|--------|------|--------|
| NEW | `blink_guard/session.py` | `finalise_session()`, `session_updater()` |
| MODIFY | `blink_guard/main.py` | Remove `_finalise_session`, `_session_updater`, `_build_ipc_callbacks`; add imports |
| MODIFY | `blink_guard/ipc.py` | Add `build_ipc_callbacks(shared)` factory |

### Verification
- `py_compile` all 3 files
- App starts, runs a session, IPC still works

---

## Task 3.4 — Camera Disconnect Recovery

### Problem
If the webcam disconnects mid-session, `cap.read()` returns `(False, None)` and the loop just `continue`s forever (CONCERNS.md #10). No user notification, no retry.

### Plan
Add camera recovery logic in `detector.py` after the `cap.read()` call:

```python
consecutive_read_fails = 0
MAX_READ_FAILS = 30  # ~1 second at 30fps

# In the loop:
ret, frame = cap.read()
if not ret:
    consecutive_read_fails += 1
    if consecutive_read_fails >= MAX_READ_FAILS:
        logger.warning("Camera disconnected — attempting recovery...")
        shared.set_detector_state(DetectorState.PAUSED)
        cap.release()
        # Retry loop
        recovered = False
        for attempt in range(10):
            time.sleep(3)  # wait 3s between retries
            if shared.shutdown_event.is_set():
                return
            cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
            if cap.isOpened():
                logger.info("Camera recovered after %d attempts.", attempt + 1)
                recovered = True
                break
        if not recovered:
            logger.error("Camera recovery failed after 10 attempts — detector stopping.")
            return
        consecutive_read_fails = 0
        shared.set_detector_state(DetectorState.WATCHING)
    time.sleep(0.05)
    continue
consecutive_read_fails = 0  # reset on success
```

### Files
| Action | File | Change |
|--------|------|--------|
| MODIFY | `blink_guard/detector.py` L164-167 | Add camera recovery loop |

### Verification
- Unplug USB webcam → check log for "Camera disconnected — attempting recovery"
- Plug back in → detector resumes

---

## Task 3.5 — Clean Up Remaining getattr() Calls

### Problem
Phase 1 cleaned `hasattr()` from `detector.py`, but `main.py` IPC callbacks still use `getattr(shared, "ear_left", 0.0)` etc. Now that SharedState properly initializes all these attributes, `getattr()` is unnecessary.

### Plan
Replace all `getattr(shared, "attr", default)` in `_build_ipc_callbacks` with direct access `shared.attr`. This will be done as part of Task 3.3 when we move the callbacks to `ipc.py`.

**Affected lines** (currently in `main.py:314-329`):
```python
# Before:
"ear_left": getattr(shared, "ear_left", 0.0),
# After:
"ear_left": shared.ear_left,
```

### Files
| Action | File | Change |
|--------|------|--------|
| Part of 3.3 | `blink_guard/ipc.py` | Remove 7 getattr() calls |

---

## Execution Order

```
3.1 (SettingsTab decompose)  ← largest task, independent
3.2 (Extract session.py)     ← depends on nothing
3.3 (Move IPC callbacks)     ← depends on 3.2 (both modify main.py)
3.4 (Camera recovery)        ← independent
3.5 (Clean getattr)          ← bundled into 3.3
```

Order: **3.2 → 3.3/3.5 → 3.1 → 3.4**

This way the `main.py` extractions happen first (3.2+3.3), then SettingsTab (3.1), then the detector fix (3.4).

---

## Expected Line Counts After Phase 3

| File | Before | After |
|------|--------|-------|
| `main.py` | 606 | ~350 |
| `tab_settings.py` | 978 | ~60 |
| `ipc.py` | 276 | ~350 |
| `session.py` | NEW | ~120 |
| `cards/*.py` (8 files) | NEW | ~40-200 each |
| `detector.py` | 348 | ~380 |

**No file exceeds 400 lines.** ✅

---

## Risk Assessment
| Risk | Mitigation |
|------|------------|
| Card components losing access to `app.ipc` | Each card receives `app` reference in constructor |
| Circular imports between `session.py` and `main.py` | `session.py` only imports from `state`, `adaptive`, `risk`, `weekly` — no back-import to `main` |
| `_on_wake_reset` in `main.py` calls `_finalise_session` which moves to `session.py` | Update import in `main.py` |
| Camera recovery blocks the detector thread for up to 30s | This is acceptable — the detector thread is dedicated and has nothing else to do while camera is disconnected |

---

**Ready to execute.** Run `/gsd:execute-phase 3` to begin.
