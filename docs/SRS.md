# Software Requirements Specification (SRS)
## BlinkGuard — Adaptive Blink Rate Monitor
**Version:** 1.0.0 · **Date:** April 2026

---

## 1. Introduction

### 1.1 Purpose
This document specifies the software requirements for BlinkGuard, a Windows desktop application that monitors and improves the user's blink rate through webcam-based eye tracking and adaptive conditioning. It serves as the authoritative reference for all functional and non-functional requirements.

### 1.2 Scope
BlinkGuard consists of two cooperating executables:
- **BlinkGuard.exe** — Background process for real-time blink detection, alerts, and adaptive algorithm execution
- **BlinkGuardDashboard.exe** — GUI dashboard for live monitoring, analytics, and configuration

The system operates entirely offline with no network dependencies.

### 1.3 Definitions & Acronyms

| Term | Definition |
|------|-----------|
| **EAR** | Eye Aspect Ratio — ratio of vertical to horizontal eye landmarks used to detect blinks |
| **IPC** | Inter-Process Communication — TCP-based messaging between background and dashboard processes |
| **DND** | Do Not Disturb — scheduled periods where alerts are suppressed |
| **Phase** | Stage in the adaptive algorithm: Observing → Active → Maintenance → Wean-off |
| **Baseline** | User's natural average inter-blink interval computed during observation |
| **Threshold** | Current target inter-blink interval; decreases over sessions toward the health target |

### 1.4 Target Users
Individual desktop users who experience eye strain, dryness, or reduced blink rates during extended screen use. Currently scoped for personal use with plans for future distribution.

---

## 2. Overall Description

### 2.1 Product Perspective
BlinkGuard is a standalone desktop application. It requires:
- A webcam (built-in or USB)
- Windows 10 or later
- Python 3.10+ (for source execution) or standalone executables

### 2.2 Product Functions (High-Level)
1. Real-time blink detection via webcam
2. Adaptive threshold conditioning over multiple sessions
3. Multi-level alert escalation with customizable sounds
4. Dashboard with live preview, progress analytics, and session history
5. System tray integration with quick controls
6. Do Not Disturb scheduling
7. Weekly progress summary generation
8. Eye strain risk scoring

### 2.3 Operating Constraints
- **Platform:** Windows 10+ only (uses Win32 API for mutex, power events, registry)
- **Privacy:** All processing must be local; no network requests permitted
- **Performance:** Camera detection loop must sustain ≥15 fps on mid-range hardware
- **Storage:** Session history capped at 365 records to prevent unbounded growth

### 2.4 Assumptions
- User has a functioning webcam with adequate lighting
- User face is visible to the camera during monitoring sessions
- Single user per installation

---

## 3. Functional Requirements

### 3.1 Blink Detection

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-DET-01 | The system SHALL use MediaPipe Face Mesh (468 landmarks) to track facial features | Must |
| FR-DET-02 | The system SHALL compute the Eye Aspect Ratio (EAR) for both eyes independently | Must |
| FR-DET-03 | The system SHALL detect a blink when EAR drops below the configured threshold for ≥2 consecutive frames and then rises above EOF threshold | Must |
| FR-DET-04 | The system SHALL enforce a 300ms grace period between consecutive blink detections to prevent double-counting | Must |
| FR-DET-05 | The system SHALL detect when no face is visible and pause blink tracking | Must |
| FR-DET-06 | The system SHALL encode camera frames as JPEG for dashboard live preview at reduced frequency | Should |
| FR-DET-07 | The system SHALL attempt camera reconnection up to 10 times (3s intervals) on webcam disconnection | Must |

