# BlinkGuard — Product Requirements Document (PRD)

**Version:** 1.0  
**Date:** April 11, 2026  
**Author:** Abrar  
**Status:** Active Development

---

## 1. Executive Summary

**BlinkGuard** is a Windows desktop application that monitors the user's blink rate via webcam in real-time and uses an adaptive conditioning algorithm to gradually train healthier blinking habits. The application runs silently in the system tray, analyzing eye blinks using computer vision, and delivers gentle, escalating audio alerts when the user goes too long without blinking — a common cause of digital eye strain.

All processing is performed locally on the user's device. **No data is ever transmitted externally**, ensuring full privacy.

---

## 2. Problem Statement

Prolonged screen use causes a significant reduction in blink rate — from the natural ~15–20 blinks/minute to as low as 3–5 blinks/minute. This leads to:

- **Dry eye syndrome** — insufficient tear film replenishment
- **Eye strain and fatigue** — headaches, blurred vision, irritation
- **Long-term corneal damage** — from chronic dryness

Existing solutions (e.g., the 20-20-20 rule) rely on static timers that don't adapt to individual blink patterns. Users ignore or disable them because the reminders feel arbitrary and disruptive.

---

## 3. Target Users

| Persona | Description |
|---|---|
| **Knowledge Workers** | Spend 6–10+ hours daily on screens (developers, writers, analysts) |
| **Gamers** | Extended sessions with high visual focus and suppressed blinking |
| **Students** | Long study/reading sessions with digital material |
| **Remote Workers** | Video calls and continuous screen time without natural breaks |

**Platform:** Windows 10/11 (desktop only)

---

## 4. Product Vision

> *Train your eyes to blink naturally — then get out of the way.*

BlinkGuard is **not** a permanent crutch. It follows a scientifically-grounded adaptive conditioning model:

1. **Observe** the user's natural blink rate (baseline)
2. **Actively train** toward a healthier target through progressive thresholds
3. **Maintain** the habit with gentle reinforcement
4. **Wean off** alerts as the habit becomes autonomous

---

## 5. Core Features

### 5.1 Real-Time Blink Detection

| Attribute | Detail |
|---|---|
| **Technology** | MediaPipe Face Mesh (468+ landmarks) |
| **Metric** | Eye Aspect Ratio (EAR) — per-eye and averaged |
| **Detection Method** | Consecutive-frame state machine (≥2 frames below threshold) |
| **Camera** | Default webcam via OpenCV (640×480, ~30 fps) |
| **Grace Period** | 0.3s post-blink to suppress double counting |
| **Calibration** | First-launch wizard tunes EAR thresholds to individual eye geometry |

### 5.2 Adaptive Conditioning Algorithm

The core algorithm operates in **four phases**:

```
┌────────────┐     ┌────────┐     ┌─────────────┐     ┌──────────┐
│  OBSERVING │────▸│ ACTIVE │────▸│ MAINTENANCE │────▸│ WEAN-OFF │
│  (2 sess.) │     │ (7-14) │     │   (7 sess.) │     │(ongoing) │
└────────────┘     └────────┘     └─────────────┘     └──────────┘
```

| Phase | Sessions | Behavior |
|---|---|---|
| **Observing** | 2 | Silent data collection. Computes personal baseline interval. |
| **Active** | 7–14 (depends on baseline) | Linear threshold interpolation from baseline → target (4s). Alerts when exceeded. |
| **Maintenance** | 7 | Holds at target threshold. Validates habit stability. |
| **Wean-Off** | Ongoing | Reduces alert frequency. Only fires after 2+ consecutive misses. |

**Key constants:**
- Default target: **4.0 seconds** between blinks
- Baseline range: 1.0–25.0 seconds (outliers >30s discarded)
- Short plan (baseline ≤5s): 7 sessions
- Long plan (baseline >5s): 14 sessions
- Minimum session length to count: 5 minutes

