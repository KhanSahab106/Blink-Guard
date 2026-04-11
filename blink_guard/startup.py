"""
startup.py — Registry read/write for Windows boot startup.

Uses HKEY_CURRENT_USER so no admin privileges are required.
"""

import sys
import os
import logging

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]

logger = logging.getLogger("BlinkGuard")

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "BlinkGuard"


def _get_exe_path() -> str:
    """Return the path to the current executable or script."""
    if getattr(sys, "frozen", False):
        return sys.executable
    # Running as a script — use pythonw if available to avoid console window
    return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'


def is_launch_on_startup() -> bool:
    """Check whether BlinkGuard is registered to launch at login."""
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        logger.exception("Failed to read startup registry key.")
        return False


def set_launch_on_startup(enable: bool) -> None:
    """Add or remove BlinkGuard from the Windows startup registry."""
    if winreg is None:
        logger.warning("winreg unavailable — cannot modify startup setting.")
        return
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        try:
            if enable:
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _get_exe_path())
                logger.info("Registered BlinkGuard for startup.")
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                    logger.info("Removed BlinkGuard from startup.")
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
    except OSError:
        logger.exception("Failed to modify startup registry key.")
