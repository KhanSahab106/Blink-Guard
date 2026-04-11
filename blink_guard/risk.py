"""
risk.py — Eye Strain Risk Score computation.

Computes a 0-100 risk score at the end of each session based on:
  • alert_rate (alerts per minute)
  • interval_ratio (avg interval vs threshold)
  • session duration penalty
"""

import logging

logger = logging.getLogger("BlinkGuard")

# Risk bands
BANDS = [
    (25, "Low", "#4ec94e"),
    (50, "Moderate", "#e5c07b"),
    (75, "High", "#d19a66"),
    (100, "Severe", "#e06c75"),
]


def compute_risk_score(
    avg_blink_interval: float | None,
    current_threshold: float | None,
    alerts_fired: int,
    session_duration_minutes: float,
) -> tuple[int, str, str]:
    """Compute the eye strain risk score.

    Returns:
        (score, band_name, band_color)
    """
    if current_threshold is None or current_threshold <= 0:
        return 0, "Low", "#4ec94e"

    interval_ratio = (avg_blink_interval or 0) / current_threshold
    alert_rate = alerts_fired / max(session_duration_minutes, 0.1)

    base_score = (interval_ratio * 50) + (alert_rate * 30)

    # Length penalty
    if session_duration_minutes < 30:
        length_penalty = 0
    elif session_duration_minutes <= 60:
        length_penalty = 5
    elif session_duration_minutes <= 120:
        length_penalty = 15
    else:
        length_penalty = 25

    raw_score = base_score + length_penalty
    score = int(min(max(raw_score, 0), 100))

    # Determine band
    band_name = "Low"
    band_color = "#4ec94e"
    for threshold, name, color in BANDS:
        if score <= threshold:
            band_name = name
            band_color = color
            break

    return score, band_name, band_color


def get_band(score: int) -> tuple[str, str]:
    """Get the band name and color for a given score."""
    for threshold, name, color in BANDS:
        if score <= threshold:
            return name, color
    return "Severe", "#e06c75"
