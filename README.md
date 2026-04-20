<p align="center">
  <h1 align="center">👁️ BlinkGuard</h1>
  <p align="center">
    <strong>Adaptive Blink Rate Monitor for Eye Health</strong><br>
    A privacy-first Windows desktop app that uses your webcam to build healthier blinking habits through gentle conditioning.
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python 3.10+"/>
    <img src="https://img.shields.io/badge/platform-Windows-0078D6?logo=windows" alt="Windows"/>
    <img src="https://img.shields.io/badge/tests-91%20passed-brightgreen" alt="Tests"/>
    <img src="https://img.shields.io/badge/coverage-96%25-brightgreen" alt="Coverage"/>
    <img src="https://img.shields.io/badge/license-personal-lightgrey" alt="License"/>
  </p>
</p>

---

## ✨ What It Does

BlinkGuard monitors your blink rate in real-time via webcam using MediaPipe face mesh. It learns your natural blink pattern over an observation period, then gently trains you to blink more frequently through a 3-phase adaptive algorithm — reducing eye strain and dryness during long screen sessions.

**All processing is 100% local. No data ever leaves your device.**

---

## 🏗️ Architecture

BlinkGuard runs as **two separate processes**:

| Process | Description |
|---------|-------------|
| **BlinkGuard.exe** | Background tray process — camera detection, blink tracking, alerts, adaptive algorithm |
| **BlinkGuardDashboard.exe** | Dashboard UI — live preview, progress charts, session history, settings |

They communicate via a local TCP IPC channel (port 57821-57825 with automatic fallback).

```
┌─────────────────────┐       IPC (TCP)       ┌─────────────────────────┐
│   BlinkGuard.exe    │◄─────────────────────►│ BlinkGuardDashboard.exe │
│                     │                        │                         │
│  • Camera capture   │                        │  • Live eye preview     │
│  • MediaPipe mesh   │                        │  • Progress charts      │
│  • Blink detection  │                        │  • Session history      │
│  • Alert escalation │                        │  • Settings cards       │
│  • Adaptive algo    │                        │  • Calibration wizard   │
│  • System tray      │                        │                         │
└─────────────────────┘                        └─────────────────────────┘
```

---

## 🚀 Quick Start

### From Source

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/BlinkGuard.git
cd BlinkGuard

# 2. Create a virtual environment
python -m venv myenv
myenv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the background process
python -m blink_guard.main

# 5. (In a separate terminal) Run the dashboard
python -m blink_guard.dashboard
```

### From Prebuilt Executables

1. Download the latest release from the dist/ folder
2. Place both `.exe` files in the same directory
3. Run `BlinkGuard.exe` — it starts in the system tray
4. Double-click the tray icon to open the dashboard

---

## 📋 Features

### Core
- **Real-time blink detection** using MediaPipe Face Mesh (468 landmarks)
- **EAR (Eye Aspect Ratio)** algorithm for accurate blink recognition
- **Calibration wizard** for personalized eye detection thresholds

### Adaptive Algorithm
- **Phase 1 — Observing** (2 sessions): Silent observation to compute your baseline blink interval
- **Phase 2 — Active** (7-14 sessions): Linearly interpolates threshold toward target, alerts when you go too long without blinking
- **Phase 3 — Maintenance** (7 sessions): Holds at target to reinforce habit
- **Phase 4 — Wean-off**: Reduces intervention as habit becomes automatic

### Alert System
- **3-level escalation**: Soft → Medium → Urgent alerts with customizable sounds
- **Custom sound support**: Use your own `.wav` / `.mp3` files
- **Do Not Disturb**: Schedule DND windows for meetings or focus time

### Dashboard
- **Live Tab**: Real-time eye view with EAR graph and blink counter
- **Progress Tab**: Session stats, phase journey, time-of-day heatmap, risk scoring
- **History Tab**: Full session log with sortable columns and CSV export
- **Settings Tab**: 6 modular card components (Alerts, Startup, Journey, DND, Camera, About)

### System Integration
- **System tray** with status indicators and quick controls
- **Launch on startup** via Windows registry
- **Sleep/wake detection** — automatically finalizes session on sleep, starts fresh on wake
- **Single-instance guard** — prevents duplicate dashboard windows
- **Camera disconnect recovery** — auto-retries up to 10 times on webcam disconnection

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=blink_guard --cov-report=term-missing

# Run a specific test file
pytest tests/test_adaptive.py -v
```

