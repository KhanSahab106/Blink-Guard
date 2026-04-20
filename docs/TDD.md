# Technical Design Document (TDD)
## BlinkGuard — Adaptive Blink Rate Monitor
**Version:** 1.0.0 · **Date:** April 2026

---

## 1. System Overview

BlinkGuard is a dual-process Windows desktop application that uses computer vision to monitor blink rates and train healthier blinking habits through progressive conditioning.

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BlinkGuard System                            │
│                                                                     │
│  ┌──────────────────────────┐    TCP/IPC    ┌────────────────────┐  │
│  │   Background Process     │◄────────────►│   Dashboard UI      │  │
│  │   (BlinkGuard.exe)       │  port 57821+  │ (Dashboard.exe)     │  │
│  │                          │               │                     │  │
│  │  ┌──────────┐ ┌────────┐│               │ ┌─────────────────┐ │  │
│  │  │ Detector │ │ Tray   ││               │ │ Tab: Live       │ │  │
│  │  │ Thread   │ │ (Main) ││               │ │ Tab: Progress   │ │  │
│  │  ├──────────┤ ├────────┤│               │ │ Tab: History    │ │  │
│  │  │ Updater  │ │ IPC    ││               │ │ Tab: Settings   │ │  │
│  │  │ Thread   │ │ Server ││               │ │   └─ 6 Cards    │ │  │
│  │  ├──────────┤ ├────────┤│               │ ├─────────────────┤ │  │
│  │  │ Session  │ │ Power  ││               │ │ Calibration     │ │  │
│  │  │ Watcher  │ │ Events ││               │ │ Wizard          │ │  │
│  │  └──────────┘ └────────┘│               │ └─────────────────┘ │  │
│  └──────────────────────────┘               └────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    settings.json (shared)                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Process Model

| Process | Entry Point | Threads | Lifetime |
|---------|-------------|---------|----------|
| Background | `main.py:main()` | Main (tray), Detector, Updater, SessionWatcher, IPC | Persistent (system tray) |
| Dashboard | `dashboard.py:main()` | Main (Tk event loop), IPC client | On-demand (user-launched) |

### 1.3 Design Principles
1. **Privacy by architecture** — No network imports, no cloud APIs, no telemetry
2. **Thread safety via SharedState** — All shared data guarded by a single reentrant lock
3. **Module boundaries ≤400 lines** — Enforced by convention; verified in Phase 3 refactor
4. **Schema-driven settings** — `defaults.py` is the single source of truth for all configuration

---

## 2. Module Design

### 2.1 Module Dependency Graph

```
main.py
├── state.py (SharedState)
│   └── defaults.py (settings schema, load/save)
├── detector.py (camera + MediaPipe)
│   └── state.py
├── session.py (finalise, updater)
│   ├── state.py
│   ├── adaptive.py (baseline, threshold, phase)
│   ├── risk.py (risk scoring)
│   └── weekly.py (summary cards)
├── ipc.py (TCP server + callbacks)
│   └── state.py
├── tray.py (pystray system tray)
│   └── state.py
├── alerts.py (pygame sound)
├── startup.py (registry)
└── dnd.py (schedule logic)

dashboard.py
├── ipc.py (TCP client)
├── defaults.py
└── ui/
    ├── app.py (main window)
    ├── tab_live.py
    ├── tab_progress.py
    ├── tab_history.py
    ├── tab_settings.py
    │   └── cards/ (_base, alert, startup, journey, dnd, camera, about)
    └── calibration.py
```

### 2.2 Module Catalog

