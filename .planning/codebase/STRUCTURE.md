# Project Structure

```
Blink_gaurd/
├── blink_guard/                    # Main application package
│   ├── __init__.py                 # Package marker (version string)
│   ├── main.py           (585L)   # Entry point — thread orchestration, calibration, session lifecycle
│   ├── state.py           (171L)   # SharedState, Phase/DetectorState enums, settings persistence
│   ├── detector.py        (358L)   # MediaPipe camera loop, EAR calculation, blink state machine
│   ├── adaptive.py        (126L)   # Baseline computation, threshold interpolation, phase transitions
│   ├── alerts.py          (168L)   # Pygame audio — 3-level escalation beeps, custom sounds
│   ├── ipc.py             (249L)   # TCP server/client for background ↔ dashboard communication
│   ├── tray.py            (224L)   # pystray system tray icon, menu, toggle callbacks
│   ├── risk.py             (73L)   # Eye strain risk score (0-100) computation
│   ├── dnd.py              (83L)   # Do Not Disturb schedule logic
│   ├── startup.py          (71L)   # Windows registry read/write for boot startup
│   ├── weekly.py          (300L)   # Weekly summary card PNG generation + toast notifications
│   ├── dashboard.py        (65L)   # Dashboard entry point (launches ui/app.py)
│   └── ui/                         # Dashboard GUI components
│       ├── __init__.py             # Package marker
│       ├── app.py         (340L)   # Main window — sidebar + tab navigation
│       ├── calibration.py (530L)   # First-launch calibration wizard
│       ├── tab_live.py    (400L)   # Live monitoring tab (camera feed, EAR chart)
│       ├── tab_progress.py(620L)   # Progress tab (journey ring, heatmap, charts)
│       ├── tab_history.py (510L)   # Session history tab (risk gauge, table)
│       └── tab_settings.py(970L)   # Settings tab (all configuration cards)
├── settings.json                   # User state + session history (runtime)
├── requirements.txt                # pip dependencies
├── build.bat                       # PyInstaller build script
├── BlinkGuardDashboard.spec        # PyInstaller spec for dashboard exe
├── PRD.md                          # Product Requirements Document
├── GEMINI.md                       # Graphify configuration
├── .gitignore                      # Git exclusions
├── .graphifyignore                 # Graphify exclusions (myenv/)
└── blinkguard.log                  # Rotating log file (runtime)
```

## Module Dependency Graph (simplified)

```
main.py ──→ state.py (SharedState, Phase, DetectorState)
       ──→ detector.py ──→ state.py, alerts.py, dnd.py
       ──→ tray.py ──→ state.py, startup.py
       ──→ alerts.py
       ──→ adaptive.py ──→ state.py
       ──→ ipc.py ──→ (callbacks from main)
       ──→ risk.py
       ──→ weekly.py
       ──→ startup.py
       ──→ ui/calibration.py

dashboard.py ──→ ui/app.py ──→ ipc.py (IPCClient)
                           ──→ ui/tab_*.py
                           ──→ ui/calibration.py
```

## God Nodes (highest connectivity)
| Module/Class | Edges | Role |
|-------------|-------|------|
| `SettingsTab` | 46 | Central hub for all user configuration |
| `SharedState` | 31 | Thread-safe data container connecting all threads |
| `Phase` | 29 | Enum driving the adaptive algorithm state machine |
| `CalibrationWizard` | 29 | First-run wizard touching detector + settings |
| `IPCClient` | 21 | Dashboard's bridge to the background process |
