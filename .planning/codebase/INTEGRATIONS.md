# External Integrations

## Hardware
- **Webcam** — OpenCV `VideoCapture` with DirectShow backend (`CAP_DSHOW`). Resolution forced to 640×480.
- **Audio output** — pygame mixer at 44100 Hz, mono, 512-sample buffer.

## Windows OS APIs
| API | Module | Purpose |
|-----|--------|---------|
| `winreg` (HKCU\Run) | `startup.py` | Launch-on-login registry key |
| `win32ts.WTSRegisterSessionNotification` | `main.py` | Detect screen lock/unlock |
| `win32gui` message pump | `main.py` | Hidden window for session events |
| `win10toast` | `weekly.py` | Toast notifications with PNG summary |

## Network / External Services
- **None.** The application is fully offline. No telemetry, no cloud sync, no API calls.
- IPC is local TCP only (`127.0.0.1:57821`).

## File System
- `settings.json` — user configuration + session history (read/write)
- `blinkguard.log` — rotating log file (2 MB max, 2 backups)
- Weekly summary PNGs saved to temp directory
