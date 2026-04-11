"""
session.py — Session lifecycle helpers.

Contains the periodic settings saver (Thread 2) and the end-of-session
finalizer that records session stats, computes baselines, updates the
adaptive phase, and triggers weekly summary generation.
"""

import datetime
import logging
import time

from blink_guard.state import SharedState, Phase
from blink_guard.adaptive import (
    compute_baseline,
    update_phase,
    should_count_session,
    OBSERVATION_SESSIONS,
)
from blink_guard.risk import compute_risk_score
from blink_guard.weekly import (
    should_generate_weekly,
    generate_summary_card,
    show_toast_notification,
    record_weekly_summary,
)

logger = logging.getLogger("BlinkGuard")

# ---------------------------------------------------------------------------
# Periodic saver (Thread 2)
# ---------------------------------------------------------------------------

SAVE_INTERVAL_SECONDS = 60


def session_updater(shared: SharedState) -> None:
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

def finalise_session(shared: SharedState) -> None:
    """Compute end-of-session stats, update adaptive state, and persist."""
    duration = shared.get_session_duration_minutes()
    avg_interval = shared.get_avg_blink_interval()

    with shared.lock:
        blink_count = shared.session_blink_count
        alerts_fired = shared.session_alerts_fired
        phase = shared.phase
        threshold = shared.current_threshold
        settings = shared.settings
        escalation_counts = shared.escalation_counts

    # --- Compute risk score ---
    risk_score, risk_band, _risk_color = compute_risk_score(
        avg_interval, threshold, alerts_fired, duration
    )

    # --- Build session record ---
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

    # --- Compute baseline after enough observation sessions ---
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
