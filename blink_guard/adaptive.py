"""
adaptive.py — Baseline computation and threshold progression logic.

Implements the three-phase adaptive algorithm:
  Phase 1 (OBSERVING)    — collect blink data, compute baseline
  Phase 2 (ACTIVE)       — linearly interpolate threshold toward target
  Phase 3 (MAINTENANCE)  — hold at target, then transition to WEAN_OFF
"""

import logging
from blink_guard.state import Phase

logger = logging.getLogger("BlinkGuard")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TARGET: float = 4.0          # healthy blink interval (seconds)
MIN_BASELINE: float = 1.0           # floor for computed baseline
MAX_BASELINE: float = 25.0          # cap for very slow blinkers
OUTLIER_CEILING: float = 30.0       # discard intervals above this
SHORT_SESSION_MINUTES: float = 5.0  # sessions shorter than this don't count
HEALTHY_BASELINE: float = 5.0       # baseline at or below → short plan
SHORT_PLAN_SESSIONS: int = 7
LONG_PLAN_SESSIONS: int = 14
MAINTENANCE_GOAL: int = 7           # sessions at target before wean-off start
OBSERVATION_SESSIONS: int = 2       # silent observation sessions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_baseline(intervals: list[float]) -> float:
    """Return the clamped mean of blink intervals, ignoring outliers.

    Args:
        intervals: list of inter-blink intervals (seconds).

    Returns:
        Baseline value in [MIN_BASELINE, MAX_BASELINE].
    """
    filtered = [iv for iv in intervals if iv <= OUTLIER_CEILING]
    if not filtered:
        return MAX_BASELINE
    mean = sum(filtered) / len(filtered)
    return max(MIN_BASELINE, min(mean, MAX_BASELINE))


def compute_threshold(
    baseline: float,
    sessions_completed: int,
    total_sessions_planned: int,
    target: float = DEFAULT_TARGET,
) -> float:
    """Linearly interpolate from baseline toward target.

    progress = min(sessions_completed / total_sessions_planned, 1.0)
    threshold = baseline - (baseline - target) * progress
    """
    if total_sessions_planned <= 0:
        return target
    progress = min(sessions_completed / total_sessions_planned, 1.0)
    threshold = baseline - (baseline - target) * progress
    return round(threshold, 2)


def get_total_sessions(baseline: float) -> int:
    """Return how many active-phase sessions are needed."""
    if baseline <= HEALTHY_BASELINE:
        return SHORT_PLAN_SESSIONS
    return LONG_PLAN_SESSIONS


def should_count_session(duration_minutes: float) -> bool:
    """A session counts only if it lasted at least 5 minutes."""
    return duration_minutes >= SHORT_SESSION_MINUTES


def update_phase(settings: dict) -> dict:
    """Transition between phases based on current settings.

    Mutates and returns *settings* dict.
    """
    phase = Phase(settings.get("phase", "observing"))
    sessions = settings.get("sessions_completed", 0)
    baseline = settings.get("baseline_interval")
    total_planned = settings.get("total_sessions_planned", LONG_PLAN_SESSIONS)
    maintenance = settings.get("maintenance_sessions", 0)
    target = settings.get("target_threshold", DEFAULT_TARGET)

    if phase == Phase.OBSERVING:
        # Stay in OBSERVING until we have a computed baseline
        if baseline is not None:
            phase = Phase.ACTIVE
            total_planned = get_total_sessions(baseline)
            settings["total_sessions_planned"] = total_planned
            settings["current_threshold"] = compute_threshold(
                baseline, 0, total_planned, target
            )
            logger.info(
                "Transitioning to ACTIVE phase. Baseline=%.1fs, Plan=%d sessions",
                baseline,
                total_planned,
            )

    elif phase == Phase.ACTIVE:
        if sessions >= total_planned:
            phase = Phase.MAINTENANCE
            settings["current_threshold"] = target
            logger.info("Transitioning to MAINTENANCE phase.")
        else:
            settings["current_threshold"] = compute_threshold(
                baseline, sessions, total_planned, target  # type: ignore[arg-type]
            )

    elif phase == Phase.MAINTENANCE:
        if maintenance >= MAINTENANCE_GOAL:
            phase = Phase.WEAN_OFF
            logger.info("Transitioning to WEAN_OFF phase.")

    # WEAN_OFF stays as-is indefinitely
    settings["phase"] = phase.value
    return settings
