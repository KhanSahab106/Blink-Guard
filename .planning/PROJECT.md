# BlinkGuard — Project Context

## Vision
A privacy-first Windows system tray application that monitors blink rate via webcam and uses an adaptive algorithm to train healthier blinking habits — reducing digital eye strain without cloud dependencies.

## Current State
- **Brownfield project** — functional prototype with 20 Python modules (~3,800 LOC)
- Two-process architecture: background detector + CustomTkinter dashboard
- Four-phase adaptive algorithm (Observing → Active → Maintenance → Wean-off)
- Codebase map completed (see `.planning/codebase/`)

## Primary Goals
1. **Ship v1.0** — Polish the existing feature set, fix critical bugs, package for clean distribution
2. **Refactor & stabilize** — Address the 12 concerns from CONCERNS.md, add test coverage, decompose god objects

## Target User
- **Currently:** Personal use (developer/knowledge worker)
- **Future:** Plan to scale to public release (GitHub, potentially Windows Store)
- Design decisions should keep future distribution in mind (clean installer, settings migration, etc.)

## Timeline
- No hard deadline. Quality over speed.
- Work in focused phases; each phase should leave the app in a shippable state.

## User-Requested Features
1. **Sleep/wake session reset** — When the machine wakes from sleep, automatically end the current session and start a new one (currently the old session just continues with stale data)
2. **Dashboard access from system tray** — The "Open Dashboard" tray menu item should work reliably, and ideally double-clicking the tray icon should also open the dashboard

## Key Constraints
- Windows-only (pywin32 dependency is acceptable)
- Privacy-first: no network calls, no telemetry, no cloud
- Must remain a lightweight background process (low CPU/memory)
- Python 3.10+ (no Node.js available in environment)

## Tech Stack Summary
See `.planning/codebase/STACK.md` for full details.
- Python 3.10, OpenCV, MediaPipe, CustomTkinter, pygame, pystray, pywin32
- PyInstaller for distribution
- settings.json for persistence (no database)

## Repository
- `C:\Users\ABRAR\Desktop\Blink_gaurd`
- Git initialized, graphify knowledge graph built
