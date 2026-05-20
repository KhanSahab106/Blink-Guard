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
from blink_guard.ipc import IPCServer, build_ipc_callbacks       # noqa: E402
from blink_guard.session import finalise_session, session_updater  # noqa: E402

# ---------------------------------------------------------------------------
# Windows session-event listener
# ---------------------------------------------------------------------------

def _on_wake_reset(shared: SharedState) -> None:
    """Finalize the pre-sleep session and start a fresh one."""
    try:
        # Only finalize if there was meaningful activity
        if shared.session_blink_count > 0:
            finalise_session(shared)
            logger.info("Pre-sleep session finalized (%d blinks).", shared.session_blink_count)
    except Exception:
        logger.exception("Failed to finalize pre-sleep session.")

    shared.reset_session()
    shared.set_detector_state(DetectorState.WATCHING)
    logger.info("Session reset after wake — new session started.")


def _start_session_watcher(shared: SharedState) -> threading.Thread | None:
    """Listen for Windows lock / unlock / sleep / wake events.

    Uses win32ts WTSRegisterSessionNotification through a hidden message
    window.  Also handles WM_POWERBROADCAST for sleep/wake detection.
    Falls back gracefully if pywin32 is not available.
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

    WM_POWERBROADCAST = 0x0218
    PBT_APMSUSPEND = 0x0004
    PBT_APMRESUMEAUTOMATIC = 0x0012

    def _wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_WTSSESSION_CHANGE:
            if wparam == WTS_SESSION_LOCK:
                logger.info("Screen locked — pausing detector.")
                shared.set_detector_state(DetectorState.PAUSED)
            elif wparam == WTS_SESSION_UNLOCK:
                logger.info("Screen unlocked — resuming detector.")
                shared.set_detector_state(DetectorState.WATCHING)
        elif msg == WM_POWERBROADCAST:
            if wparam == PBT_APMSUSPEND:
                logger.info("System suspending — pausing detector.")
                shared.set_detector_state(DetectorState.PAUSED)
            elif wparam == PBT_APMRESUMEAUTOMATIC:
                logger.info("System woke from sleep — resetting session.")
                # Run reset in a separate thread to avoid blocking the message pump
                threading.Thread(
                    target=_on_wake_reset, args=(shared,),
                    name="WakeReset", daemon=True,
                ).start()
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
    # Skip when launched from dashboard to avoid invisible popups
    if "--skip-prompt" not in sys.argv:
        _run_calibration_if_needed(shared)

    # Ask user to confirm session start (skip if launched from dashboard)
    if "--skip-prompt" not in sys.argv:
        if not _show_session_prompt():
            logger.info("User declined session — exiting.")
            shutdown_sound()
            return
    else:
        logger.info("Launched from dashboard — skipping session prompt.")

    # Start IPC server
    get_state_cb, get_frame_cb, cmd_cb = build_ipc_callbacks(shared)
    ipc_server = IPCServer(get_state_cb, get_frame_cb, cmd_cb)
    ipc_server.start()

    # Start threads
    detector_thread = threading.Thread(
        target=run_detector, args=(shared,), name="Detector", daemon=True
    )
    updater_thread = threading.Thread(
        target=session_updater, args=(shared,), name="Updater", daemon=True
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
        finalise_session(shared)
    except Exception:
        logger.exception("Failed to finalise session.")

    shutdown_sound()
    logger.info("BlinkGuard stopped.\n")


if __name__ == "__main__":
    main()
