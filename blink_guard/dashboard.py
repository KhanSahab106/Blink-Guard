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

def main() -> None:
    logger.info("=" * 60)
    logger.info("BlinkGuard Dashboard starting.")
    logger.info("=" * 60)

    from blink_guard.ui.app import DashboardApp

    app = DashboardApp()
    app.mainloop()

    logger.info("BlinkGuard Dashboard stopped.\n")


if __name__ == "__main__":
    main()