### 5.3 Three-Level Alert Escalation

Alerts escalate gently to avoid being jarring:

| Level | Sound | Frequency | Duration | Volume | Delay |
|---|---|---|---|---|---|
| L1 — Soft | Sine beep | 440 Hz | 150ms × 1 | 50% of base | Immediate |
| L2 — Medium | Sine beep | 550 Hz | 200ms × 1 | 75% of base | +2s after L1 |
| L3 — Urgent | Sine beep | 660 Hz | 300ms × 2 | 100% of base | +2s after L2 |

- Alerts reset on blink detection.
- Custom `.wav` / `.mp3` sounds supported (max 5 MB).
- Suppressed during DND windows but detection continues.

### 5.4 System Tray Integration

The background process lives in the Windows system tray with a programmatically generated eye icon. Right-click menu includes:

- **Live stats** — current phase, avg interval, threshold, progress percentage
- **DND status** indicator
- **Alert escalation** level indicator
- **Open Dashboard** — launches the dashboard UI
- **Pause / Resume** toggle
- **Sound On/Off** toggle
- **Start with Windows** toggle (via `HKCU\...\Run` registry key)
- **Quit**

### 5.5 Dashboard UI

A standalone **CustomTkinter** dark-themed desktop application that communicates with the background process via TCP IPC (`localhost:57821`). The dashboard features four tabs:

| Tab | Description |
|---|---|
| **Live** | Real-time camera preview with face detection overlays, live EAR graph, blink counter, alert level, DND indicator |
| **History** | Session history table, per-session stats, filterable/sortable |
| **Progress** | Phase progress visualization, threshold trajectory chart, time-of-day blink heatmap, eye strain risk scoring |
| **Settings** | EAR calibration, sound options, DND schedule editor, camera selection, volume control, startup toggle, phase management |

### 5.6 Calibration Wizard

A first-launch calibration wizard that:

1. Guides the user through open-eye and blink-eye calibration frames
2. Computes personal `ear_blink_threshold` and `ear_open_threshold`
3. Saves calibration status and date to `settings.json`
4. Can be re-triggered from Settings tab

### 5.7 Do Not Disturb (DND)

- Configurable weekly schedule (per-day, HH:MM start/end)
- Suppresses audio alerts only — detection and data collection continue
- Status visible in system tray and dashboard
- Validated rule format (day names, time ordering)

### 5.8 Eye Strain Risk Scoring

Post-session risk score (0–100) based on:

| Factor | Weight |
|---|---|
| Interval ratio (avg / threshold) | 50% |
| Alert rate (alerts/minute) | 30% |
| Session duration penalty | 0–25 pts |

| Score | Band | Color |
|---|---|---|
| 0–25 | Low | 🟢 Green |
| 26–50 | Moderate | 🟡 Yellow |
| 51–75 | High | 🟠 Orange |
| 76–100 | Severe | 🔴 Red |

### 5.9 Weekly Summary Cards

Auto-generated **800×450 PNG** report cards every Monday containing:

- Session count, total blinks, avg interval, alerts fired
- Best/worst session of the week
- 7-day bar chart (color-coded by risk threshold)
- Phase badge and improvement streak
- Threshold improvement delta
- Delivered via **Windows toast notification**
- Stored in `%APPDATA%/BlinkGuard/summaries/` (last 52 weeks retained)

### 5.10 Session Lifecycle

```
User Launch
    │
    ▼
Session Prompt (Start / Not Now)
    │
    ▼
Calibration Wizard (first run only)
    │
    ▼
┌─────────────────────────────────────────────┐
│  Background Threads:                        │
│    • Thread 1: Camera + MediaPipe detector  │
│    • Thread 2: Periodic settings saver (60s)│
│    • Thread 3: Windows session watcher      │
│    • Thread 4: IPC server                   │
│  Main Thread: pystray system tray           │
└─────────────────────────────────────────────┘
    │
    ▼ (Quit from tray)
End-of-Session Processing
    • Compute risk score
    • Record session to history
    • Update hourly data
    • Phase transition check
    • Weekly summary check
    • Save final settings
```

