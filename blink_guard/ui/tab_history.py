"""
tab_history.py — Session History tab.

Shows:
  1. Risk score gauge (most recent session)
  2. Bar chart of avg blink interval per session
  3. Scrollable session table with Risk + Escalation columns
  4. Summary stats row
  5. Weekly Summaries gallery
"""

import json
import os
import sys
import subprocess
import logging

import customtkinter as ctk

logger = logging.getLogger("BlinkGuard.Dashboard")

# Palette
BG_DARK = "#1e1e1e"
SURFACE = "#252526"
ACCENT = "#007acc"
TEXT_PRIMARY = "#d4d4d4"
TEXT_MUTED = "#858585"
BORDER = "#3c3c3c"
RED = "#f44747"
GREEN = "#4ec94e"
ORANGE = "#cca700"
YELLOW = "#e5c07b"

PHASE_LABELS = {
    "observing": "OBS",
    "active": "ACT",
    "maintenance": "MNT",
    "wean_off": "W-O",
}

RISK_COLORS = {
    "Low": GREEN,
    "Moderate": YELLOW,
    "High": "#d19a66",
    "Severe": RED,
}


from blink_guard.defaults import load_settings_from_disk


def _load_settings() -> dict:
    return load_settings_from_disk()


class HistoryTab(ctk.CTkFrame):
    """Session History tab with risk gauge, chart, table, and weekly summaries."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG_DARK, corner_radius=0)
        self.app = app
        self._chart_widget = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=BG_DARK, corner_radius=0,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color="#555555",
        )
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_risk_gauge()
        self._build_chart_area()
        self._build_table_area()
        self._build_weekly_section()

    # ---- Risk Gauge (most recent session) --------------------------------

    def _build_risk_gauge(self) -> None:
        card = ctk.CTkFrame(self._scroll, fg_color=SURFACE, corner_radius=10)
        card.pack(fill="x", padx=16, pady=(16, 8))

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="Latest Session Risk",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._gauge_canvas = ctk.CTkCanvas(
            card, bg=SURFACE, highlightthickness=0, width=200, height=120,
        )
        self._gauge_canvas.pack(pady=(0, 4))

        self._gauge_label = ctk.CTkLabel(
            card, text="No data", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self._gauge_label.pack(padx=20, pady=(0, 16))

    def _draw_risk_gauge(self, score: int, band: str) -> None:
        canvas = self._gauge_canvas
        canvas.delete("all")

        cx, cy = 100, 100
        r = 80
        line_w = 12

        # Background arc (semicircle)
        canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=0, extent=180,
            style="arc", outline=BORDER, width=line_w,
        )

        # Score arc
        extent = (score / 100.0) * 180
        color = RISK_COLORS.get(band, ACCENT)
        canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=180, extent=-extent,
            style="arc", outline=color, width=line_w,
        )

        # Score text
        canvas.create_text(cx, cy - 20, text=str(score),
                          fill=TEXT_PRIMARY, font=("Segoe UI", 28, "bold"))
        canvas.create_text(cx, cy + 8, text=band,
                          fill=color, font=("Segoe UI", 12))

    # ---- Chart Area -----------------------------------------------------

    def _build_chart_area(self) -> None:
        card = ctk.CTkFrame(self._scroll, fg_color=SURFACE, corner_radius=10)
        card.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            card, text="Average Blink Interval Over Time",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(12, 4))

        self._chart_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._chart_frame.pack(fill="x", padx=8, pady=(0, 8))

        self._chart_placeholder = ctk.CTkLabel(
            self._chart_frame, text="No session data yet",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=180,
        )
        self._chart_placeholder.pack(fill="x", padx=8)

    def _render_chart(self, history: list) -> None:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            return

        if not history:
            return

        if self._chart_widget:
            self._chart_widget.get_tk_widget().destroy()
        self._chart_placeholder.pack_forget()

        dates = [s.get("date", "?") for s in history]
        avgs = [s.get("avg_blink_interval", 0) for s in history]
        thresholds = [s.get("threshold_used", 0) for s in history]

        colors = []
        for avg, thr in zip(avgs, thresholds):
            if thr and avg > thr:
                colors.append(RED)
            else:
                colors.append(GREEN)

        fig, ax = plt.subplots(figsize=(6, 2.2), dpi=100)
        fig.patch.set_facecolor(SURFACE)
        ax.set_facecolor("#1a1a1a")

        x = range(len(dates))
        ax.bar(x, avgs, color=colors, alpha=0.85, width=0.6, zorder=5)

        ax.set_xticks(list(x))
        short_dates = []
        for d in dates:
            try:
                parts = d.split("-")
                short_dates.append(f"{parts[1]}/{parts[2]}")
            except (IndexError, AttributeError):
                short_dates.append(d)
        ax.set_xticklabels(short_dates, rotation=45, ha="right")

        ax.set_ylabel("Seconds", color=TEXT_MUTED, fontsize=9)
        ax.tick_params(colors=TEXT_MUTED, labelsize=7)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color(BORDER)
        ax.spines["left"].set_color(BORDER)
        ax.grid(axis="y", color=BORDER, alpha=0.3)

        fig.tight_layout(pad=1.0)

        self._chart_widget = FigureCanvasTkAgg(fig, master=self._chart_frame)
        self._chart_widget.draw()
        self._chart_widget.get_tk_widget().pack(fill="x", padx=4, pady=4)
        plt.close(fig)

    # ---- Table Area (with Risk + Escalation columns) --------------------

    def _build_table_area(self) -> None:
        card = ctk.CTkFrame(self._scroll, fg_color=SURFACE, corner_radius=10)
        card.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            card, text="Session Log",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(12, 4))

        # Header
        columns = ["Date", "Dur.", "Blinks", "Avg", "Alerts", "Risk", "Esc.", "Phase"]
        weights = [3, 2, 2, 2, 2, 2, 2, 2]

        self._header_frame = ctk.CTkFrame(card, fg_color="#2a2a2a", corner_radius=0, height=32)
        self._header_frame.pack(fill="x", padx=8, pady=(4, 0))
        self._header_frame.pack_propagate(False)

        for i, (col, w) in enumerate(zip(columns, weights)):
            self._header_frame.grid_columnconfigure(i, weight=w)
            ctk.CTkLabel(
                self._header_frame, text=col,
                text_color=TEXT_MUTED,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            ).grid(row=0, column=i, sticky="ew", padx=4, pady=6)

        # Scrollable body
        self._table_scroll = ctk.CTkScrollableFrame(
            card, fg_color="#1a1a1a", corner_radius=0, height=200,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color="#555555",
        )
        self._table_scroll.pack(fill="x", padx=8, pady=(0, 4))
        for i in range(8):
            self._table_scroll.grid_columnconfigure(i, weight=weights[i])

        # Summary row
        self._summary_frame = ctk.CTkFrame(card, fg_color="#2a2a2a", corner_radius=0, height=32)
        self._summary_frame.pack(fill="x", padx=8, pady=(0, 8))
        self._summary_frame.pack_propagate(False)
        for i in range(8):
            self._summary_frame.grid_columnconfigure(i, weight=weights[i])

        self._table_placeholder = ctk.CTkLabel(
            self._table_scroll, text="No sessions recorded yet",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self._table_placeholder.grid(row=0, column=0, columnspan=8, sticky="ew", pady=20)

    def _populate_table(self, history: list) -> None:
        for widget in self._table_scroll.winfo_children():
            widget.destroy()

        if not history:
            self._table_placeholder = ctk.CTkLabel(
                self._table_scroll, text="No sessions recorded yet",
                text_color=TEXT_MUTED,
                font=ctk.CTkFont(family="Segoe UI", size=12),
            )
            self._table_placeholder.grid(row=0, column=0, columnspan=8, sticky="ew", pady=20)
            return

        weights = [3, 2, 2, 2, 2, 2, 2, 2]
        for i in range(8):
            self._table_scroll.grid_columnconfigure(i, weight=weights[i])

        for row_idx, session in enumerate(reversed(history)):
            bg = "#1a1a1a" if row_idx % 2 == 0 else "#1f1f1f"

            date = session.get("date", "—")
            dur = session.get("duration_minutes", 0)
            blinks = session.get("total_blinks", 0)
            avg = session.get("avg_blink_interval", 0)
            alerts = session.get("alerts_fired", 0)
            risk_score = session.get("risk_score", 0)
            risk_band = session.get("risk_band", "—")
            esc = session.get("escalation_counts", {})
            phase = session.get("phase", "—")

            # Escalation summary
            esc_text = ""
            if esc:
                parts = []
                for lvl in [1, 2, 3]:
                    count = esc.get(f"level_{lvl}", 0)
                    if count:
                        parts.append(f"L{lvl}:{count}")
                esc_text = " ".join(parts) if parts else "—"
            else:
                esc_text = "—"

            values = [
                date,
                f"{dur:.0f}m",
                str(blinks),
                f"{avg:.1f}s" if avg else "—",
                str(alerts),
                f"{risk_score}",
                esc_text,
                PHASE_LABELS.get(phase, phase[:3].upper() if isinstance(phase, str) else "—"),
            ]

            for col_idx, val in enumerate(values):
                text_color = TEXT_PRIMARY
                if col_idx == 3 and avg and session.get("threshold_used"):
                    text_color = GREEN if avg <= session["threshold_used"] else RED
                if col_idx == 5:  # Risk
                    text_color = RISK_COLORS.get(risk_band, TEXT_PRIMARY)

                label = ctk.CTkLabel(
                    self._table_scroll, text=val,
                    text_color=text_color,
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    fg_color=bg, corner_radius=0,
                )
                label.grid(row=row_idx, column=col_idx, sticky="ew", padx=1, pady=1)

        # Summary
        for w in self._summary_frame.winfo_children():
            w.destroy()

        if history:
            all_avgs = [s.get("avg_blink_interval", 0) for s in history if s.get("avg_blink_interval")]
            all_alerts = [s.get("alerts_fired", 0) for s in history]
            all_blinks = [s.get("total_blinks", 0) for s in history]
            all_durs = [s.get("duration_minutes", 0) for s in history]
            all_risk = [s.get("risk_score", 0) for s in history if "risk_score" in s]

            total_sessions = len(history)
            avg_avg = sum(all_avgs) / len(all_avgs) if all_avgs else 0
            total_alerts = sum(all_alerts)
            total_blinks_sum = sum(all_blinks)
            total_dur = sum(all_durs)
            avg_risk = sum(all_risk) / len(all_risk) if all_risk else 0

            summary_vals = [
                f"All ({total_sessions})",
                f"{total_dur:.0f}m",
                str(total_blinks_sum),
                f"{avg_avg:.1f}s" if avg_avg else "—",
                str(total_alerts),
                f"{avg_risk:.0f}" if all_risk else "—",
                "—",
                "—",
            ]

            for i, val in enumerate(summary_vals):
                ctk.CTkLabel(
                    self._summary_frame, text=val,
                    text_color=ACCENT,
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                ).grid(row=0, column=i, sticky="ew", padx=4, pady=6)

    # ---- Weekly Summaries -----------------------------------------------

    def _build_weekly_section(self) -> None:
        card = ctk.CTkFrame(self._scroll, fg_color=SURFACE, corner_radius=10)
        card.pack(fill="x", padx=16, pady=(0, 16))

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Weekly Summaries",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text="Generate Now", width=120, height=28,
            fg_color=ACCENT, hover_color="#1a8ad4",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._generate_weekly_now,
        ).grid(row=0, column=1, sticky="e")

        self._weekly_grid = ctk.CTkFrame(card, fg_color="transparent")
        self._weekly_grid.pack(fill="x", padx=16, pady=(0, 16))

        self._weekly_placeholder = ctk.CTkLabel(
            self._weekly_grid, text="No weekly summaries yet",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self._weekly_placeholder.pack(pady=12)

    def _populate_weekly_summaries(self, settings: dict) -> None:
        for w in self._weekly_grid.winfo_children():
            w.destroy()

        summaries = settings.get("weekly_summaries", [])
        if not summaries:
            self._weekly_placeholder = ctk.CTkLabel(
                self._weekly_grid, text="No weekly summaries yet",
                text_color=TEXT_MUTED,
                font=ctk.CTkFont(family="Segoe UI", size=12),
            )
            self._weekly_placeholder.pack(pady=12)
            return

        # Show thumbnails, 3 per row
        from PIL import Image
        for idx, summary in enumerate(reversed(summaries[-12:])):  # last 12
            row_idx = idx // 3
            col_idx = idx % 3

            path = summary.get("path", "")
            date = summary.get("date", "?")

            item = ctk.CTkFrame(self._weekly_grid, fg_color="#2a2a2a", corner_radius=6)
            item.grid(row=row_idx, column=col_idx, padx=4, pady=4, sticky="nsew")
            self._weekly_grid.grid_columnconfigure(col_idx, weight=1)

            ctk.CTkLabel(
                item, text=f"📊 {date}",
                text_color=TEXT_PRIMARY,
                font=ctk.CTkFont(family="Segoe UI", size=11),
            ).pack(padx=8, pady=(8, 4))

            if os.path.isfile(path):
                try:
                    img = Image.open(path)
                    img.thumbnail((200, 120))
                    photo = ctk.CTkImage(light_image=img, dark_image=img,
                                        size=(img.width, img.height))
                    lbl = ctk.CTkLabel(item, image=photo, text="")
                    lbl.pack(padx=8, pady=(0, 4))
                    lbl._photo = photo
                    lbl.bind("<Button-1>", lambda e, p=path: self._open_summary(p))
                except Exception:
                    pass

            ctk.CTkButton(
                item, text="Open", width=80, height=24,
                fg_color=BORDER, hover_color="#4a4a4a",
                text_color=TEXT_PRIMARY,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                command=lambda p=path: self._open_summary(p),
            ).pack(padx=8, pady=(0, 8))

    def _open_summary(self, path: str) -> None:
        if os.path.isfile(path):
            try:
                os.startfile(path)
            except Exception:
                logger.exception("Failed to open summary")

    def _generate_weekly_now(self) -> None:
        try:
            from blink_guard.weekly import generate_summary_card, record_weekly_summary
            settings = _load_settings()
            path = generate_summary_card(settings)
            if path:
                record_weekly_summary(settings, path)
                from blink_guard.defaults import save_settings_to_disk
                save_settings_to_disk(settings)
                self._refresh_data()
                self._open_summary(path)
        except Exception:
            logger.exception("Failed to generate weekly summary")

    # ---- Refresh --------------------------------------------------------

    def _refresh_data(self) -> None:
        settings = _load_settings()
        history = settings.get("session_history", [])

        # Risk gauge — most recent session
        if history:
            latest = history[-1]
            score = latest.get("risk_score", 0)
            band = latest.get("risk_band", "Low")
            self._draw_risk_gauge(score, band)
            self._gauge_label.configure(
                text=f"Score: {score}/100 — {band}",
                text_color=RISK_COLORS.get(band, TEXT_MUTED),
            )
        else:
            self._gauge_label.configure(text="No sessions yet", text_color=TEXT_MUTED)

        self._render_chart(history)
        self._populate_table(history)
        self._populate_weekly_summaries(settings)

    def on_tab_selected(self) -> None:
        self._refresh_data()

    def update_live_state(self, state: dict) -> None:
        pass
