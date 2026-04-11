"""
main.py — Entry point for BlinkGuard.

Wires threads together:
  • Main thread  → pystray system tray (required by pystray)
  • Thread 1     → OpenCV + MediaPipe camera loop (detector.py)
  • Thread 2     → Session stats updater (periodic save to settings.json)

Also hooks Windows session events (lock / unlock / sleep) via pywin32.
Launches calibration wizard on first run.
"""

import sys
import os
import json
import time
import datetime
import threading
import logging
import logging.handlers

# ---------------------------------------------------------------------------
# Logging setup (must happen before any local imports)
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    if getattr(sys, "frozen", False):
        log_dir = os.path.dirname(sys.executable)
    else:
        log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    log_path = os.path.join(log_dir, "blinkguard.log")

    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    root = logging.getLogger("BlinkGuard")
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    # Also log to stderr when running from a console
    if not getattr(sys, "frozen", False):
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.INFO)
        stderr_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(message)s")
        )
        root.addHandler(stderr_handler)


_setup_logging()
logger = logging.getLogger("BlinkGuard")

# ---------------------------------------------------------------------------
# Local imports (after logging is ready)
# ---------------------------------------------------------------------------

from blink_guard.state import SharedState, Phase, DetectorState  # noqa: E402
from blink_guard.detector import run_detector                   # noqa: E402
from blink_guard.tray import run_tray                           # noqa: E402
from blink_guard.alerts import init_sound, shutdown_sound        # noqa: E402
from blink_guard.startup import set_launch_on_startup            # noqa: E402
from blink_guard.adaptive import (                               # noqa: E402
    compute_baseline,
    update_phase,
    should_count_session,
    OBSERVATION_SESSIONS,
)
from blink_guard.ipc import IPCServer                            # noqa: E402
from blink_guard.risk import compute_risk_score                  # noqa: E402
from blink_guard.weekly import (                                 # noqa: E402
    should_generate_weekly,
    generate_summary_card,
    show_toast_notification,
    record_weekly_summary,
)

# ---------------------------------------------------------------------------
# Windows session-event listener
# ---------------------------------------------------------------------------

