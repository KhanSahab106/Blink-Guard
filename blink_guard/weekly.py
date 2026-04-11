"""
weekly.py — Weekly Summary Card generation.

Generates an 800x450 PNG summary card using Pillow with session stats,
a 7-day bar chart, and phase/streak info. Also triggers a Windows toast.
"""

import os
import sys
import json
import datetime
import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("BlinkGuard")

# Colors
BG = "#1e1e1e"
ACCENT = "#007acc"
SURFACE = "#252526"
TEXT = "#d4d4d4"
MUTED = "#858585"
GREEN = "#4ec94e"
YELLOW = "#e5c07b"
RED = "#e06c75"
ORANGE = "#d19a66"


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _summaries_dir() -> str:
    """Return %APPDATA%/BlinkGuard/summaries/ ensuring it exists."""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    d = os.path.join(appdata, "BlinkGuard", "summaries")
    os.makedirs(d, exist_ok=True)
    return d


from blink_guard.defaults import settings_path, load_settings_from_disk


def _load_settings() -> dict:
    return load_settings_from_disk()


def should_generate_weekly(settings: dict) -> bool:
    """Check if a weekly summary should be generated (Monday, first session)."""
    today = datetime.date.today()
    if today.weekday() != 0:  # Not Monday
        return False

    summaries: list = settings.get("weekly_summaries", [])
    if summaries:
        last_date = summaries[-1].get("date", "")
        if last_date == today.isoformat():
            return False  # Already generated today

    # Check if any sessions exist in past 7 days
    history = settings.get("session_history", [])
    cutoff = (today - datetime.timedelta(days=7)).isoformat()
    recent = [s for s in history if s.get("date", "") >= cutoff]
    return len(recent) > 0


def _compute_weekly_stats(settings: dict) -> dict[str, Any]:
    """Compute stats from the past 7 days of session history."""
    today = datetime.date.today()
    cutoff = (today - datetime.timedelta(days=7)).isoformat()
    start_date = (today - datetime.timedelta(days=6)).isoformat()

    history = settings.get("session_history", [])
    recent = [s for s in history if s.get("date", "") >= cutoff]

    if not recent:
        return {}

    total_sessions = len(recent)
    total_blinks = sum(s.get("total_blinks", 0) for s in recent)
    all_avgs = [s.get("avg_blink_interval", 0) for s in recent if s.get("avg_blink_interval")]
    avg_interval = sum(all_avgs) / len(all_avgs) if all_avgs else 0
    total_alerts = sum(s.get("alerts_fired", 0) for s in recent)

    # Best/worst session
    best = min(all_avgs) if all_avgs else 0
    worst = max(all_avgs) if all_avgs else 0

    # Risk scores
    risk_scores = [s.get("risk_score", 0) for s in recent if "risk_score" in s]
    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0

    # Streak: consecutive days at or below threshold
    streak = 0
    threshold = settings.get("current_threshold", None)
    if threshold:
        for i in range(7):
            day = (today - datetime.timedelta(days=i)).isoformat()
            day_sessions = [s for s in history if s.get("date") == day]
            if day_sessions:
                day_avg = sum(s.get("avg_blink_interval", 0) for s in day_sessions) / len(day_sessions)
                if day_avg <= threshold:
                    streak += 1
                else:
                    break
            else:
                break

    # Per-day averages for bar chart (last 7 days)
    daily_avgs = []
    for i in range(6, -1, -1):
        day = (today - datetime.timedelta(days=i)).isoformat()
        day_sessions = [s for s in history if s.get("date") == day]
        if day_sessions:
            day_avgs_list = [s.get("avg_blink_interval", 0) for s in day_sessions if s.get("avg_blink_interval")]
            avg = sum(day_avgs_list) / len(day_avgs_list) if day_avgs_list else 0
            daily_avgs.append((day, avg))
        else:
            daily_avgs.append((day, 0))

    # Threshold change
    threshold_start = None
    threshold_end = settings.get("current_threshold")
    # Find threshold at start of week from history
    for s in history:
        if s.get("date", "") >= cutoff:
            threshold_start = s.get("threshold_used")
            break
    improvement = 0.0
    if threshold_start and threshold_end:
        improvement = threshold_start - threshold_end

    return {
        "date_range": f"{start_date} – {today.isoformat()}",
        "total_sessions": total_sessions,
        "total_blinks": total_blinks,
        "avg_interval": round(avg_interval, 1),
        "best_session": round(best, 1),
        "worst_session": round(worst, 1),
        "total_alerts": total_alerts,
        "avg_risk": round(avg_risk, 0),
        "streak_days": streak,
        "daily_avgs": daily_avgs,
        "threshold_improvement": round(improvement, 1),
        "phase": settings.get("phase", "observing"),
    }


