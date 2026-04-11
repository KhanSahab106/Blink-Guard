# Testing

## Current State
- **No automated tests exist.** No `tests/` directory, no test files, no test runner configured.
- No CI/CD pipeline.
- Testing is manual: run the application, observe behavior, check `blinkguard.log`.

## Manual Testing Approach
1. Launch `main.py` → confirm session prompt appears
2. Accept session → verify tray icon appears with correct menu items
3. Observe webcam → confirm blink detection (debug log shows EAR values)
4. Wait for threshold → confirm escalating beep alerts (L1 → L2 → L3)
5. Open dashboard → confirm live feed, charts, settings render correctly
6. Change settings in dashboard → confirm they persist across restarts

## Recommended Test Strategy (future)
| Layer | Tool | Coverage Target |
|-------|------|-----------------|
| Unit | pytest | `adaptive.py`, `risk.py`, `dnd.py` (pure logic, no I/O) |
| Integration | pytest + mock | `detector.py` (mock camera), `ipc.py` (mock socket) |
| E2E | manual | Full session lifecycle with webcam |

## Quick-Win Unit Tests
These modules are pure functions with no side effects — ideal first targets:
- `compute_baseline()` — edge cases: empty list, all outliers, single value
- `compute_threshold()` — boundary: 0 sessions, max sessions, 0 total planned
- `compute_risk_score()` — boundary: None threshold, 0 duration, extreme values
- `is_dnd_active()` — time matching, day matching, edge of window
- `validate_rule()` — invalid days, missing times, reversed start/end
- `should_count_session()` — exactly 5 min, below, above