def _start_session_watcher(shared: SharedState) -> threading.Thread | None:
    """Listen for Windows lock / unlock / sleep events.

    Uses win32ts WTSRegisterSessionNotification through a hidden message
    window.  Falls back gracefully if pywin32 is not available.
    """
    try:
        import win32api
        import win32con
        import win32gui
        import win32ts
    except ImportError:
        logger.warning("pywin32 not available — screen-lock detection disabled.")
        return None

    WM_WTSSESSION_CHANGE = 0x02B1
    WTS_SESSION_LOCK = 0x7
    WTS_SESSION_UNLOCK = 0x8

    def _wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_WTSSESSION_CHANGE:
            if wparam == WTS_SESSION_LOCK:
                logger.info("Screen locked — pausing detector.")
                shared.set_detector_state(DetectorState.PAUSED)
            elif wparam == WTS_SESSION_UNLOCK:
                logger.info("Screen unlocked — resuming detector.")
                shared.set_detector_state(DetectorState.WATCHING)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _listener():
        try:
            wc = win32gui.WNDCLASS()
            wc.lpfnWndProc = _wnd_proc
            wc.lpszClassName = "BlinkGuardSessionWatcher"
            wc.hInstance = win32api.GetModuleHandle(None)
            class_atom = win32gui.RegisterClass(wc)

            hwnd = win32gui.CreateWindow(
                class_atom, "BlinkGuardSessionWatcher",
                0, 0, 0, 0, 0, 0, 0, wc.hInstance, None,
            )
            win32ts.WTSRegisterSessionNotification(hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)

            # Message pump — exits when shutdown_event is set
            while not shared.shutdown_event.is_set():
                # PeekMessage with a short sleep to stay responsive to shutdown
                result = win32gui.PeekMessage(hwnd, 0, 0, win32con.PM_REMOVE)
                if result and result[0]:  # result is (msg, ...) or 0
                    win32gui.TranslateMessage(result[1])
                    win32gui.DispatchMessage(result[1])
                else:
                    time.sleep(0.2)

            win32ts.WTSUnRegisterSessionNotification(hwnd)
            win32gui.DestroyWindow(hwnd)
            win32gui.UnregisterClass(class_atom, wc.hInstance)
        except Exception:
            logger.exception("Session watcher crashed.")

    t = threading.Thread(target=_listener, name="SessionWatcher", daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
# Session-stats updater (Thread 2)
# ---------------------------------------------------------------------------

SAVE_INTERVAL_SECONDS = 60


def _session_updater(shared: SharedState) -> None:
    """Periodically persist session stats to settings.json."""
    logger.info("Session updater thread starting.")
    while not shared.shutdown_event.is_set():
        shared.shutdown_event.wait(SAVE_INTERVAL_SECONDS)
        if shared.shutdown_event.is_set():
            break
        try:
            shared.save_settings()
            logger.debug("Settings saved (periodic).")
        except Exception:
            logger.exception("Periodic save failed.")
    logger.info("Session updater thread stopped.")


# ---------------------------------------------------------------------------
# End-of-session processing
# ---------------------------------------------------------------------------

def _finalise_session(shared: SharedState) -> None:
    """Compute end-of-session stats, update adaptive state, and persist."""
    duration = shared.get_session_duration_minutes()
    avg_interval = shared.get_avg_blink_interval()

    with shared.lock:
        blink_count = shared.session_blink_count
        alerts_fired = shared.session_alerts_fired
        phase = shared.phase
        threshold = shared.current_threshold
        settings = shared.settings
        escalation_counts = getattr(shared, "escalation_counts", {})

    # --- Compute risk score ---
    risk_score, risk_band, _risk_color = compute_risk_score(
        avg_interval, threshold, alerts_fired, duration
    )

    # --- build session record ---
    record = {
        "date": datetime.date.today().isoformat(),
        "duration_minutes": round(duration, 1),
        "total_blinks": blink_count,
        "avg_blink_interval": round(avg_interval, 2) if avg_interval else 0,
        "alerts_fired": alerts_fired,
        "threshold_used": threshold,
        "phase": phase.value,
        "risk_score": risk_score,
        "risk_band": risk_band,
        "escalation_counts": dict(escalation_counts),
    }
    history: list = settings.setdefault("session_history", [])
    history.append(record)
    logger.info("Session record: %s", record)

    # --- Update hourly alert counts ---
    hour = datetime.datetime.now().strftime("%H")
    hourly = settings.setdefault("hourly_data", {})
    hour_data = hourly.setdefault(hour, {"total_intervals": [], "alert_count": 0})
    hour_data["alert_count"] = hour_data.get("alert_count", 0) + alerts_fired

    # --- Phase 1: compute baseline after enough observation sessions ---
    if phase == Phase.OBSERVING:
        obs_count = sum(
            1 for s in history if should_count_session(s.get("duration_minutes", 0))
        )
        if obs_count >= OBSERVATION_SESSIONS and avg_interval is not None:
            all_intervals: list[float] = []
            with shared.lock:
                ts = shared.blink_timestamps.copy()
            if len(ts) >= 2:
                all_intervals = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]

            baseline = compute_baseline(all_intervals) if all_intervals else (avg_interval or 12.0)
            with shared.lock:
                shared.baseline_interval = baseline
                settings["baseline_interval"] = baseline
            logger.info("Baseline computed: %.2fs", baseline)

    # --- Count session if long enough ---
    if should_count_session(duration) and phase != Phase.OBSERVING:
        settings["sessions_completed"] = settings.get("sessions_completed", 0) + 1
        if phase == Phase.MAINTENANCE:
            settings["maintenance_sessions"] = settings.get("maintenance_sessions", 0) + 1

    # --- Phase transitions ---
    settings = update_phase(settings)

    # --- Weekly summary check ---
    try:
        if should_generate_weekly(settings):
            path = generate_summary_card(settings)
            if path:
                record_weekly_summary(settings, path)
                improvement = 0.0
                # Try to show toast in background
                try:
                    show_toast_notification(path, improvement)
                except Exception:
                    pass
    except Exception:
        logger.exception("Weekly summary generation failed.")

    # --- Write back ---
    with shared.lock:
        shared.settings = settings
        shared.phase = Phase(settings["phase"])
        shared.current_threshold = settings.get("current_threshold")
        shared.baseline_interval = settings.get("baseline_interval")

    shared.save_settings()
    logger.info("Final settings saved.")


# ---------------------------------------------------------------------------
# IPC callbacks
# ---------------------------------------------------------------------------

