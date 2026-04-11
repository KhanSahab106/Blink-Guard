# Architecture

## Overview
BlinkGuard is a **two-process Windows desktop application**:

1. **Background Process** (`main.py`) — Runs in the system tray. Captures webcam, detects blinks via MediaPipe, fires audio alerts, manages adaptive training phases.
2. **Dashboard Process** (`dashboard.py` → `ui/app.py`) — Standalone CustomTkinter GUI. Connects to the background process via TCP IPC to display live stats, history, and settings.

## Process Architecture

```
┌─────────────────────────────────────┐
│         Background Process          │
│                                     │
│  Main Thread    → pystray tray icon │
│  Thread 1       → Camera + MediaPipe│
│  Thread 2       → Periodic settings │
│  Thread 3       → Win32 session     │
│  Thread 4       → IPC TCP server    │
│                                     │
│         SharedState (mutex)         │
└──────────────┬──────────────────────┘
               │ TCP localhost:57821
               │ JSON-over-newline
┌──────────────▼──────────────────────┐
│         Dashboard Process           │
│                                     │
│  CustomTkinter main loop            │
│  IPCClient polls every 500ms        │
│  5 tabs: Live, Progress, History,   │
│          Settings, Calibration      │
└─────────────────────────────────────┘
```

## Data Flow

```
Camera → MediaPipe Face Mesh → EAR Calculation → Blink State Machine
                                                        │
                                          ┌─────────────┼──────────────┐
                                          ▼             ▼              ▼
                                     SharedState   Alert System   Hourly Data
                                          │
                                    settings.json (persistence)
                                          │
                                    Phase Engine (adaptive.py)
                                          │
                                ┌─────────┼──────────┐
                                ▼         ▼          ▼
                           OBSERVING → ACTIVE → MAINTENANCE → WEAN_OFF
```

## Key Design Decisions
1. **Thread-safe SharedState** — All cross-thread data goes through `SharedState` with a single mutex lock. Simple but effective for this scale.
2. **Two-process split** — Background runs headless (no GUI thread contention with OpenCV). Dashboard is a separate process so it can be opened/closed independently.
3. **JSON-over-TCP IPC** — Chosen over pipes/shared memory for simplicity. Supports camera frame transfer via base64 JPEG.
4. **Four-phase adaptive algorithm** — Observing → Active → Maintenance → Wean-off. Thresholds linearly interpolate from user's baseline toward a healthy target.
5. **Privacy-first** — All processing is local. No frames leave the machine. Camera frames are JPEG-encoded in-memory for the dashboard but never saved to disk.