### 3.2 Adaptive Algorithm

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-ADP-01 | **Observing Phase:** The system SHALL silently collect blink data for ≥2 sessions before computing a baseline | Must |
| FR-ADP-02 | **Baseline Computation:** The system SHALL compute the baseline as the mean of inter-blink intervals, filtering outliers >30s and clamping to [1.0, 25.0] seconds | Must |
| FR-ADP-03 | **Active Phase:** The system SHALL linearly interpolate the alert threshold from baseline toward target over N sessions (7 for healthy baselines ≤5s, 14 otherwise) | Must |
| FR-ADP-04 | **Maintenance Phase:** After completing all active sessions, the system SHALL hold threshold at target for ≥7 sessions | Must |
| FR-ADP-05 | **Wean-off Phase:** After maintenance, the system SHALL transition to wean-off with reduced intervention | Should |
| FR-ADP-06 | Sessions <5 minutes SHALL NOT count toward phase progression | Must |

### 3.3 Alert System

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-ALT-01 | When no blink is detected within the current threshold, the system SHALL fire an alert | Must |
| FR-ALT-02 | Alerts SHALL escalate across 3 levels: Soft (L1) → Medium (L2) → Urgent (L3) with increasing intensity | Must |
| FR-ALT-03 | The user SHALL be able to select between default beep and custom sound files (.wav, .mp3) | Must |
| FR-ALT-04 | The user SHALL be able to adjust alert volume (0-100) | Must |
| FR-ALT-05 | Custom sound files SHALL be limited to 5MB maximum | Should |
| FR-ALT-06 | The user SHALL be able to preview the selected alert sound from settings | Should |

### 3.4 Do Not Disturb

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-DND-01 | The user SHALL be able to enable/disable DND globally | Must |
| FR-DND-02 | The user SHALL be able to create DND rules specifying days and time ranges (HH:MM format) | Must |
| FR-DND-03 | During DND windows, alert sounds SHALL be suppressed but blink tracking SHALL continue | Must |
| FR-DND-04 | DND rules SHALL be validated: start < end, valid day names, valid time format | Must |
| FR-DND-05 | Maximum 10 DND rules per user | Should |

### 3.5 Dashboard

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-DSH-01 | **Live Tab:** The dashboard SHALL display a real-time camera preview with eye landmark overlay | Must |
| FR-DSH-02 | **Live Tab:** The dashboard SHALL show live EAR values, blink count, and alert status | Must |
| FR-DSH-03 | **Progress Tab:** The dashboard SHALL display session statistics, phase journey, and risk scoring | Must |
| FR-DSH-04 | **Progress Tab:** The dashboard SHALL render a time-of-day blink heatmap | Should |
| FR-DSH-05 | **History Tab:** The dashboard SHALL list all past sessions with date, duration, blinks, alerts, and risk | Must |
| FR-DSH-06 | **Settings Tab:** The dashboard SHALL provide grouped configuration cards for all user-adjustable settings | Must |
| FR-DSH-07 | The dashboard SHALL poll the background process for live state every 500ms | Must |
| FR-DSH-08 | Only one dashboard instance SHALL be allowed (enforced via Windows mutex) | Must |

### 3.6 System Integration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-SYS-01 | The background process SHALL run in the Windows system tray | Must |
| FR-SYS-02 | The tray icon SHALL indicate current status (watching, paused, face not visible) | Must |
| FR-SYS-03 | Double-clicking the tray icon SHALL open the dashboard | Must |
| FR-SYS-04 | The user SHALL be able to toggle "launch on startup" via Windows registry | Must |
| FR-SYS-05 | The system SHALL detect Windows sleep/wake events and finalize/restart sessions accordingly | Must |
| FR-SYS-06 | IPC SHALL use TCP with port fallback (57821-57825) and lock file discovery | Must |

### 3.7 Data & Persistence

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-DAT-01 | All settings and session history SHALL be stored in a local `settings.json` file | Must |
| FR-DAT-02 | Settings SHALL be auto-saved every 60 seconds during a session | Must |
| FR-DAT-03 | All settings keys SHALL have defined defaults and type validation | Must |
| FR-DAT-04 | Session history SHALL be capped at 365 records with oldest pruned on overflow | Must |
| FR-DAT-05 | Weekly summary cards SHALL be generated when eligibility criteria are met | Should |

