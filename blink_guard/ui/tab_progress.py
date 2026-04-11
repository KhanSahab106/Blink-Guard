"""
tab_progress.py — Progress tab.

Shows:
  1. Habit Journey circular progress ring
  2. Threshold progression chart (matplotlib)
  3. Time-of-Day Heatmap (24-column grid)
  4. Risk Score 30-day trend sparkline
  5. Baseline info card
"""

import json
import os
import sys
import logging
import datetime

import customtkinter as ctk

logger = logging.getLogger("BlinkGuard.Dashboard")

# Palette
BG_DARK = "#1e1e1e"
SURFACE = "#252526"
ACCENT = "#007acc"
ACCENT_HOVER = "#1a8ad4"
TEXT_PRIMARY = "#d4d4d4"
TEXT_MUTED = "#858585"
BORDER = "#3c3c3c"
RED = "#f44747"
GREEN = "#4ec94e"
ORANGE = "#cca700"
YELLOW = "#e5c07b"

PHASE_COLORS = {
    "observing": "#569cd6",
    "active": "#dcdcaa",
    "maintenance": "#4ec94e",
    "wean_off": "#c586c0",
}

PHASE_LABELS = {
    "observing": "OBSERVING",
    "active": "ACTIVE",
    "maintenance": "MAINTENANCE",
    "wean_off": "WEAN-OFF",
}


from blink_guard.defaults import load_settings_from_disk, save_settings_to_disk


def _load_settings() -> dict:
    return load_settings_from_disk()


