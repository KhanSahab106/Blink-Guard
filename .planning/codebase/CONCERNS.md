# Concerns & Technical Debt

## 🔴 Critical
1. **No settings schema validation** — `settings.json` is a raw dict. Corrupt or missing keys will cause silent bugs or crashes. Any code change that adds a new setting must manually handle the "key doesn't exist yet" case everywhere.
2. **`hasattr()` anti-pattern** — Dynamic attributes on `SharedState` (`ear_left`, `escalation_level`, etc.) are set in `main.py` but checked with `hasattr()` in `detector.py`. If `main.py` changes, these silently become dead code.
3. **No automated tests** — Zero test coverage. Pure-logic modules (`adaptive.py`, `risk.py`, `dnd.py`) are easy to test but aren't. Regression risk is high.

## 🟡 Moderate
4. **`SettingsTab` is a god object** — 970 lines, 46 graph edges. It handles alert settings, calibration, DND schedule, phase management, camera selection, and appearance. Should be decomposed into separate card components.
5. **`main.py` does too much** — Entry point also contains session finalization logic, IPC callback construction, calibration launching, and the session prompt dialog. These should be extracted.
6. **Unbounded `session_history`** — Every session appends a record to `settings.json`. After months of use, this list grows indefinitely. No archiving or pruning strategy.
7. **TCP port collision** — IPC uses hardcoded port 57821. No fallback if the port is occupied. Two instances of BlinkGuard will conflict silently.
8. **Base64 frame encoding** — Camera frames sent over IPC as base64 JPEG. Adds ~33% bandwidth overhead. Fine for localhost but wasteful.

## 🟢 Minor
9. **Inconsistent settings path** — `_settings_path()` is duplicated in `state.py` and every `ui/tab_*.py` file (each has its own `_settings_path()` and `_load_settings()`). Single source of truth needed.
10. **No graceful camera recovery** — If the webcam disconnects mid-session, `cap.read()` returns `(False, None)` and the loop just `continue`s forever. No user notification.
11. **Wean-off phase has no exit** — `WEAN_OFF` stays "as-is indefinitely" (comment in code). No completion criteria or celebration moment.
12. **Weekly summary uses `win10toast`** — This library is unmaintained (last release 2020). May break on future Windows versions.

## Architecture Risks
- **Windows-only lock-in** — pywin32, winreg, DSHOW camera backend. Cross-platform would require significant abstraction.
- **Single-threaded UI** — Dashboard uses CustomTkinter's main loop. Heavy operations (chart rendering, settings reload) can cause UI freezes.
- **No migration system** — If `settings.json` schema changes between versions, there's no upgrade path. Old settings files may silently break.