| Module | Lines | Role | Dependencies |
|--------|-------|------|-------------|
| `main.py` | 320 | Process lifecycle, thread orchestration | state, detector, tray, session, ipc, alerts, startup |
| `detector.py` | 319 | Camera capture, MediaPipe face mesh, blink detection, alert escalation | state, alerts, dnd |
| `state.py` | 183 | Thread-safe shared state container | defaults |
| `session.py` | 147 | Periodic saver + end-of-session finalization | state, adaptive, risk, weekly |
| `ipc.py` | 348 | TCP IPC server, client, callback factory | state (lazy import) |
| `tray.py` | 180 | System tray icon and menu | state |
| `adaptive.py` | 126 | Baseline computation, threshold interpolation, phase transitions | state (Phase enum only) |
| `defaults.py` | 155 | Settings schema, defaults, validation, persistence | — (leaf module) |
| `risk.py` | 73 | Eye strain risk score computation | — (leaf module) |
| `dnd.py` | 83 | DND schedule matching and validation | — (leaf module) |
| `alerts.py` | ~140 | pygame sound initialization and playback | — |
| `startup.py` | ~60 | Windows registry launch-on-startup | — |
| `weekly.py` | ~280 | Weekly summary card generation (matplotlib) | defaults |
| `dashboard.py` | ~80 | Dashboard entry point with mutex guard | ipc, ui, defaults |

---

## 3. Core Data Structures

### 3.1 SharedState (state.py)

The central thread-safe container. All mutable runtime data is stored here.

```python
class SharedState:
    # Threading
    lock: threading.Lock
    shutdown_event: threading.Event

    # Detector
    detector_state: DetectorState     # WATCHING | BLINK_DETECTED | FACE_NOT_VISIBLE | PAUSED
    ear_left: float                   # Current left EAR
    ear_right: float                  # Current right EAR
    ear_history: list[float]          # Rolling EAR window
    last_jpeg_frame: bytes | None     # Latest camera frame (JPEG)

    # Phase & Adaptive
    phase: Phase                      # OBSERVING | ACTIVE | MAINTENANCE | WEAN_OFF
    current_threshold: float | None   # Alert threshold (seconds)
    baseline_interval: float | None   # Computed baseline

    # Session Counters
    blink_timestamps: list[float]     # All blink timestamps (current session)
    last_blink_time: float
    session_start_time: float
    session_blink_count: int
    session_alerts_fired: int
    consecutive_misses: int

    # Alert State
    escalation_level: int             # 0-3
    escalation_counts: dict           # {"1": n, "2": n, "3": n}

    # DND
    dnd_active: bool
    dnd_end_time: str | None

    # Preferences (mirrored from settings)
    sound_enabled: bool
    launch_on_startup: bool

    # Persistence
    settings: dict                    # Full settings.json contents
```

**Thread safety protocol:**
- All reads/writes go through `with shared.lock:`
- Helper methods (`record_blink()`, `set_detector_state()`, etc.) encapsulate locking
- `save_settings()` takes a snapshot under lock, then writes outside the lock

### 3.2 Settings Schema (defaults.py)

All 22 settings keys with defaults and type constraints:

```python
SETTINGS_SCHEMA = {
    # Phase & Adaptive
    "phase":                   {"default": "observing",  "type": (str,)},
    "baseline_interval":       {"default": None,         "type": (float, int, NoneType)},
    "current_threshold":       {"default": None,         "type": (float, int, NoneType)},
    "sessions_completed":      {"default": 0,            "type": (int,)},
    "total_sessions_planned":  {"default": 14,           "type": (int,)},
    "target_threshold":        {"default": 4.0,          "type": (float, int)},
    "maintenance_sessions":    {"default": 0,            "type": (int,)},

    # User Preferences
    "sound_enabled":           {"default": True,         "type": (bool,)},
    "launch_on_startup":       {"default": True,         "type": (bool,)},
    "volume":                  {"default": 75,           "type": (int,)},
    "camera_index":            {"default": 0,            "type": (int,)},
    "show_landmarks":          {"default": True,         "type": (bool,)},

    # Calibration
    "calibrated":              {"default": False,        "type": (bool,)},
    "calibration_date":        {"default": None,         "type": (str, NoneType)},
    "ear_blink_threshold":     {"default": 0.2,          "type": (float, int)},
    "ear_open_threshold":      {"default": None,         "type": (float, int, NoneType)},

    # Alerts
    "alert_sound":             {"default": "default",    "type": (str,)},
    "custom_sound_path":       {"default": None,         "type": (str, NoneType)},

    # DND
    "dnd_enabled":             {"default": False,        "type": (bool,)},
    "dnd_schedule":            {"default": [],           "type": (list,)},

    # Data Containers
    "session_history":         {"default": [],           "type": (list,)},
    "hourly_data":             {"default": {},           "type": (dict,)},
}
```