def _build_ipc_callbacks(shared: SharedState):
    """Create IPC callback functions that read from SharedState."""

    def get_state() -> dict:
        avg_interval = shared.get_avg_blink_interval()
        with shared.lock:
            return {
                "blink_count": shared.session_blink_count,
                "avg_interval": avg_interval,
                "last_blink_ms_ago": int((time.time() - shared.last_blink_time) * 1000),
                "ear_left": getattr(shared, "ear_left", 0.0),
                "ear_right": getattr(shared, "ear_right", 0.0),
                "ear_history": list(getattr(shared, "ear_history", [])),
                "alerts_fired": shared.session_alerts_fired,
                "phase": shared.phase.value,
                "current_threshold": shared.current_threshold,
                "face_detected": shared.detector_state != DetectorState.FACE_NOT_VISIBLE,
                "escalation_level": getattr(shared, "escalation_level", 0),
                "dnd_active": getattr(shared, "dnd_active", False),
                "dnd_end_time": getattr(shared, "dnd_end_time", None),
                "escalation_counts": dict(getattr(shared, "escalation_counts", {})),
            }

    def get_frame() -> bytes | None:
        return getattr(shared, "last_jpeg_frame", None)

    def handle_command(cmd: str, msg: dict) -> dict:
        if cmd == "PAUSE":
            shared.set_detector_state(DetectorState.PAUSED)
            return {"ok": True}
        elif cmd == "RESUME":
            shared.set_detector_state(DetectorState.WATCHING)
            return {"ok": True}
        elif cmd == "SET_SETTING":
            key = msg.get("key")
            value = msg.get("value")
            allowed_keys = (
                "sound_enabled", "launch_on_startup",
                "alert_volume", "volume", "camera_index",
                "ear_threshold", "ear_blink_threshold", "ear_open_threshold",
                "show_landmarks",
                "total_sessions_planned", "target_threshold",
                "phase", "baseline_interval",
                "sessions_completed", "current_threshold",
                "maintenance_sessions",
                "alert_sound", "custom_sound_path",
                "dnd_enabled", "dnd_schedule",
                "calibrated", "calibration_date",
            )
            if key and key in allowed_keys:
                with shared.lock:
                    shared.settings[key] = value
                    if key == "sound_enabled":
                        shared.sound_enabled = bool(value)
                    elif key == "launch_on_startup":
                        shared.launch_on_startup = bool(value)
                    elif key == "phase":
                        shared.phase = Phase(value)
                    elif key == "baseline_interval":
                        shared.baseline_interval = value
                    elif key == "current_threshold":
                        shared.current_threshold = value
                shared.save_settings()
                return {"ok": True}
            return {"error": f"unknown setting: {key}"}
        elif cmd == "LAUNCH_CONFIRMED":
            return {"ok": True}
        return {"error": f"unhandled: {cmd}"}

    return get_state, get_frame, handle_command


# ---------------------------------------------------------------------------
# Calibration (first-launch)
# ---------------------------------------------------------------------------

def _run_calibration_if_needed(shared: SharedState) -> None:
    """Launch calibration wizard on first run. Blocks until wizard closes."""
    with shared.lock:
        calibrated = shared.settings.get("calibrated", False)

    if calibrated:
        return

    logger.info("First launch detected — starting calibration wizard.")

    try:
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Create a hidden root window for the wizard
        root = ctk.CTk()
        root.withdraw()

        calibration_done = threading.Event()

        def on_complete():
            calibration_done.set()
            root.after(100, root.destroy)

        from blink_guard.ui.calibration import CalibrationWizard
        wizard = CalibrationWizard(master=root, on_complete=on_complete)
        wizard.lift()
        wizard.focus_force()

        root.mainloop()

        # Reload settings after calibration
        shared.load_settings()
        logger.info("Calibration wizard completed.")

    except Exception:
        logger.exception("Calibration wizard failed — using defaults.")


# ---------------------------------------------------------------------------
# Session start prompt
# ---------------------------------------------------------------------------