**Current status:** 91 tests · 95.7% coverage on testable modules

| Module | Coverage | Tests |
|--------|----------|-------|
| `adaptive.py` | 100% | 20 |
| `dnd.py` | 100% | 16 |
| `risk.py` | 94% | 17 |
| `defaults.py` | 85% | 16 |
| `state.py` | 99% | 19 |

---

## 📦 Building Executables

```bash
# Build both executables
build.bat
```

This creates:
```
dist/BlinkGuard/
├── BlinkGuard.exe            # Background process
├── BlinkGuardDashboard.exe   # Dashboard UI
├── settings.json             # Configuration
└── README.txt                # User guide
```

---

## 📁 Project Structure

```
Blink_gaurd/
├── blink_guard/                # Main package
│   ├── __init__.py             # Version info
│   ├── main.py                 # Entry point — threading, lifecycle
│   ├── detector.py             # Camera + MediaPipe blink detection
│   ├── state.py                # Thread-safe shared state container
│   ├── session.py              # Session lifecycle (save, finalize)
│   ├── adaptive.py             # Baseline + threshold progression
│   ├── alerts.py               # Sound playback (pygame)
│   ├── risk.py                 # Eye strain risk scoring
│   ├── dnd.py                  # Do Not Disturb schedule logic
│   ├── defaults.py             # Settings schema, load/save/validate
│   ├── ipc.py                  # TCP IPC server + client + callbacks
│   ├── startup.py              # Windows registry startup toggle
│   ├── tray.py                 # System tray (pystray)
│   ├── weekly.py               # Weekly summary card generation
│   ├── dashboard.py            # Dashboard entry point
│   └── ui/                     # Dashboard UI components
│       ├── app.py              # Main dashboard window
│       ├── tab_live.py         # Live eye preview tab
│       ├── tab_progress.py     # Progress & analytics tab
│       ├── tab_history.py      # Session history tab
│       ├── tab_settings.py     # Settings container (thin)
│       ├── calibration.py      # Calibration wizard
│       └── cards/              # Modular settings cards
│           ├── _base.py        # Shared palette + BaseCard class
│           ├── card_alert.py   # Sound, volume, custom audio
│           ├── card_startup.py # Launch on startup toggle
│           ├── card_journey.py # Sessions, target, phase, reset
│           ├── card_dnd.py     # DND schedule management
│           ├── card_camera.py  # Camera, EAR, landmarks, calibration
│           └── card_about.py   # Version, privacy, log file
├── tests/                      # Test suite
│   ├── conftest.py             # Shared fixtures
│   ├── test_adaptive.py        # Adaptive algorithm tests
│   ├── test_risk.py            # Risk scoring tests
│   ├── test_dnd.py             # DND schedule tests
│   ├── test_defaults.py        # Settings schema tests
│   └── test_state.py           # SharedState integration tests
├── build.bat                   # PyInstaller build script
├── pyproject.toml              # Project config (pytest, coverage)
├── requirements.txt            # Python dependencies
└── .planning/                  # GSD project management
```

---

## ⚙️ Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| opencv-python | 4.9.0 | Camera capture & frame processing |
| mediapipe | 0.10.13 | Face mesh landmark detection |
| customtkinter | 5.2.2 | Modern dark-themed dashboard UI |
| pystray | 0.19.5 | System tray integration |
| pygame | 2.5.2 | Alert sound playback |
| pywin32 | 306 | Windows API (mutex, power events) |
| matplotlib | 3.8.4 | Progress charts & heatmaps |
| Pillow | 10.3.0 | Image processing |
| numpy | ≥1.24.0 | Numerical operations |
| win10toast | ≥0.9 | Windows toast notifications |
| pyinstaller | 6.5.0 | Executable packaging |

---

## 🔒 Privacy

- **Zero network access** — all camera processing uses local MediaPipe models
- **No cloud storage** — settings and session history stored in local `settings.json`
- **No telemetry** — no analytics, tracking, or data collection whatsoever
- **Camera frames are never saved** — only transient JPEG for live dashboard preview

---

## 📄 License

Personal use. Not yet licensed for distribution.
