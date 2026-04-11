# BlinkGuard — Roadmap

## Phase 1: Foundation & Critical Fixes
**Goal:** Make the app stable and safe to build on. Fix the bugs that will bite us later.

| # | Task | Req | Files |
|---|------|-----|-------|
| 1.1 | Settings schema validation + defaults | R1.1 | `state.py`, new `defaults.py` |
| 1.2 | Move dynamic attrs into SharedState constructor | R1.2 | `state.py`, `main.py`, `detector.py` |
| 1.3 | Centralize `_settings_path()` | R1.3 | `state.py`, `ui/tab_*.py` |
| 1.4 | Bound session history (cap at 365) | R1.4 | `state.py` |
| 1.5 | Add version string | R5.2 | `__init__.py`, `ui/app.py`, `tray.py` |

**Exit criteria:** App starts, runs a session, and saves settings without any silent failures. All settings have documented defaults.

---

## Phase 2: New Features
**Goal:** Deliver the two user-requested features.

| # | Task | Req | Files |
|---|------|-----|-------|
| 2.1 | Sleep/wake session reset | R2.1 | `main.py`, `state.py` |
| 2.2 | Tray double-click opens dashboard | R2.2 | `tray.py` |
| 2.3 | Prevent duplicate dashboard instances | R2.2 | `tray.py`, `dashboard.py` |
| 2.4 | IPC port fallback | R5.3 | `ipc.py` |

**Exit criteria:** Closing laptop lid + reopening starts a fresh session. Double-clicking the tray icon opens the dashboard. No duplicate dashboards.

---

## Phase 3: Refactor
**Goal:** Clean up god objects and reduce coupling for future scalability.

| # | Task | Req | Files |
|---|------|-----|-------|
| 3.1 | Decompose SettingsTab into card components | R3.1 | `ui/tab_settings.py` → `ui/cards/*.py` |
| 3.2 | Extract session logic from main.py | R3.2 | `main.py` → `session.py` |
| 3.3 | Move IPC callbacks into ipc.py | R3.2 | `main.py`, `ipc.py` |
| 3.4 | Camera disconnect recovery | R3.3 | `detector.py` |

**Exit criteria:** No file exceeds 400 lines. `main.py` is <200 lines. SettingsTab is a thin container for card widgets.

---

## Phase 4: Tests & Distribution
**Goal:** Add test coverage and ensure clean release packaging.

| # | Task | Req | Files |
|---|------|-----|-------|
| 4.1 | Test infrastructure (pytest, conftest, CI) | R4.3 | `tests/conftest.py`, `pyproject.toml` |
| 4.2 | Unit tests: adaptive.py | R4.1 | `tests/test_adaptive.py` |
| 4.3 | Unit tests: risk.py | R4.1 | `tests/test_risk.py` |
| 4.4 | Unit tests: dnd.py | R4.1 | `tests/test_dnd.py` |
| 4.5 | Integration tests: ipc.py | R4.2 | `tests/test_ipc.py` |
| 4.6 | Integration tests: state.py | R4.2 | `tests/test_state.py` |
| 4.7 | Clean PyInstaller build + smoke test | R5.1 | `build.bat`, `.spec` files |

**Exit criteria:** `pytest --cov` shows ≥90% on `adaptive.py`, `risk.py`, `dnd.py`. PyInstaller build produces working executables.

---

## Summary

```
Phase 1 (Foundation)     ████░░░░░░░░  ~5 tasks
Phase 2 (Features)       ░░░░░░░░░░░░  ~4 tasks
Phase 3 (Refactor)       ░░░░░░░░░░░░  ~4 tasks
Phase 4 (Tests & Ship)   ░░░░░░░░░░░░  ~7 tasks
```

**Next action:** `/gsd:plan-phase 1`