### 3.3 Phase State Machine (adaptive.py)

```
                    baseline computed
  ┌──────────┐     ──────────────────►    ┌──────────┐
  │ OBSERVING│                            │  ACTIVE  │
  │ (2 sess) │                            │ (7-14 s) │
  └──────────┘                            └─────┬────┘
                                                │
                                    sessions ≥ planned
                                                │
                                          ┌─────▼────┐
                                          │MAINTENANCE│
                                          │  (7 sess) │
                                          └─────┬────┘
                                                │
                                    maintenance ≥ 7
                                                │
                                          ┌─────▼────┐
                                          │ WEAN_OFF │
                                          │(indefinite)│
                                          └──────────┘
```

**Threshold formula (Active phase):**
```
progress = min(sessions_completed / total_sessions_planned, 1.0)
threshold = baseline - (baseline - target) * progress
```

---

## 4. Threading Model

### 4.1 Background Process Threads

```
┌─────────Thread─────────┬──────────────Role─────────────────┬───────Lifetime────────┐
│ Main Thread            │ System tray (pystray event loop)  │ Process lifetime      │
│ Detector Thread        │ Camera capture + blink detection  │ daemon, until shutdown│
│ Updater Thread         │ Periodic settings save (60s)      │ daemon, until shutdown│
│ Session Watcher Thread │ Win32 power event listener        │ daemon, until shutdown│
│ IPC Server Thread      │ TCP server for dashboard commands │ daemon, until shutdown│
│ IPC Client Thread(s)   │ Per-connection handler            │ Connection lifetime   │
└────────────────────────┴───────────────────────────────────┴───────────────────────┘
```

### 4.2 Synchronization

- **Single lock pattern**: All threads share one `threading.Lock` via `SharedState.lock`
- **Shutdown coordination**: `threading.Event` (`shutdown_event`) signals all threads to exit
- **No deadlock risk**: Lock is never held across thread boundaries; all critical sections are short

### 4.3 Dashboard Process

Single-threaded Tk event loop with a 500ms polling timer (`after()`) that reads live state from the background process via IPC.

---

## 5. IPC Protocol

### 5.1 Transport
- TCP over localhost (127.0.0.1)
- Primary port: 57821; fallback: 57822-57825
- Port discovery via lock file (`blinkguard.port`)
- Newline-delimited JSON messages

### 5.2 Message Types

**Client → Server:**

| Command | Payload | Response |
|---------|---------|----------|
| `GET_LIVE_STATE` | — | Full state snapshot (dict) |
| `GET_CAMERA_FRAME` | — | `{"frame": "<base64 JPEG>"}` |
| `PAUSE` | — | `{"ok": true}` |
| `RESUME` | — | `{"ok": true}` |
| `SET_SETTING` | `{"key": "...", "value": ...}` | `{"ok": true}` or `{"error": "..."}` |
| `LAUNCH_CONFIRMED` | — | `{"ok": true}` |

### 5.3 Allowed Settings (via SET_SETTING)

```
sound_enabled, launch_on_startup, alert_volume, volume, camera_index,
ear_threshold, ear_blink_threshold, ear_open_threshold, show_landmarks,
total_sessions_planned, target_threshold, phase, baseline_interval,
sessions_completed, current_threshold, maintenance_sessions,
alert_sound, custom_sound_path, dnd_enabled, dnd_schedule,
calibrated, calibration_date
```

### 5.4 Port Discovery Protocol

