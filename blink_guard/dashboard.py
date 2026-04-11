"""
dashboard.py — Entry point for the BlinkGuard Dashboard.

Launches the CustomTkinter dashboard UI as a standalone application.
Communicates with the running BlinkGuard background process via IPC
on localhost:57821.
"""

import sys
import os
import logging
import logging.handlers

# Ensure the project root is on sys.path when run as a script
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ---------------------------------------------------------------------------
# Logging setup
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
    # Avoid duplicate handlers if already set up
    if not root.handlers:
        root.addHandler(handler)

    if not getattr(sys, "frozen", False):
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.INFO)
        stderr_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(message)s")
        )
        root.addHandler(stderr_handler)


_setup_logging()
logger = logging.getLogger("BlinkGuard.Dashboard")

# ---------------------------------------------------------------------------
# CustomTkinter configuration
# ---------------------------------------------------------------------------

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _is_already_running() -> bool:
    """Check if another dashboard instance is already running via a named mutex."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        # Try to create a named mutex
        mutex = kernel32.CreateMutexW(None, False, "BlinkGuardDashboard_SingleInstance")
        if ctypes.GetLastError() == ERROR_ALREADY_EXISTS:
            # Another instance owns the mutex
            if mutex:
                kernel32.CloseHandle(mutex)
            return True
        # We now own the mutex — keep it alive for the process lifetime
        # (it will be released automatically when the process exits)
        return False
    except Exception:
        # If ctypes fails (unlikely on Windows), allow the app to run
        return False


def main() -> None:
    if _is_already_running():
        logger.info("Dashboard is already running — exiting duplicate instance.")
        return

    logger.info("=" * 60)
    logger.info("BlinkGuard Dashboard starting.")
    logger.info("=" * 60)

    from blink_guard.ui.app import DashboardApp

    app = DashboardApp()
    app.mainloop()

    logger.info("BlinkGuard Dashboard stopped.\n")


if __name__ == "__main__":
    main()
