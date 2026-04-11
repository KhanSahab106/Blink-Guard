# Phase 4: Tests & Distribution — Execution Plan

## Overview
**Goal:** Add automated test coverage to the pure-logic modules, validate the refactored build pipeline, and preparation for v1.0 release.

**Exit criteria:**
- `pytest` runs with ≥90% coverage on `adaptive.py`, `risk.py`, `dnd.py`
- `defaults.py` schema validation/pruning is tested
- `state.py` thread-safe helpers are tested
- `build.bat` includes new modules (`session.py`, `ui/cards/`)
- All tests pass green

---

## Task 4.1 — Test Infrastructure

### Plan
Create `pyproject.toml` with pytest config, a `tests/` directory, and a shared `conftest.py`.

### Files
| Action | File | Detail |
|--------|------|--------|
| NEW | `pyproject.toml` | `[tool.pytest.ini_options]` + `[tool.coverage]` config |
| NEW | `tests/__init__.py` | Package marker |
| NEW | `tests/conftest.py` | Shared fixtures: `sample_settings()`, `mock_shared_state()` |

---

## Task 4.2 — Unit Tests: adaptive.py

### Functions to test
| Function | Test cases |
|----------|------------|
| `compute_baseline()` | Normal intervals, all outliers (>30s), empty list, mixed, single-value list |
| `compute_threshold()` | 0 sessions (start), midway, completed (≥planned), 0 planned sessions |
| `get_total_sessions()` | Healthy baseline (≤5), high baseline (>5) |
| `should_count_session()` | Short (<5 min), exactly 5 min, long (>5 min) |
| `update_phase()` | OBSERVING→ACTIVE (baseline set), ACTIVE→MAINTENANCE (enough sessions), MAINTENANCE→WEAN_OFF (enough maintenance), WEAN_OFF stays, OBSERVING stays (no baseline) |

### Files
| Action | File |
|--------|------|
| NEW | `tests/test_adaptive.py` (~25 test functions) |

---

## Task 4.3 — Unit Tests: risk.py

### Functions to test
| Function | Test cases |
|----------|------------|
| `compute_risk_score()` | No threshold (returns 0), low risk (normal blinks, few alerts), moderate, high, severe, long session penalty, short session no penalty |
| `get_band()` | Each boundary value (0, 25, 26, 50, 51, 75, 76, 100) |

### Files
| Action | File |
|--------|------|
| NEW | `tests/test_risk.py` (~12 test functions) |

---

## Task 4.4 — Unit Tests: dnd.py

### Functions to test
| Function | Test cases |
|----------|------------|
| `is_dnd_active()` | DND disabled, no schedule, active window matches, wrong day, wrong time, multiple rules |
| `validate_rule()` | Valid rule, no days, invalid day name, missing times, bad format, start≥end |

### Approach
`is_dnd_active` uses `datetime.datetime.now()` — freeze time with `unittest.mock.patch` or `freezegun`.

### Files
| Action | File |
|--------|------|
| NEW | `tests/test_dnd.py` (~14 test functions) |

---

## Task 4.5 — Unit Tests: defaults.py

### Functions to test
| Function | Test cases |
|----------|------------|
| `apply_defaults()` | Empty dict → all defaults, partial dict → only missing filled, mutable defaults are deep-copied |
| `validate_settings()` | Correct types → no warnings, wrong types → reset + warning, unknown keys → ignored |
| `prune_session_history()` | Under cap (no-op), exact cap, over cap (oldest trimmed) |

### Files
| Action | File |
|--------|------|
| NEW | `tests/test_defaults.py` (~10 test functions) |

---

## Task 4.6 — Integration Tests: state.py

### What to test
| Method | Test cases |
|--------|------------|
| `record_blink()` | Updates count, timestamp, state |
| `reset_session()` | Clears all session counters |
| `get_avg_blink_interval()` | No blinks → None, 1 blink → None, normal blinks → correct mean, outlier filtering |
| `load_settings()` / `save_settings()` | Round-trip with tmp file (mock `settings_path`) |

### Files
| Action | File |
|--------|------|
| NEW | `tests/test_state.py` (~10 test functions) |

---

## Task 4.7 — Update Build Pipeline

### Problem
`build.bat` was created before Phase 3 refactoring. New modules (`session.py`, `ui/cards/*`) need to be discoverable via `--hidden-import`.

### Plan
Add these hidden imports to both PyInstaller commands:
```
--hidden-import=blink_guard.session
--hidden-import=blink_guard.ui.cards
--hidden-import=blink_guard.ui.cards._base
--hidden-import=blink_guard.ui.cards.card_alert
--hidden-import=blink_guard.ui.cards.card_startup
--hidden-import=blink_guard.ui.cards.card_journey
--hidden-import=blink_guard.ui.cards.card_dnd
--hidden-import=blink_guard.ui.cards.card_camera
--hidden-import=blink_guard.ui.cards.card_about
```

### Files
| Action | File |
|--------|------|
| MODIFY | `build.bat` | Add hidden imports for new modules |

---

## Execution Order

```
4.1 (infrastructure)  ← first, everything depends on it
4.2 (adaptive tests)  ← after 4.1
4.3 (risk tests)      ← after 4.1 (parallel with 4.2)
4.4 (dnd tests)       ← after 4.1 (parallel)
4.5 (defaults tests)  ← after 4.1 (parallel)
4.6 (state tests)     ← after 4.1 (parallel)
4.7 (build.bat)       ← independent, do last
```

Order: **4.1 → 4.2+4.3+4.4+4.5+4.6 → 4.7**

---

## Verification Plan

```bash
# Run all tests with coverage
pytest tests/ -v --tb=short --cov=blink_guard --cov-report=term-missing

# Target: ≥90% coverage on adaptive.py, risk.py, dnd.py, defaults.py
```

---

## Dependencies
- `pytest` and `pytest-cov` will be added to the dev environment
- No new production dependencies

---

**Ready to execute.** Run `/gsd:execute-phase 4` to begin.