def generate_summary_card(settings: dict | None = None) -> str | None:
    """Generate the weekly summary PNG. Returns path to saved image or None."""
    if settings is None:
        settings = _load_settings()

    stats = _compute_weekly_stats(settings)
    if not stats:
        return None

    W, H = 800, 450
    img = Image.new("RGB", (W, H), _hex_to_rgb(BG))
    draw = ImageDraw.Draw(img)

    # Try to load a nice font, fall back to default
    try:
        font_lg = ImageFont.truetype("segoeui.ttf", 22)
        font_md = ImageFont.truetype("segoeui.ttf", 14)
        font_sm = ImageFont.truetype("segoeui.ttf", 11)
        font_val = ImageFont.truetype("segoeuib.ttf", 20)
    except (OSError, IOError):
        font_lg = ImageFont.load_default()
        font_md = ImageFont.load_default()
        font_sm = ImageFont.load_default()
        font_val = ImageFont.load_default()

    # --- Header bar ---
    draw.rectangle([0, 0, W, 50], fill=_hex_to_rgb(ACCENT))
    draw.text((20, 12), "BlinkGuard — Weekly Summary", fill=(255, 255, 255), font=font_lg)
    draw.text((W - 220, 18), stats.get("date_range", ""), fill=(200, 220, 255), font=font_sm)

    # --- Stats grid (2x3) ---
    stat_cards = [
        ("Sessions", str(stats["total_sessions"])),
        ("Total Blinks", str(stats["total_blinks"])),
        ("Avg Interval", f"{stats['avg_interval']}s"),
        ("Alerts Fired", str(stats["total_alerts"])),
        ("Best Session", f"{stats['best_session']}s"),
        ("Avg Risk Score", f"{int(stats['avg_risk'])}"),
    ]

    card_w, card_h = 240, 65
    start_x, start_y = 20, 65
    gap_x, gap_y = 15, 10

    for idx, (label, value) in enumerate(stat_cards):
        col = idx % 3
        row = idx // 3
        x = start_x + col * (card_w + gap_x)
        y = start_y + row * (card_h + gap_y)

        draw.rounded_rectangle([x, y, x + card_w, y + card_h],
                               radius=6, fill=_hex_to_rgb(SURFACE))
        draw.text((x + 12, y + 8), label, fill=_hex_to_rgb(MUTED), font=font_sm)
        draw.text((x + 12, y + 28), value, fill=_hex_to_rgb(TEXT), font=font_val)

    # --- 7-day bar chart ---
    chart_y = start_y + 2 * (card_h + gap_y) + 15
    chart_h = 120
    chart_x = 30
    chart_w = W - 200

    draw.text((chart_x, chart_y - 5), "Daily Avg Interval", fill=_hex_to_rgb(MUTED), font=font_sm)
    chart_y += 15

    daily = stats.get("daily_avgs", [])
    threshold = settings.get("current_threshold", 8.0)
    max_val = max((d[1] for d in daily if d[1] > 0), default=10.0) * 1.2

    bar_width = chart_w // max(len(daily), 1) - 6
    for i, (day_str, avg) in enumerate(daily):
        if avg <= 0:
            continue
        bar_h = int((avg / max_val) * (chart_h - 20))
        bx = chart_x + i * (bar_width + 6)
        by = chart_y + chart_h - bar_h - 15

        # Color by risk
        if threshold and avg <= threshold:
            color = _hex_to_rgb(GREEN)
        elif threshold and avg <= threshold + 3:
            color = _hex_to_rgb(YELLOW)
        else:
            color = _hex_to_rgb(RED)

        draw.rounded_rectangle([bx, by, bx + bar_width, chart_y + chart_h - 15],
                               radius=3, fill=color)

        # Day label
        try:
            day_label = day_str.split("-")[2]  # just day number
        except (IndexError, AttributeError):
            day_label = "?"
        draw.text((bx + bar_width // 2 - 5, chart_y + chart_h - 12),
                  day_label, fill=_hex_to_rgb(MUTED), font=font_sm)

    # --- Phase badge + streak (bottom right) ---
    phase = stats.get("phase", "observing").upper().replace("_", "-")
    streak = stats.get("streak_days", 0)
    improvement = stats.get("threshold_improvement", 0)

    rx = W - 170
    ry = chart_y + 5

    draw.rounded_rectangle([rx, ry, rx + 150, ry + 30], radius=6, fill=_hex_to_rgb(ACCENT))
    draw.text((rx + 10, ry + 6), f"Phase: {phase}", fill=(255, 255, 255), font=font_sm)

    draw.text((rx, ry + 40), f"🔥 Streak: {streak} days", fill=_hex_to_rgb(TEXT), font=font_md)

    if improvement > 0:
        draw.text((rx, ry + 65), f"⬇ Improved by {improvement}s",
                  fill=_hex_to_rgb(GREEN), font=font_sm)

    # --- Save ---
    today_str = datetime.date.today().isoformat()
    filename = f"summary_{today_str}.png"
    save_path = os.path.join(_summaries_dir(), filename)
    img.save(save_path, "PNG")
    logger.info("Weekly summary saved: %s", save_path)

    return save_path


def show_toast_notification(image_path: str, improvement: float = 0.0) -> None:
    """Show a Windows toast notification with the summary image."""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        body = f"Avg interval improved by {improvement}s this week" if improvement > 0 else "Your weekly BlinkGuard summary is ready"
        toaster.show_toast(
            "Your Weekly BlinkGuard Summary",
            body,
            icon_path=None,
            duration=10,
            threaded=True,
        )
    except ImportError:
        # win10toast not available, try subprocess approach
        try:
            os.startfile(image_path)
        except Exception:
            logger.warning("Could not show toast notification")
    except Exception:
        logger.exception("Failed to show toast notification")


def record_weekly_summary(settings: dict, image_path: str) -> None:
    """Record the summary in settings.json."""
    summaries = settings.setdefault("weekly_summaries", [])
    summaries.append({
        "date": datetime.date.today().isoformat(),
        "path": image_path,
    })
    # Keep last 52 weeks
    if len(summaries) > 52:
        settings["weekly_summaries"] = summaries[-52:]
