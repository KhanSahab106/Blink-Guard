# BlinkGuard — Requirements

## Scope
Ship BlinkGuard v1.0 as a stable, well-tested, distributable Windows desktop application.

---

## R1: Critical Bug Fixes & Stability

### R1.1 — Settings Schema Validation
- Add a schema/defaults system so missing or corrupt keys in `settings.json` never cause crashes
- Implement a migration path for settings format changes between versions

### R1.2 — Eliminate `hasattr()` Anti-Pattern
- Move all dynamic attributes (`ear_left`, `escalation_level`, `dnd_active`, etc.) into the `SharedState.__init__()` constructor
- Remove all `hasattr()` guards from `detector.py` and `main.py`

### R1.3 — Centralize Settings Path
- Create a single `_settings_path()` utility and remove the 6+ duplicated copies across `state.py` and all `ui/tab_*.py` files

### R1.4 — Bounded Session History
- Cap `session_history` in `settings.json` (e.g., last 365 sessions)
- Archive or prune older records on load

---

## R2: New Features

### R2.1 — Sleep/Wake Session Reset
- Detect Windows resume-from-sleep events via `WM_POWERBROADCAST` / `PBT_APMRESUMEAUTOMATIC`
- On wake: finalize the current session (save stats, update phase), then start a fresh session automatically
- Log the event clearly: "System woke from sleep — session reset"

### R2.2 — Dashboard Access from System Tray
- Double-click on tray icon should open the dashboard (currently only the right-click menu works)
- Ensure "Open Dashboard" menu item works in both frozen (.exe) and dev (python) modes
- If dashboard is already running, bring it to front instead of spawning a duplicate

---

## R3: Refactoring

### R3.1 — Decompose SettingsTab
- Split the 970-line `tab_settings.py` into focused components:
  - `AlertSettingsCard`
  - `CalibrationCard`
  - `DNDScheduleCard`
  - `PhaseManagementCard`
  - `AppearanceCard`
  - `CameraCard`

### R3.2 — Extract Main.py Responsibilities
- Move session finalization logic to a dedicated module (e.g., `session.py`)
- Move IPC callback construction into `ipc.py`
- Move the session prompt dialog into `ui/`

### R3.3 — Camera Recovery
- Detect webcam disconnect (consecutive failed `cap.read()`)
- Show user notification after N failures
- Attempt reconnection periodically

---

## R4: Test Coverage

### R4.1 — Unit Tests for Pure Logic
- `adaptive.py`: `compute_baseline()`, `compute_threshold()`, `update_phase()`, `should_count_session()`
- `risk.py`: `compute_risk_score()`, `get_band()`
- `dnd.py`: `is_dnd_active()`, `validate_rule()`
- Target: 100% branch coverage on these three modules

### R4.2 — Integration Tests
- `ipc.py`: Mock socket server/client round-trip
- `state.py`: SharedState thread-safety under concurrent access

### R4.3 — Test Infrastructure
- Add `pytest` + `pytest-cov` to dev dependencies
- Create `tests/` directory with `conftest.py`
- Add a `test` script to `build.bat` or a Makefile equivalent

---

## R5: Distribution Polish

### R5.1 — Clean Build
- Ensure PyInstaller produces working `.exe` for both background + dashboard
- Test cold-start on a clean Windows machine (no Python installed)

### R5.2 — Version String
- Add `__version__` to `__init__.py`
- Display version in tray tooltip and dashboard title bar

### R5.3 — IPC Port Conflict Handling
- Try primary port 57821, fallback to 57822-57825 if occupied
- Write active port to a lock file so dashboard can discover it

---

## Out of Scope (v1.0)
- Cross-platform support (macOS/Linux)
- Cloud sync or telemetry
- Multi-monitor support
- Break/stretch reminders
- Windows Store packaging