1. Server attempts to bind ports 57821-57825 in order
2. On successful bind, writes the active port to `blinkguard.port`
3. Client reads `blinkguard.port` for the active port
4. If file is missing/stale, client scans all 5 ports

---

## 6. Blink Detection Algorithm

### 6.1 EAR Computation

For each eye, 6 landmark points are used:

```
    P2    P3
P1            P4
    P6    P5

EAR = (||P2-P6|| + ||P3-P5||) / (2 * ||P1-P4||)
```

- Open eye: EAR ≈ 0.25-0.35
- Closed eye: EAR ≈ 0.05-0.15
- Blink threshold (default): 0.20

### 6.2 Blink State Machine

```
     EAR ≥ threshold          EAR < threshold (≥2 frames)
  ┌──────────────────┐      ┌──────────────────────────┐
  │                  │      │                          │
  │    EYES_OPEN     ├─────►│     EYES_CLOSING         │
  │                  │      │  (frames_below counter)  │
  │                  │◄─────┤                          │
  └──────────────────┘      └──────────────────────────┘
         ▲                            │
         │        EAR ≥ threshold     │
         │    (after ≥2 frames below) │
         │                            ▼
         │                  ┌──────────────────┐
         └──────────────────┤  BLINK_DETECTED  │
              300ms grace   │  (record blink)  │
                            └──────────────────┘
```

### 6.3 Alert Escalation

```
No blink for > threshold → L1 alert (soft beep)
    └─ Still no blink after interval → L2 alert (medium)
        └─ Still no blink after interval → L3 alert (urgent, repeating)
```

Reset: Any valid blink resets escalation to L0.

---

## 7. Camera Recovery

### 7.1 Failure Detection
- Track `consecutive_read_fails` counter
- Trigger recovery after 30 consecutive frames fail (~1 second at 30fps)

### 7.2 Recovery Procedure
1. Set detector state to `PAUSED`
2. Release the current `cv2.VideoCapture`
3. Retry loop: up to 10 attempts, 3 seconds apart
4. On each attempt: create new `VideoCapture`, check `isOpened()`
5. If successful: reconfigure resolution, set state to `WATCHING`, reset counter
6. If all attempts fail: log error, stop detector thread (non-crashing exit)

### 7.3 Shutdown Awareness
- Each retry iteration checks `shutdown_event` to allow clean exit during recovery

---

## 8. UI Component Architecture

### 8.1 Dashboard Layout

```
┌──────────────────────────────────────────────────┐
│  [Live]  [Progress]  [History]  [Settings]       │  ← Tab bar
├──────────────────────────────────────────────────┤
│                                                  │
│              Active Tab Content                  │
│                                                  │
│                                                  │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 8.2 Settings Tab — Card Decomposition

`tab_settings.py` (53 lines) is a thin container that instantiates 6 cards:

| Card | File | Responsibility |
|------|------|---------------|
| AlertCard | `card_alert.py` (202 lines) | Sound toggle, volume, sound type, custom file, preview |
| StartupCard | `card_startup.py` (53 lines) | Launch on startup toggle + registry update |
| JourneyCard | `card_journey.py` (159 lines) | Sessions planned, target threshold, phase display, reset |
| DNDCard | `card_dnd.py` (202 lines) | DND toggle, rule list, add/delete rules form |
| CameraCard | `card_camera.py` (133 lines) | Camera index, EAR slider, landmarks, calibration |
| AboutCard | `card_about.py` (60 lines) | Version, privacy notice, log file shortcut |

All cards extend `BaseCard` (`_base.py`) which provides:
- Shared VS Code dark palette constants
- Row layout helper (`_make_row()`)
- Abstract `build()` and `refresh(settings)` methods

### 8.3 Theme Constants

```python
BG_DARK      = "#1e1e1e"    # Window background
SURFACE      = "#252526"    # Card background
ACCENT       = "#007acc"    # Interactive elements
ACCENT_HOVER = "#1a8ad4"    # Hover state
TEXT_PRIMARY = "#d4d4d4"    # Main text
TEXT_MUTED   = "#858585"    # Secondary text
BORDER       = "#3c3c3c"    # Dividers and borders
RED          = "#f44747"    # Errors, destructive actions
GREEN        = "#4ec94e"    # Success indicators
YELLOW       = "#e5c07b"    # Warnings
```

---

## 9. Risk Scoring Algorithm

### 9.1 Formula

```
interval_ratio = avg_blink_interval / current_threshold
alert_rate     = alerts_fired / max(session_duration_minutes, 0.1)