---

## 6. Technical Architecture

### 6.1 Module Breakdown

| Module | Responsibility |
|---|---|
| `main.py` | Entry point — wires threads, session prompt, calibration, IPC callbacks, shutdown |
| `detector.py` | Camera loop, MediaPipe EAR blink detection, escalation alerts, DND checks |
| `state.py` | Thread-safe `SharedState` container, settings persistence, phase/detector enums |
| `adaptive.py` | Baseline computation, threshold interpolation, phase transition logic |
| `alerts.py` | Pygame mixer init, sine beep generation, multi-level playback, custom sound support |
| `tray.py` | pystray icon + menu with live stats, toggles, dashboard launcher |
| `dashboard.py` | Dashboard entry point (CustomTkinter) |
| `ipc.py` | TCP socket server/client for background ↔ dashboard communication |
| `dnd.py` | Do Not Disturb schedule validation and checking |
| `risk.py` | Eye strain risk score computation (0–100) |
| `weekly.py` | Weekly summary PNG generation + toast notification |
| `startup.py` | Windows registry startup management (`HKCU\...\Run`) |
| `ui/app.py` | Dashboard main window with tabbed layout |
| `ui/tab_live.py` | Live monitoring tab (camera preview, EAR chart, blink stats) |
| `ui/tab_history.py` | Session history tab |
| `ui/tab_progress.py` | Progress tracking tab (phase, heatmap, risk) |
| `ui/tab_settings.py` | Settings tab (calibration, sound, DND, etc.) |
| `ui/calibration.py` | Calibration wizard UI |

### 6.2 Inter-Process Communication

```
┌──────────────────┐         TCP :57821          ┌──────────────────┐
│  BlinkGuard.exe  │◄──── JSON over newline ────►│ Dashboard.exe    │
│  (background)    │                              │ (CustomTkinter)  │
│                  │  Commands:                   │                  │
│  IPCServer       │   GET_LIVE_STATE             │  IPCClient       │
│                  │   GET_CAMERA_FRAME (base64)  │                  │
│                  │   SET_SETTING {key, value}   │                  │
│                  │   PAUSE / RESUME             │                  │
└──────────────────┘                              └──────────────────┘
```

### 6.3 Data Persistence

All data is stored in a single `settings.json` file co-located with the executable:

```json
{
  "calibrated": false,
  "ear_blink_threshold": 0.20,
  "ear_open_threshold": 0.35,
  "baseline_interval": null,
  "sessions_completed": 0,
  "total_sessions_planned": 14,
  "target_threshold": 4.0,
  "current_threshold": null,
  "phase": "observing",
  "sound_enabled": true,
  "launch_on_startup": true,
  "dnd_enabled": false,
  "dnd_schedule": [],
  "hourly_data": {},
  "session_history": [],
  "weekly_summaries": [],
  "volume": 75
}
```

### 6.4 Windows Integration