class ProgressTab(ctk.CTkFrame):
    """Progress tab showing journey, charts, heatmap, and risk trend."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG_DARK, corner_radius=0)
        self.app = app
        self._chart_widget = None
        self._risk_chart_widget = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=BG_DARK, corner_radius=0,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color="#555555",
        )
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_journey_card()
        self._build_threshold_chart()
        self._build_heatmap()
        self._build_risk_trend()
        self._build_baseline_card()

    # ---- Journey Card ---------------------------------------------------

    def _build_journey_card(self) -> None:
        card = ctk.CTkFrame(self._scroll, fg_color=SURFACE, corner_radius=10)
        card.pack(fill="x", padx=20, pady=(16, 10))

        ctk.CTkLabel(
            card, text="Habit Journey",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 8))

        ring_frame = ctk.CTkFrame(card, fg_color="transparent")
        ring_frame.pack(fill="x", padx=20, pady=(0, 8))

        self._ring_canvas = ctk.CTkCanvas(
            ring_frame, bg=SURFACE, highlightthickness=0,
            width=200, height=200,
        )
        self._ring_canvas.pack(pady=4)

        self._journey_status = ctk.CTkLabel(
            card, text="Collecting observation data...",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self._journey_status.pack(padx=20, pady=(0, 4))

        self._journey_phase_badge = ctk.CTkLabel(
            card, text="OBSERVING",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#1e1e1e",
            fg_color="#569cd6",
            corner_radius=6,
            width=120, height=26,
        )
        self._journey_phase_badge.pack(padx=20, pady=(0, 16))

    def _draw_progress_ring(self, progress: float, center_text: str) -> None:
        canvas = self._ring_canvas
        canvas.delete("all")
        size = 200
        pad = 20
        cx, cy = size // 2, size // 2
        line_width = 12

        canvas.create_arc(
            pad, pad, size - pad, size - pad,
            start=90, extent=-360,
            style="arc", outline=BORDER, width=line_width,
        )

        if progress > 0:
            extent = -360 * min(progress, 1.0)
            canvas.create_arc(
                pad, pad, size - pad, size - pad,
                start=90, extent=extent,
                style="arc", outline=ACCENT, width=line_width,
            )

        canvas.create_text(
            cx, cy - 8, text=center_text,
            fill=TEXT_PRIMARY, font=("Segoe UI", 24, "bold"),
        )
        canvas.create_text(
            cx, cy + 18, text=f"{progress * 100:.0f}%",
            fill=TEXT_MUTED, font=("Segoe UI", 12),
        )

    # ---- Threshold Chart ------------------------------------------------

    def _build_threshold_chart(self) -> None:
        card = ctk.CTkFrame(self._scroll, fg_color=SURFACE, corner_radius=10)
        card.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            card, text="Threshold Progression",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 8))

        self._chart_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._chart_frame.pack(fill="x", padx=12, pady=(0, 16))

        self._chart_placeholder = ctk.CTkLabel(
            self._chart_frame, text="No session data yet",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=200,
        )
        self._chart_placeholder.pack(fill="x", padx=8, pady=8)

    def _render_threshold_chart(self, settings: dict) -> None:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            return

        history = settings.get("session_history", [])
        baseline = settings.get("baseline_interval")
        target = settings.get("target_threshold", 4.0)

        if not history:
            return

        if self._chart_widget:
            self._chart_widget.get_tk_widget().destroy()
        self._chart_placeholder.pack_forget()

        thresholds = [s.get("threshold_used", 0) for s in history if s.get("threshold_used")]
        sessions = list(range(1, len(thresholds) + 1))

        if not thresholds:
            return

        fig, ax = plt.subplots(figsize=(6, 2.5), dpi=100)
        fig.patch.set_facecolor(SURFACE)
        ax.set_facecolor("#1a1a1a")

        ax.plot(sessions, thresholds, color=ACCENT, linewidth=2, marker="o",
                markersize=4, zorder=5)
        ax.fill_between(sessions, thresholds, target, alpha=0.15, color=ACCENT)
        ax.axhline(y=target, color=GREEN, linestyle="--", linewidth=1, alpha=0.8)
        ax.text(len(sessions) + 0.3, target, "Target", color=GREEN,
                fontsize=8, va="center")

        if baseline:
            ax.axhline(y=baseline, color=ORANGE, linestyle="--", linewidth=1, alpha=0.6)
            ax.text(len(sessions) + 0.3, baseline, "Baseline", color=ORANGE,
                    fontsize=8, va="center")

        ax.set_xlabel("Session", color=TEXT_MUTED, fontsize=9)
        ax.set_ylabel("Seconds", color=TEXT_MUTED, fontsize=9)
        ax.tick_params(colors=TEXT_MUTED, labelsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color(BORDER)
        ax.spines["left"].set_color(BORDER)
        ax.grid(axis="y", color=BORDER, alpha=0.3)

        fig.tight_layout(pad=1.5)

        self._chart_widget = FigureCanvasTkAgg(fig, master=self._chart_frame)
        self._chart_widget.draw()
        self._chart_widget.get_tk_widget().pack(fill="x", padx=4, pady=4)

        plt.close(fig)

    # ---- Time-of-Day Heatmap -------------------------------------------

    def _build_heatmap(self) -> None:
        card = ctk.CTkFrame(self._scroll, fg_color=SURFACE, corner_radius=10)
        card.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            card, text="Time-of-Day Blink Health",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 8))

        self._heatmap_canvas = ctk.CTkCanvas(
            card, bg=SURFACE, highlightthickness=0, height=90,
        )
        self._heatmap_canvas.pack(fill="x", padx=16, pady=(0, 4))

        # Tooltip label (hidden initially)
        self._heatmap_tooltip = ctk.CTkLabel(
            card, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        self._heatmap_tooltip.pack(padx=20, pady=(0, 4))

        # Insight text
        self._heatmap_insight = ctk.CTkLabel(
            card, text="",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self._heatmap_insight.pack(padx=20, pady=(0, 16))

    def _render_heatmap(self, settings: dict) -> None:
        canvas = self._heatmap_canvas
        canvas.delete("all")

        w = canvas.winfo_width()
        if w < 50:
            w = 700  # fallback

        hourly = settings.get("hourly_data", {})
        threshold = settings.get("current_threshold", 8.0)

        cell_w = max(w // 24 - 2, 16)
        cell_h = 40
        y_top = 10
        y_label = y_top + cell_h + 4

        # Color mapping
        def _hour_color(avg_interval):
            if avg_interval is None:
                return BORDER
            if threshold and avg_interval <= threshold:
                return GREEN
            elif threshold and avg_interval <= threshold + 3:
                return YELLOW
            else:
                return RED

        hour_avgs = {}
        worst_window = None
        worst_window_avg = 0

        for h in range(24):
            hk = f"{h:02d}"
            data = hourly.get(hk, {})
            intervals = data.get("total_intervals", [])
            alerts = data.get("alert_count", 0)

            if intervals:
                avg = sum(intervals) / len(intervals)
                hour_avgs[h] = avg
            else:
                hour_avgs[h] = None

            x = h * (cell_w + 2) + 4
            color = _hour_color(hour_avgs[h])

            canvas.create_rectangle(
                x, y_top, x + cell_w, y_top + cell_h,
                fill=color, outline="#2a2a2a", width=1,
            )

            # Show dash if no data
            if not intervals:
                canvas.create_text(
                    x + cell_w // 2, y_top + cell_h // 2,
                    text="—", fill=TEXT_MUTED, font=("Segoe UI", 8),
                )

            # Hour label (every 3 hours)
            if h % 3 == 0:
                canvas.create_text(
                    x + cell_w // 2, y_label + 4,
                    text=f"{h:02d}", fill=TEXT_MUTED, font=("Segoe UI", 8),
                )

        # Bind hover events
        def _on_hover(event):
            cx = event.x - 4
            h_idx = int(cx / (cell_w + 2))
            if 0 <= h_idx < 24:
                hk = f"{h_idx:02d}"
                data = hourly.get(hk, {})
                intervals = data.get("total_intervals", [])
                alerts = data.get("alert_count", 0)
                if intervals:
                    avg = sum(intervals) / len(intervals)
                    self._heatmap_tooltip.configure(
                        text=f"{h_idx:02d}:00–{h_idx+1:02d}:00 — "
                             f"Avg interval: {avg:.1f}s — {alerts} alerts — "
                             f"{len(intervals)} readings"
                    )
                else:
                    self._heatmap_tooltip.configure(
                        text=f"{h_idx:02d}:00–{h_idx+1:02d}:00 — No data"
                    )

        canvas.bind("<Motion>", _on_hover)

        # Compute worst 2-hour window
        for h in range(23):
            a1 = hour_avgs.get(h)
            a2 = hour_avgs.get(h + 1)
            if a1 is not None and a2 is not None:
                window_avg = (a1 + a2) / 2
                if window_avg > worst_window_avg:
                    worst_window_avg = window_avg
                    worst_window = (h, h + 2)

        if worst_window and worst_window_avg > 0:
            self._heatmap_insight.configure(
                text=f"⚠ Your eyes are most strained between "
                     f"{worst_window[0]:02d}:00–{worst_window[1]:02d}:00"
            )
        else:
            self._heatmap_insight.configure(text="")

    # ---- Risk Score Trend -----------------------------------------------

    def _build_risk_trend(self) -> None:
        card = ctk.CTkFrame(self._scroll, fg_color=SURFACE, corner_radius=10)
        card.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            card, text="30-Day Risk Score Trend",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 8))

        self._risk_chart_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._risk_chart_frame.pack(fill="x", padx=12, pady=(0, 8))

        self._risk_placeholder = ctk.CTkLabel(
            self._risk_chart_frame, text="No risk data yet",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=80,
        )
        self._risk_placeholder.pack(fill="x", padx=8, pady=8)

        # Summary label
        self._risk_avg_label = ctk.CTkLabel(
            card, text="",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self._risk_avg_label.pack(padx=20, pady=(0, 16))

    def _render_risk_trend(self, settings: dict) -> None:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            return

        history = settings.get("session_history", [])
        # Filter sessions with risk scores from last 30 days
        cutoff = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        recent = [s for s in history
                 if "risk_score" in s and s.get("date", "") >= cutoff]

        if not recent:
            return

        if self._risk_chart_widget:
            self._risk_chart_widget.get_tk_widget().destroy()
        self._risk_placeholder.pack_forget()

        scores = [s.get("risk_score", 0) for s in recent]
        indices = list(range(1, len(scores) + 1))

        fig, ax = plt.subplots(figsize=(6, 1.5), dpi=100)
        fig.patch.set_facecolor(SURFACE)
        ax.set_facecolor("#1a1a1a")

        # Color each point by risk band
        from blink_guard.risk import get_band
        colors = [get_band(s)[1] for s in scores]

        ax.plot(indices, scores, color=ACCENT, linewidth=1.5, alpha=0.7)
        ax.scatter(indices, scores, c=colors, s=20, zorder=5)

        # Risk band lines
        ax.axhline(y=25, color=GREEN, linestyle=":", linewidth=0.5, alpha=0.5)
        ax.axhline(y=50, color=YELLOW, linestyle=":", linewidth=0.5, alpha=0.5)
        ax.axhline(y=75, color=RED, linestyle=":", linewidth=0.5, alpha=0.5)

        ax.set_ylim(0, 100)
        ax.set_ylabel("Risk", color=TEXT_MUTED, fontsize=8)
        ax.tick_params(colors=TEXT_MUTED, labelsize=7)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color(BORDER)
        ax.spines["left"].set_color(BORDER)

        fig.tight_layout(pad=1.0)

        self._risk_chart_widget = FigureCanvasTkAgg(fig, master=self._risk_chart_frame)
        self._risk_chart_widget.draw()
        self._risk_chart_widget.get_tk_widget().pack(fill="x", padx=4, pady=4)

        plt.close(fig)

        # Summary
        avg_risk = sum(scores) / len(scores)
        band_name, band_color = get_band(int(avg_risk))
        self._risk_avg_label.configure(
            text=f"30-day avg: {avg_risk:.0f} ({band_name})",
            text_color=band_color,
        )

    # ---- Baseline Card --------------------------------------------------

    def _build_baseline_card(self) -> None:
        card = ctk.CTkFrame(self._scroll, fg_color=SURFACE, corner_radius=10)
        card.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkLabel(
            card, text="Baseline",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 8))

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(fill="x", padx=20, pady=(0, 8))

        self._baseline_labels: dict[str, ctk.CTkLabel] = {}
        for key, label in [
            ("interval", "Baseline interval"),
            ("date", "Recorded on"),
            ("sessions", "Observation sessions"),
        ]:
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row, text=label, text_color=TEXT_MUTED,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            val = ctk.CTkLabel(
                row, text="—", text_color=TEXT_PRIMARY,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                anchor="e",
            )
            val.grid(row=0, column=1, sticky="e")
            self._baseline_labels[key] = val

        self._reobserve_btn = ctk.CTkButton(
            card, text="Re-observe Baseline",
            fg_color=BORDER, hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            width=180, height=32,
            command=self._confirm_reobserve,
        )
        self._reobserve_btn.pack(padx=20, pady=(4, 16))

    def _confirm_reobserve(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Re-observation")
        dialog.geometry("420x180")
        dialog.configure(fg_color=SURFACE)
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - 420) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - 180) // 2
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog, text="⚠️ Re-observe Baseline",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(padx=24, pady=(20, 8))

        ctk.CTkLabel(
            dialog, text="This will restart your habit journey.\nAll progress will be reset.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_MUTED,
        ).pack(padx=24, pady=(0, 16))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 16))

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=BORDER, hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY,
            command=dialog.destroy,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_frame, text="Reset", width=100,
            fg_color=RED, hover_color="#d43a3a",
            text_color="#ffffff",
            command=lambda: self._do_reobserve(dialog),
        ).pack(side="right")

    def _do_reobserve(self, dialog) -> None:
        dialog.destroy()
        if self.app.ipc.connected:
            self.app.ipc.set_setting("phase", "observing")
            self.app.ipc.set_setting("baseline_interval", None)
            self.app.ipc.set_setting("sessions_completed", 0)
            self.app.ipc.set_setting("current_threshold", None)

        try:
            settings = _load_settings()
            settings["phase"] = "observing"
            settings["baseline_interval"] = None
            settings["sessions_completed"] = 0
            settings["current_threshold"] = None
            settings["maintenance_sessions"] = 0
            save_settings_to_disk(settings)
        except Exception:
            logger.exception("Failed to reset settings")
        self._refresh_data()

    # ---- Refresh --------------------------------------------------------

    def _refresh_data(self) -> None:
        settings = _load_settings()

        baseline = settings.get("baseline_interval")
        threshold = settings.get("current_threshold")
        target = settings.get("target_threshold", 4.0)
        phase = settings.get("phase", "observing")
        sessions_completed = settings.get("sessions_completed", 0)
        total_planned = settings.get("total_sessions_planned", 14)

        # Journey ring
        if baseline is None or threshold is None or (baseline is not None and target is not None and baseline <= target):
            progress = 0.0
            center_text = "—"
            status_text = "Collecting observation data..."
        else:
            progress = (baseline - threshold) / (baseline - target)
            progress = max(0.0, min(progress, 1.0))
            center_text = f"{threshold:.1f}s"
            remaining = max(total_planned - sessions_completed, 0)
            if progress >= 1.0:
                status_text = "🎉 Target reached!"
            else:
                status_text = f"{remaining} sessions to go"

        self._draw_progress_ring(progress, center_text)
        self._journey_status.configure(text=status_text)

        phase_color = PHASE_COLORS.get(phase, ACCENT)
        phase_label = PHASE_LABELS.get(phase, phase.upper())
        self._journey_phase_badge.configure(text=phase_label, fg_color=phase_color)

        # Baseline card
        if baseline:
            self._baseline_labels["interval"].configure(text=f"{baseline:.1f}s")
        else:
            self._baseline_labels["interval"].configure(text="Not recorded yet")

        history = settings.get("session_history", [])
        if history:
            self._baseline_labels["date"].configure(text=history[0].get("date", "—"))
        else:
            self._baseline_labels["date"].configure(text="—")

        obs_count = min(len(history), 2)
        self._baseline_labels["sessions"].configure(text=str(obs_count))

        # Charts
        self._render_threshold_chart(settings)
        self._render_heatmap(settings)
        self._render_risk_trend(settings)

    def on_tab_selected(self) -> None:
        self._refresh_data()

    def update_live_state(self, state: dict) -> None:
        pass