base_score = (interval_ratio × 50) + (alert_rate × 30)

duration_penalty:
  < 30 min  →  0
  30-60 min →  5
  60-120 min → 15
  > 120 min → 25

risk_score = clamp(base_score + duration_penalty, 0, 100)
```

### 9.2 Risk Bands

| Score | Band | Color | Interpretation |
|-------|------|-------|---------------|
| 0-25 | Low | `#4ec94e` | Healthy blink pattern |
| 26-50 | Moderate | `#e5c07b` | Slight strain risk |
| 51-75 | High | `#d19a66` | Take a break recommended |
| 76-100 | Severe | `#e06c75` | Immediate rest needed |

---

## 10. Build & Distribution

### 10.1 Build Process

`build.bat` invokes PyInstaller twice to create two `--onefile` executables:

1. **BlinkGuard.exe** — bundles `main.py` + all backend modules + mediapipe models + pystray
2. **BlinkGuardDashboard.exe** — bundles `dashboard.py` + UI modules + customtkinter + matplotlib

### 10.2 Hidden Imports

PyInstaller requires explicit `--hidden-import` for dynamically imported modules:
- `blink_guard.defaults`, `blink_guard.session`
- `blink_guard.dnd`, `blink_guard.risk`, `blink_guard.weekly`
- `blink_guard.ipc`, `blink_guard.ui.calibration`
- `blink_guard.ui.cards._base` + all 6 card modules
- `pystray._win32`, `PIL._tkinter_finder`
- `numpy`, `win10toast`, `matplotlib.backends.backend_tkagg`

### 10.3 Data Bundling

| Data | Source | Destination |
|------|--------|-------------|
| MediaPipe models | `mediapipe/modules/` | `mediapipe/modules/` |
| CustomTkinter assets | `customtkinter/` | `customtkinter/` |

---

## 11. Testing Strategy

### 11.1 Test Pyramid

```
          ┌────────┐
          │ Manual │  ← GUI, hardware, sound
          ├────────┤
       ┌──┤ Integr.│  ← SharedState lifecycle (test_state.py)
       │  ├────────┤
       │  │  Unit  │  ← Pure logic (adaptive, risk, dnd, defaults)
       └──┴────────┘
```

### 11.2 Coverage Targets

| Module | Target | Actual | Rationale |
|--------|--------|--------|-----------|
| `adaptive.py` | ≥95% | **100%** | Pure functions, critical algorithm |
| `risk.py` | ≥95% | **94%** | Pure functions |
| `dnd.py` | ≥90% | **100%** | Time-dependent but mockable |
| `defaults.py` | ≥85% | **85%** | File I/O + validation |
| `state.py` | ≥80% | **99%** | Thread-safe container |

### 11.3 Test Fixtures

| Fixture | Purpose |
|---------|---------|
| `tmp_settings_dir` | Redirect `settings_path()` to temp directory |
| `fresh_settings` | Default settings dict backed by temp dir |
| `shared_state` | Pre-initialized SharedState with temp settings |

---

## 12. Known Limitations

1. **Windows-only** — uses Win32 API (mutex, power broadcast, registry)
2. **Single webcam** — no multi-camera support
3. **No encrypted settings** — `settings.json` is plaintext (acceptable for personal use)
4. **MediaPipe model size** — bundled models add ~30MB to executable size
5. **No automatic updates** — user must manually replace executables
6. **DND no overnight support** — start time must be before end time (no cross-midnight rules)
