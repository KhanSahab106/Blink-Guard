# Technology Stack

## Language & Runtime
- **Python 3.10** (system-wide, `C:\Users\ABRAR\AppData\Local\Programs\Python\Python310`)
- Local venv at `myenv/` (Python 3.12 headers present but primary runtime is 3.10)

## Core Libraries
| Library | Version | Purpose |
|---------|---------|---------|
| opencv-python | 4.9.0.80 | Camera capture + frame processing |
| mediapipe | 0.10.13 | Face Mesh 468 landmarks for EAR calculation |
| pystray | 0.19.5 | System tray icon + right-click menu |
| Pillow | 10.3.0 | Icon generation, weekly summary PNG |
| pygame | 2.5.2 | Audio mixer for alert beeps (sine wave synthesis) |
| pywin32 | 306 | Windows registry (startup), session events (lock/unlock) |
| customtkinter | 5.2.2 | Dashboard GUI (tabs, charts, calibration wizard) |
| matplotlib | 3.8.4 | Charts in dashboard tabs (progress, history) |
| numpy | >=1.24.0 | Numerical support for mediapipe |
| win10toast | >=0.9 | Windows toast notifications (weekly summary) |
| pyinstaller | 6.5.0 | Build to `.exe` |

## Build & Distribution
- **PyInstaller** via `build.bat` and `BlinkGuardDashboard.spec`
- Produces two executables: `BlinkGuard.exe` (background) + `BlinkGuardDashboard.exe` (GUI)
- Output in `dist/`

## Data Persistence
- **settings.json** (flat JSON file at project root)
  - Session history, hourly data, phase state, calibration, DND schedule
  - No database — single-file persistence

## Inter-Process Communication
- **TCP socket** on `localhost:57821`
- Newline-delimited JSON protocol
- Background process = server; Dashboard = client

## Platform
- **Windows-only** (pywin32, winreg, Win32 message pump, DSHOW camera backend)
- No macOS/Linux support path currently exists
