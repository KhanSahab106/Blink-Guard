# Phase 4: Tests & Distribution — Execution Plan

## Overview
**Goal:** Add automated test coverage on all pure-logic modules, integration tests for `state.py`, and ensure the PyInstaller build produces working executables that correctly import the new Phase 3 modules.

**Exit criteria:**
- `pytest` passes with ≥90% coverage on `adaptive.py`, `risk.py`, `dnd.py`, `defaults.py`
- Integration tests verify `SharedState` lifecycle (load → mutate → save → reload)
- `build.bat` includes hidden imports for new modules (`session`, `cards/*`)
- Clean build produces two working executables

---

## Task 4.1 — Test Infrastructure

### Plan
Create `pyproject.toml` with pytest + coverage config, a `tests/conftest.py` with common fixtures (temp settings dir, pre-built `SharedState`), and install test deps.

### Files
| Action | File | Contents |
|--------|------|----------|
| NEW | `pyproject.toml` | `[project]` metadata + `[tool.pytest.ini_options]` + `[tool.coverage]` |
| NEW | `tests/__init__.py` | Package marker |
| NEW | `tests/conftest.py` | Fixtures: `tmp_settings_dir`, `fresh_settings`, `shared_state` |

### Key fixtures
```python
@pytest.fixture
def tmp_settings_dir(tmp_path, monkeypatch):
    """Redirect settings_path() to a temp directory."""
    monkeypatch.setattr("blink_guard.defaults.settings_path",
                        lambda: str(tmp_path / "settings.json"))
    return tmp_path

@pytest.fixture
def fresh_settings(tmp_settings_dir):
    """Return a default settings dict (already backed by tmp dir)."""
    from blink_guard.defaults import apply_defaults
    return apply_defaults({})
```

---

## Task 4.2 — Unit Tests: adaptive.py

### Functions to test
| Function | Test cases |
|----------|------------|
| `compute_baseline` | Normal intervals, all outliers (>30s → MAX), empty list, single item, mixed with outliers |
| `compute_threshold` | Mid-progress, 0 sessions, at completion, total_planned=0 |
| `get_total_sessions` | Healthy baseline (≤5 → 7), unhealthy (>5 → 14) |
| `should_count_session` | 4.9min → False, 5.0min → True, 60min → True |
| `update_phase` | OBSERVING→ACTIVE (baseline set), ACTIVE→MAINTENANCE (sessions met), MAINTENANCE→WEAN_OFF (maintenance met), stays in each phase when criteria not met |

### File
| Action | File |
|--------|------|
| NEW | `tests/test_adaptive.py` (~120 lines) |

---

## Task 4.3 — Unit Tests: risk.py

### Functions to test
| Function | Test cases |
|----------|------------|
| `compute_risk_score` | Null threshold → (0, Low), low interval/alerts → Low band, high values → Severe, duration penalties at 30/60/120+ min |
| `get_band` | Boundary values: 0, 25, 26, 50, 75, 100 |

### File
| Action | File |
|--------|------|
| NEW | `tests/test_risk.py` (~60 lines) |

---

## Task 4.4 — Unit Tests: dnd.py

### Functions to test
| Function | Test cases |
|----------|------------|
| `validate_rule` | Valid rule → None, no days → error, invalid day → error, bad time format → error, start ≥ end → error |
| `is_dnd_active` | DND disabled → False, no schedule → False, matching day+time → True, non-matching day → False, outside time window → False |

### File
| Action | File |
|--------|------|
| NEW | `tests/test_dnd.py` (~80 lines) |

For `is_dnd_active` we'll use `freezegun` or `monkeypatch` on `datetime.datetime.now()` to control the "current" time deterministically.

---

## Task 4.5 — Unit Tests: defaults.py

### Functions to test
| Function | Test cases |
|----------|------------|
| `apply_defaults` | Empty dict → all defaults present, partial dict → missing filled, existing values preserved |
| `validate_settings` | Correct types → no warnings, wrong type → warning + reset to default |
| `prune_session_history` | Under cap → 0 pruned, over cap → trimmed to 365 |
| `load_settings_from_disk` | Missing file → defaults, valid file → loaded, corrupt JSON → defaults |
| `save_settings_to_disk` | Round-trip: save → load → identical |

### File
| Action | File |
|--------|------|
| NEW | `tests/test_defaults.py` (~90 lines) |

---

## Task 4.6 — Integration Tests: state.py

### Scenarios to test
| Scenario | Assertions |
|----------|------------|
| `SharedState()` constructor | All attrs initialized, correct types |
| `record_blink()` | Increments count, appends timestamp, updates state |
| `reset_session()` | Clears all per-session counters |
| `load_settings()` → `save_settings()` round-trip | Settings persist to disk and reload identically |
| `get_avg_blink_interval()` | With <2 blinks → None, normal → correct average, outliers (>30s) discarded |

### File
| Action | File |
|--------|------|
| NEW | `tests/test_state.py` (~100 lines) |

---

## Task 4.7 — Update PyInstaller Build

### Problem
Phase 3 added new modules that PyInstaller may not auto-discover:
- `blink_guard.session`
- `blink_guard.ui.cards._base`
- `blink_guard.ui.cards.card_alert` (and 5 more card modules)

### Plan
Update `build.bat` to add `--hidden-import` for all new modules.

### Files
| Action | File | Change |
|--------|------|--------|
| MODIFY | `build.bat` | Add hidden imports for `session`, `defaults`, and `ui.cards.*` |

---

## Execution Order

```
4.1 (Infrastructure)     ← creates pyproject.toml, conftest.py
4.2 (test_adaptive.py)   ← pure logic, no deps
4.3 (test_risk.py)       ← pure logic, no deps
4.4 (test_dnd.py)        ← needs datetime mock
4.5 (test_defaults.py)   ← needs tmp_settings_dir fixture
4.6 (test_state.py)      ← needs tmp_settings_dir fixture
4.7 (build.bat update)   ← independent
```

Linear order: **4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6 → 4.7**

Then run `pytest --cov=blink_guard --cov-report=term-missing` to verify.

---

## Dependencies to Install
```
pip install pytest pytest-cov freezegun
```
(`freezegun` for deterministic datetime mocking in DND tests)

---

## Expected Coverage

| Module | Target | Rationale |
|--------|--------|-----------|
| `adaptive.py` | ≥95% | Pure functions, easily testable |
| `risk.py` | ≥95% | Pure functions, small module |
| `dnd.py` | ≥90% | Needs time mocking but straightforward |
| `defaults.py` | ≥90% | File I/O + validation, easy to test with tmp_path |
| `state.py` | ≥80% | Thread-safe helpers, save/load integration |

---

**Ready to execute.** Run `/gsd:execute-phase 4` to begin.