| Feature | Implementation |
|---|---|
| **System Tray** | pystray with PIL-generated icon |
| **Startup** | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` registry key |
| **Lock/Unlock** | `WTSRegisterSessionNotification` via pywin32 (pauses on lock) |
| **Toast Notifications** | win10toast library |

---

## 7. Technology Stack

| Category | Technology | Version |
|---|---|---|
| Language | Python | 3.11+ |
| Computer Vision | OpenCV | 4.9.0 |
| Face Mesh | MediaPipe | 0.10.13 |
| System Tray | pystray | 0.19.5 |
| Audio | pygame | 2.5.2 |
| Dashboard UI | CustomTkinter | 5.2.2 |
| Charts | matplotlib | 3.8.4 |
| Image Processing | Pillow | 10.3.0 |
| Windows APIs | pywin32 | 306 |
| Notifications | win10toast | ≥0.9 |
| Numerics | numpy | ≥1.24.0 |
| Packaging | PyInstaller | 6.5.0 |

---

## 8. Distribution

### 8.1 Build Process

Two standalone executables are built via PyInstaller (`build.bat`):

| Executable | Description |
|---|---|
| `BlinkGuard.exe` | Background tray process (main entry) |
| `BlinkGuardDashboard.exe` | Dashboard UI (standalone) |

Both are `--onefile --noconsole` builds bundling MediaPipe models and CustomTkinter assets.

### 8.2 Distribution Package

```
dist/BlinkGuard/
├── BlinkGuard.exe
├── BlinkGuardDashboard.exe
├── settings.json
└── README.txt
```

---

## 9. Privacy & Security

- ✅ **Zero network access** — no data sent externally
- ✅ **Local-only processing** — camera frames processed in-memory, never saved to disk (except optional dashboard previews via IPC)
- ✅ **IPC on localhost only** — TCP server bound to `127.0.0.1`
- ✅ **No admin required** — registry writes use `HKEY_CURRENT_USER`
- ✅ **Minimal data footprint** — only aggregated statistics stored (no video/images)
- ✅ **Auto-cleanup** — weekly summaries capped at 52, hourly intervals capped at 500 per hour, EAR history capped at 100 entries

---

## 10. Non-Functional Requirements

| Requirement | Target |
|---|---|
| CPU usage (background) | < 5% on modern quad-core (detection throttled to ~30 fps with 0.03s sleep) |
| Memory usage | < 150 MB (MediaPipe model + OpenCV buffer) |
| Camera resolution | 640×480 (reduced for performance) |
| Settings save interval | 60 seconds (periodic) + on shutdown |
| IPC latency | < 50ms localhost |
| JPEG encoding | Every 3rd frame (~10 fps) at quality 60 |
| Startup time | < 3 seconds to tray (excluding calibration) |

---

## 11. Future Roadmap

| Priority | Feature | Description |
|---|---|---|
| P1 | **Multi-monitor support** | Detect which monitor the user is focused on |
| P1 | **macOS / Linux port** | Abstract platform-specific components (tray, startup, session events) |
| P2 | **Focus-mode integration** | Detect fullscreen apps and auto-adjust alert behavior |
| P2 | **Export data** | CSV/JSON export of session history for personal analytics |
| P2 | **Dark/Light theme toggle** | Dashboard theme switching |
| P3 | **Multiple user profiles** | Family/shared PC support with per-user baselines |
| P3 | **Smart break suggestions** | Combine blink data with session duration for break recommendations |
| P3 | **Accessibility** | Screen reader support, high-contrast mode, keyboard navigation |

---

## 12. Success Metrics

| Metric | Target |
|---|---|
| Avg blink interval reduction | ≥30% improvement from baseline after completing Active phase |
| Session completion rate | ≥70% of sessions ≥5 minutes |
| Phase completion | ≥50% of users reach Maintenance phase within 3 weeks |
| User retention | ≥60% still running BlinkGuard after 30 days |
| Alert dismiss rate | L1 alerts resolved (blink) within 2 seconds ≥80% of the time |

---

## 13. Glossary

| Term | Definition |
|---|---|
| **EAR** | Eye Aspect Ratio — ratio of vertical to horizontal eye distances, drops during blinks |
| **Baseline** | User's natural average inter-blink interval, measured during Observing phase |
| **Threshold** | Maximum allowed seconds between blinks before an alert fires |
| **Phase** | Current stage in the adaptive conditioning pipeline |
| **Escalation** | Progressive alert intensity (L1→L2→L3) when blink is overdue |
| **DND** | Do Not Disturb — scheduled silent periods |
| **IPC** | Inter-Process Communication between background and dashboard via TCP |
| **Session** | A single run of BlinkGuard from start to quit |
