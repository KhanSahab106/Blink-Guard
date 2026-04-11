"""
tray.py — pystray tray icon and right-click menu.

Generates an eye-shaped icon programmatically and builds the system-tray
menu with live stats, toggles, DND indicator, and controls.
"""

import logging
import os
import sys
import subprocess

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as Item

from blink_guard.state import SharedState, DetectorState, Phase
from blink_guard.startup import set_launch_on_startup

logger = logging.getLogger("BlinkGuard")


# ---------------------------------------------------------------------------
# Icon generation
# ---------------------------------------------------------------------------

def _create_eye_icon(size: int = 64) -> Image.Image:
    """Draw a simple eye-shaped icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    w, h = size * 0.42, size * 0.22

    bbox_top = (cx - w, cy - h * 1.8, cx + w, cy + h * 0.4)
    bbox_bot = (cx - w, cy - h * 0.4, cx + w, cy + h * 1.8)
    draw.arc(bbox_top, 200, 340, fill=(30, 60, 120, 255), width=2)
    draw.arc(bbox_bot, 20, 160, fill=(30, 60, 120, 255), width=2)

    ir = size * 0.16
    draw.ellipse(
        (cx - ir, cy - ir, cx + ir, cy + ir),
        fill=(70, 140, 220, 255),
        outline=(30, 60, 120, 255),
        width=2,
    )

    pr = size * 0.07
    draw.ellipse(
        (cx - pr, cy - pr, cx + pr, cy + pr),
        fill=(10, 10, 30, 255),
    )

    hr = size * 0.03
    hx, hy = cx - ir * 0.35, cy - ir * 0.35
    draw.ellipse(
        (hx - hr, hy - hr, hx + hr, hy + hr),
        fill=(255, 255, 255, 200),
    )

    return img


# ---------------------------------------------------------------------------
# Menu helpers
# ---------------------------------------------------------------------------

def _phase_label(shared: SharedState) -> str:
    with shared.lock:
        phase = shared.phase
    labels = {
        Phase.OBSERVING: "📊 Phase: Observing",
        Phase.ACTIVE: "🎯 Phase: Active",
        Phase.MAINTENANCE: "✅ Phase: Maintenance",
        Phase.WEAN_OFF: "🌿 Phase: Wean-off",
    }
    return labels.get(phase, "Phase: Unknown")


def _stats_label(shared: SharedState) -> str:
    avg = shared.get_avg_blink_interval()
    with shared.lock:
        threshold = shared.current_threshold
    avg_str = f"{avg:.1f}s" if avg is not None else "—"
    thr_str = f"{threshold:.1f}s" if threshold is not None else "—"
    return f"Avg interval: {avg_str}  |  Threshold: {thr_str}"


def _progress_label(shared: SharedState) -> str:
    with shared.lock:
        baseline = shared.baseline_interval
        threshold = shared.current_threshold
        target = shared.settings.get("target_threshold", 4.0)
    if baseline is None or threshold is None:
        return "Progress: collecting data…"
    if baseline <= target:
        return "Progress: 100% ✨"
    progress = (baseline - threshold) / (baseline - target)
    pct = min(max(progress, 0.0), 1.0) * 100
    return f"Progress toward {target:.0f}s: {pct:.0f}%"


def _dnd_label(shared: SharedState) -> str:
    dnd_active = getattr(shared, "dnd_active", False)
    dnd_end = getattr(shared, "dnd_end_time", None)
    if dnd_active:
        return f"🔕 DND active (until {dnd_end or '?'})"
    return "🔕 DND: Off"


def _escalation_label(shared: SharedState) -> str:
    level = getattr(shared, "escalation_level", 0)
    if level == 0:
        return "🔔 Alert: Idle"
    labels = {1: "🔔 Alert: L1 (Soft)", 2: "🔔 Alert: L2 (Medium)", 3: "🔔 Alert: L3 (Urgent)"}
    return labels.get(level, f"🔔 Alert: L{level}")


def _is_paused(shared: SharedState) -> bool:
    return shared.get_detector_state() == DetectorState.PAUSED


# ---------------------------------------------------------------------------
# Menu action callbacks
# ---------------------------------------------------------------------------

def _toggle_pause(shared: SharedState, icon: pystray.Icon) -> None:
    if shared.get_detector_state() == DetectorState.PAUSED:
        shared.set_detector_state(DetectorState.WATCHING)
        logger.info("Resumed by user.")
    else:
        shared.set_detector_state(DetectorState.PAUSED)
        logger.info("Paused by user.")
    icon.update_menu()


def _toggle_sound(shared: SharedState, icon: pystray.Icon) -> None:
    with shared.lock:
        shared.sound_enabled = not shared.sound_enabled
        logger.info("Sound %s.", "enabled" if shared.sound_enabled else "disabled")
    icon.update_menu()


def _toggle_startup(shared: SharedState, icon: pystray.Icon) -> None:
    with shared.lock:
        shared.launch_on_startup = not shared.launch_on_startup
        enable = shared.launch_on_startup
    set_launch_on_startup(enable)
    icon.update_menu()


def _open_dashboard() -> None:
    """Launch the dashboard as a separate process."""
    try:
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            dash_exe = os.path.join(exe_dir, "BlinkGuardDashboard.exe")
            if os.path.isfile(dash_exe):
                subprocess.Popen([dash_exe], creationflags=subprocess.DETACHED_PROCESS)
                logger.info("Launched BlinkGuardDashboard.exe")
            else:
                logger.error("BlinkGuardDashboard.exe not found at %s", dash_exe)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            dash_py = os.path.join(base, "blink_guard", "dashboard.py")
            subprocess.Popen(
                [sys.executable, dash_py],
                creationflags=subprocess.DETACHED_PROCESS,
            )
            logger.info("Launched dashboard.py")
    except Exception:
        logger.exception("Failed to launch dashboard.")


def _quit(shared: SharedState, icon: pystray.Icon) -> None:
    logger.info("Quit requested from tray.")
    shared.shutdown_event.set()
    icon.stop()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_tray(shared: SharedState) -> None:
    """Build and run the system tray icon.  Blocks until icon.stop()."""

    def menu_factory() -> pystray.Menu:
        return pystray.Menu(
            Item(lambda _: _phase_label(shared), None, enabled=False),
            Item(lambda _: _stats_label(shared), None, enabled=False),
            Item(lambda _: _progress_label(shared), None, enabled=False),
            Item(lambda _: _dnd_label(shared), None, enabled=False),
            Item(lambda _: _escalation_label(shared), None, enabled=False),
            pystray.Menu.SEPARATOR,
            Item("📊 Open Dashboard", lambda icon, _: _open_dashboard(), default=True),
            pystray.Menu.SEPARATOR,
            Item(
                lambda _: "▶ Resume" if _is_paused(shared) else "⏸ Pause",
                lambda icon, _: _toggle_pause(shared, icon),
            ),
            Item(
                lambda _: f"🔊 Sound: {'On' if shared.sound_enabled else 'Off'}",
                lambda icon, _: _toggle_sound(shared, icon),
            ),
            Item(
                lambda _: f"🚀 Start with Windows: {'Yes' if shared.launch_on_startup else 'No'}",
                lambda icon, _: _toggle_startup(shared, icon),
            ),
            pystray.Menu.SEPARATOR,
            Item("❌ Quit", lambda icon, _: _quit(shared, icon)),
        )

    from blink_guard import __version__

    icon = pystray.Icon(
        name="BlinkGuard",
        icon=_create_eye_icon(),
        title=f"BlinkGuard v{__version__}",
        menu=menu_factory(),
    )

    logger.info("Tray icon starting.")
    icon.run()
    logger.info("Tray icon stopped.")