### 3.8 Calibration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-CAL-01 | On first launch, the system SHALL run a calibration wizard to compute personalized EAR thresholds | Must |
| FR-CAL-02 | The calibration wizard SHALL guide the user through "look straight" and "blink" phases | Must |
| FR-CAL-03 | The user SHALL be able to recalibrate from the Camera settings card | Should |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-PERF-01 | Camera detection loop frame rate | ≥15 fps on i5/Ryzen 5 with integrated GPU |
| NFR-PERF-02 | Dashboard UI responsiveness | <100ms for user interactions |
| NFR-PERF-03 | IPC round-trip latency | <50ms on localhost |
| NFR-PERF-04 | Memory usage (background process) | <300MB RSS |
| NFR-PERF-05 | Startup time to first detection frame | <5 seconds |

### 4.2 Reliability

| ID | Requirement |
|----|-------------|
| NFR-REL-01 | The system SHALL recover from camera disconnection without crashing (up to 10 retries) |
| NFR-REL-02 | Corrupt `settings.json` SHALL fall back to defaults without data loss in the running session |
| NFR-REL-03 | IPC port conflicts SHALL be resolved via automatic fallback to alternative ports |
| NFR-REL-04 | Sleep/wake events SHALL NOT corrupt session data |

### 4.3 Usability

| ID | Requirement |
|----|-------------|
| NFR-USE-01 | The dashboard SHALL use a VS Code-inspired dark theme for minimal eye strain |
| NFR-USE-02 | All settings changes SHALL take effect immediately without requiring a restart |
| NFR-USE-03 | Progress reset SHALL require a confirmation dialog with clear warning text |

### 4.4 Security & Privacy

| ID | Requirement |
|----|-------------|
| NFR-SEC-01 | The application SHALL NOT make any network requests |
| NFR-SEC-02 | Camera frames SHALL NOT be persisted to disk (transient JPEG for live preview only) |
| NFR-SEC-03 | IPC communication SHALL be limited to localhost (127.0.0.1) |

### 4.5 Maintainability

| ID | Requirement |
|----|-------------|
| NFR-MNT-01 | No source file SHALL exceed 400 lines |
| NFR-MNT-02 | Pure logic modules SHALL have ≥85% unit test coverage |
| NFR-MNT-03 | All settings keys SHALL be defined in a single schema (`defaults.py`) |

---

## 5. Data Dictionary

### 5.1 Session Record Schema
```json
{
  "date": "2026-04-20",
  "duration_minutes": 45.3,
  "total_blinks": 312,
  "avg_blink_interval": 8.72,
  "alerts_fired": 5,
  "threshold_used": 6.5,
  "phase": "active",
  "risk_score": 42,
  "risk_band": "Moderate",
  "escalation_counts": {"1": 3, "2": 1, "3": 1}
}
```

### 5.2 DND Rule Schema
```json
{
  "days": ["mon", "wed", "fri"],
  "start": "09:00",
  "end": "10:00"
}
```

### 5.3 Risk Bands

| Score Range | Band | Color |
|-------------|------|-------|
| 0-25 | Low | Green |
| 26-50 | Moderate | Yellow |
| 51-75 | High | Orange |
| 76-100 | Severe | Red |

---

## 6. Traceability Matrix

| Requirement | Module(s) | Test File |
|-------------|-----------|-----------|
| FR-DET-01..07 | `detector.py` | Manual (hardware-dependent) |
| FR-ADP-01..06 | `adaptive.py`, `session.py` | `test_adaptive.py` |
| FR-ALT-01..06 | `alerts.py`, cards/`card_alert.py` | Manual (audio) |
| FR-DND-01..05 | `dnd.py`, cards/`card_dnd.py` | `test_dnd.py` |
| FR-DSH-01..08 | `ui/app.py`, `ui/tab_*.py` | Manual (GUI) |
| FR-SYS-01..06 | `main.py`, `tray.py`, `ipc.py` | Manual (OS integration) |
| FR-DAT-01..05 | `defaults.py`, `state.py` | `test_defaults.py`, `test_state.py` |
| FR-CAL-01..03 | `ui/calibration.py` | Manual (hardware) |
| NFR-SEC-01..03 | Architecture-wide | Code review |
| NFR-MNT-01..03 | All modules | `pytest --cov` |