def _show_session_prompt() -> bool:
    """Show a styled popup asking the user to confirm session start.

    Returns True if the user clicks 'Start Session', False otherwise.
    """
    try:
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
    except ImportError:
        return True  # skip prompt if CTk unavailable

    result = {"accepted": False}

    root = ctk.CTk()
    root.title("BlinkGuard")
    root.geometry("460x320")
    root.resizable(False, False)
    root.configure(fg_color="#1e1e1e")

    # Center on screen
    root.update_idletasks()
    w, h = 460, 320
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    # Icon
    try:
        from PIL import Image, ImageDraw
        size = 64
        img = Image.new("RGBA", (size, size), (30, 30, 30, 255))
        draw = ImageDraw.Draw(img)
        cr = size * 0.22
        cx, cy = size // 2, size // 2
        draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr),
                     fill=(0, 122, 204, 255), outline=(90, 170, 230, 255), width=2)
        pr = size * 0.09
        draw.ellipse((cx - pr, cy - pr, cx + pr, cy + pr), fill=(20, 20, 40, 255))
        import tempfile
        icon_path = os.path.join(tempfile.gettempdir(), "blinkguard_icon.ico")
        img.save(icon_path, format="ICO", sizes=[(64, 64)])
        root.iconbitmap(icon_path)
    except Exception:
        pass

    # Eye emoji
    ctk.CTkLabel(
        root, text="👁", font=ctk.CTkFont(size=48), text_color="#007acc",
    ).pack(pady=(28, 4))

    # Title
    ctk.CTkLabel(
        root, text="Start BlinkGuard Session?",
        font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
        text_color="#d4d4d4",
    ).pack(pady=(0, 8))

    # Description
    ctk.CTkLabel(
        root,
        text="BlinkGuard will monitor your blink rate in the\n"
             "background and gently remind you to blink.",
        font=ctk.CTkFont(family="Segoe UI", size=13),
        text_color="#858585",
        justify="center",
    ).pack(pady=(0, 24))

    # Buttons
    btn_frame = ctk.CTkFrame(root, fg_color="transparent")
    btn_frame.pack(pady=(0, 20))

    def on_start():
        result["accepted"] = True
        root.destroy()

    def on_cancel():
        result["accepted"] = False
        root.destroy()

    ctk.CTkButton(
        btn_frame, text="▶  Start Session", width=180, height=40,
        fg_color="#007acc", hover_color="#1a8ad4",
        text_color="#ffffff",
        font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        corner_radius=8,
        command=on_start,
    ).pack(side="left", padx=(0, 12))

    ctk.CTkButton(
        btn_frame, text="Not Now", width=120, height=40,
        fg_color="#3c3c3c", hover_color="#4a4a4a",
        text_color="#d4d4d4",
        font=ctk.CTkFont(family="Segoe UI", size=13),
        corner_radius=8,
        command=on_cancel,
    ).pack(side="left")

    # Handle window close (X button) = cancel
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.lift()
    root.focus_force()
    root.mainloop()

    return result["accepted"]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=" * 60)
    logger.info("BlinkGuard starting.")
    logger.info("=" * 60)

    shared = SharedState()
    shared.load_settings()

    # Apply startup preference
    set_launch_on_startup(shared.launch_on_startup)

    # Initialise sound
    init_sound()

    # Run calibration wizard if first launch (blocks until done)
    _run_calibration_if_needed(shared)

    # Ask user to confirm session start
    if not _show_session_prompt():
        logger.info("User declined session — exiting.")
        shutdown_sound()
        return

    # Start IPC server
    get_state_cb, get_frame_cb, cmd_cb = _build_ipc_callbacks(shared)
    ipc_server = IPCServer(get_state_cb, get_frame_cb, cmd_cb)
    ipc_server.start()

    # Start threads
    detector_thread = threading.Thread(
        target=run_detector, args=(shared,), name="Detector", daemon=True
    )
    updater_thread = threading.Thread(
        target=_session_updater, args=(shared,), name="Updater", daemon=True
    )

    detector_thread.start()
    updater_thread.start()
    session_watcher = _start_session_watcher(shared)

    # Run tray on main thread (blocks until quit)
    try:
        run_tray(shared)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt — shutting down.")
    finally:
        shared.shutdown_event.set()

    # Stop IPC server
    ipc_server.stop()

    # Wait for threads to exit
    detector_thread.join(timeout=5)
    updater_thread.join(timeout=3)
    if session_watcher:
        session_watcher.join(timeout=2)

    # End-of-session bookkeeping
    try:
        _finalise_session(shared)
    except Exception:
        logger.exception("Failed to finalise session.")

    shutdown_sound()
    logger.info("BlinkGuard stopped.\n")


if __name__ == "__main__":
    main()
