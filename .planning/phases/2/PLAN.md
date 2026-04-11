# Phase 2: New Features — Execution Plan

## Overview
**Goal:** Deliver the two user-requested features: sleep/wake session reset and dashboard access from the system tray.

**Exit criteria:** Closing the laptop lid + reopening starts a fresh session. Double-clicking the tray icon opens the dashboard. No duplicate dashboard instances. IPC port handles conflicts.

---

## Task 2.1 — Sleep/Wake Session Reset

### Problem
When the machine sleeps and wakes, the current session continues with stale data. The user expects a fresh session to start automatically after waking up.

### How It Works Now
`_start_session_watcher()` in `main.py:86-147` creates a hidden Win32 window registered for `WTS_SESSION_LOCK`/`WTS_SESSION_UNLOCK` events. On lock → pause detector. On unlock → resume detector. **Sleep/wake events are not handled at all.**

### Plan
Extend the existing `_wnd_proc` to also handle `WM_POWERBROADCAST`:

```python
WM_POWERBROADCAST = 0x0218
PBT_APMSUSPEND = 0x0004          # System is suspending
PBT_APMRESUMEAUTOMATIC = 0x0012  # System woke up

def _wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_WTSSESSION_CHANGE:
        # ... existing lock/unlock logic ...
    elif msg == WM_POWERBROADCAST:
        if wparam == PBT_APMSUSPEND:
            logger.info("System suspending — pausing detector.")
            shared.set_detector_state(DetectorState.PAUSED)
        elif wparam == PBT_APMRESUMEAUTOMATIC:
            logger.info("System woke from sleep — resetting session.")
            _on_wake_reset(shared)
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
```

The `_on_wake_reset(shared)` function will:
1. Finalize the current session (call `_finalise_session(shared)`)
2. Reset session counters on SharedState:
   - `session_start_time = time.time()`
   - `session_blink_count = 0`
   - `session_alerts_fired = 0`
   - `blink_timestamps = []`
   - `last_blink_time = time.time()`
   - `escalation_level = 0`
   - `escalation_counts = {}`
   - `consecutive_misses = 0`
3. Resume the detector: `shared.set_detector_state(DetectorState.WATCHING)`
4. Log clearly: "Session reset after wake — new session started"

Add a `reset_session()` helper to `SharedState` in `state.py` to encapsulate this.

### Files
| Action | File | Change |
|--------|------|--------|
| MODIFY | `blink_guard/state.py` | Add `reset_session()` method |
| MODIFY | `blink_guard/main.py` L86-147 | Add `WM_POWERBROADCAST` handling + `_on_wake_reset()` |

### Verification
- Put laptop to sleep → wake up → check `blinkguard.log` for "System woke from sleep" message
- Verify session_history in settings.json has a new record for the pre-sleep session

---

## Task 2.2 — Tray Double-Click Opens Dashboard

### Problem
Currently, only the right-click menu item "Open Dashboard" opens the dashboard. Double-clicking the tray icon does nothing (pystray default behavior).

### Plan
pystray doesn't natively support double-click, but it does have an `on_activate` parameter — the function called when the default menu item is activated (single left click or double click, depending on platform). On Windows, this is the double-click action.

We can either:
- **Option A:** Set a default menu item with `default=True` on the "Open Dashboard" item — pystray will run its callback on double-click
- **Option B:** Pass the callback directly when creating the Icon

**Chosen: Option A** — it's the documented pystray pattern.

```python
Item("📊 Open Dashboard", lambda icon, _: _open_dashboard(), default=True, visible=False),
Item("📊 Open Dashboard", lambda icon, _: _open_dashboard()),
```

The first item is invisible but marked `default=True` — it fires on tray double-click. The second item stays visible in the menu as before.

Actually, the simpler approach: just set `default=True` on the existing visible item.

```python
Item("📊 Open Dashboard", lambda icon, _: _open_dashboard(), default=True),
```

### Files
| Action | File | Change |
|--------|------|--------|
| MODIFY | `blink_guard/tray.py` L196 | Add `default=True` to the Dashboard menu item |

### Verification
- Double-click tray icon → dashboard opens
- Right-click → "Open Dashboard" still works

---

## Task 2.3 — Prevent Duplicate Dashboard Instances

### Problem
Every click of "Open Dashboard" spawns a new process. If the user clicks it 5 times, they get 5 dashboard windows.

### Plan
Use a named mutex (Windows) to detect if a dashboard instance is already running:

1. **In `dashboard.py`** — Before launching the GUI, try to acquire a named mutex
2. If the mutex already exists → another instance is running → try to bring it to front, or just exit
3. If the mutex is acquired → proceed normally

```python
# dashboard.py
import ctypes

def _acquire_single_instance() -> bool:
    """Try to acquire a named mutex. Returns True if we're the first instance."""
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, "BlinkGuardDashboard_SingleInstance")
    return ctypes.GetLastError() != 183  # ERROR_ALREADY_EXISTS
```

Also update `_open_dashboard()` in `tray.py` to communicate with the open dashboard via IPC before spawning a new one — but since the dashboard is a client not a server, a simpler approach is the mutex.

### Files
| Action | File | Change |
|--------|------|--------|
| MODIFY | `blink_guard/dashboard.py` | Add mutex-based single-instance check |

### Verification
- Click "Open Dashboard" → opens
- Click again → does NOT open a second window
- Close dashboard → click again → opens normally

---

## Task 2.4 — IPC Port Fallback

### Problem
If port 57821 is occupied (e.g., two BlinkGuard instances or another app), the IPC server silently fails and the dashboard can never connect.

### Plan
1. Try ports 57821-57825 in `IPCServer._serve()`
2. Write the active port to a lock file (`blinkguard.port` next to settings.json)
3. `IPCClient.connect()` reads the lock file to discover the port
4. Clean up the lock file on server stop

```python
# ipc.py
IPC_PORTS = [57821, 57822, 57823, 57824, 57825]

def _find_available_port() -> int | None:
    for port in IPC_PORTS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((IPC_HOST, port))
            sock.close()
            return port
        except OSError:
            continue
    return None
```

### Files
| Action | File | Change |
|--------|------|--------|
| MODIFY | `blink_guard/ipc.py` | Port fallback + lock file write/read |
| MODIFY | `blink_guard/defaults.py` | Add `port_file_path()` helper |

### Verification
- Start BlinkGuard → `blinkguard.port` file created with port number
- Block port 57821 → start BlinkGuard → uses 57822
- Dashboard connects via lock file discovery

---

## Execution Order

```
2.1 (sleep/wake)     ← independent, high value
2.2 (tray dblclick)  ← independent, trivial, 1 line
2.3 (duplicate guard) ← independent
2.4 (IPC port)       ← independent
```

All 4 tasks are independent and can be done in any order. I'll do them sequentially for clean commits.

---

## Risk Assessment
| Risk | Mitigation |
|------|------------|
| `_finalise_session` during wake might crash if session had no data | Guard with `try/except` + check `session_blink_count > 0` before recording |
| pystray `default=True` doesn't work on all platforms | We're Windows-only — tested on Windows 10/11 |
| Named mutex not released on crash | Mutex is released automatically when the process dies — Windows handles this |
| Port lock file becomes stale after crash | IPCClient should try the lock file port first, then fall back to scanning all ports |

---

**Ready to execute.** Run `/gsd:execute-phase 2` to begin.
