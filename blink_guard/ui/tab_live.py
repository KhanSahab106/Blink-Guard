"""
tab_live.py — Live Monitor tab.

Two-column layout:
  Left (60%): Camera feed with MediaPipe overlay
  Right (40%): Live stats panel with EAR graph + escalation indicator
"""

import time
import base64
import logging
import io
from collections import deque

import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk

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


class LiveTab(ctk.CTkFrame):
    """Live Monitor tab showing camera feed and real-time stats."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG_DARK, corner_radius=0)
        self.app = app
        self._feed_paused = False
        self._last_blink_flash = 0
        self._ear_history_left: deque = deque(maxlen=100)
        self._ear_history_right: deque = deque(maxlen=100)
        self._current_photo = None

        self.grid_columnconfigure(0, weight=3)  # camera 60%
        self.grid_columnconfigure(1, weight=2)  # stats 40%
        self.grid_rowconfigure(0, weight=1)

        self._build_camera_panel()
        self._build_stats_panel()

    # ---- Camera Panel ---------------------------------------------------

    def _build_camera_panel(self) -> None:
        self._cam_frame = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=8)
        self._cam_frame.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        self._cam_frame.grid_columnconfigure(0, weight=1)
        self._cam_frame.grid_rowconfigure(1, weight=1)

        # Header row: LIVE dot + DND badge + pause button
        header = ctk.CTkFrame(self._cam_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        header.grid_columnconfigure(1, weight=1)

        self._live_dot = ctk.CTkLabel(
            header, text="● LIVE", text_color=RED,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self._live_dot.grid(row=0, column=0, sticky="w")

        self._dnd_badge = ctk.CTkLabel(
            header, text="", text_color=YELLOW,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        self._dnd_badge.grid(row=0, column=1, sticky="w", padx=(12, 0))

        self._pause_btn = ctk.CTkButton(
            header, text="⏸ Pause Feed", width=100, height=28,
            fg_color=BORDER, hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._toggle_feed_pause,
        )
        self._pause_btn.grid(row=0, column=2, sticky="e")

        # Camera canvas — use raw tkinter.Label for reliable video rendering
        self._cam_label = tk.Label(
            self._cam_frame, text="", bg="#111111",
            borderwidth=0, highlightthickness=0,
        )
        self._cam_label.grid(row=1, column=0, sticky="nsew", padx=12, pady=(4, 12))

        # Overlay text (placed on top of camera label)
        self._overlay_text = ctk.CTkLabel(
            self._cam_frame, text="Connecting to BlinkGuard...",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            fg_color="transparent",
        )
        self._overlay_text.grid(row=1, column=0, sticky="")

    def _toggle_feed_pause(self) -> None:
        self._feed_paused = not self._feed_paused
        if self._feed_paused:
            self._pause_btn.configure(text="▶ Resume Feed")
            self._live_dot.configure(text="⏸ PAUSED", text_color=TEXT_MUTED)
            self._overlay_text.configure(text="Feed paused")
            self._overlay_text.tkraise()
        else:
            self._pause_btn.configure(text="⏸ Pause Feed")
            self._live_dot.configure(text="● LIVE", text_color=RED)
            self._overlay_text.configure(text="")

    # ---- Stats Panel ----------------------------------------------------

    def _build_stats_panel(self) -> None:
        self._stats_frame = ctk.CTkScrollableFrame(
            self, fg_color=BG_DARK, corner_radius=0,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color="#555555",
        )
        self._stats_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)

        # --- Blink interval timer ---
        timer_card = self._make_card(self._stats_frame, "Time Since Last Blink")

        self._timer_label = ctk.CTkLabel(
            timer_card, text="0.0s",
            font=ctk.CTkFont(family="Segoe UI", size=48, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self._timer_label.pack(padx=16, pady=(4, 12))

        # --- Session stats ---
        stats_card = self._make_card(self._stats_frame, "Session Stats")

        self._stat_labels: dict[str, ctk.CTkLabel] = {}
        stats = [
            ("blinks", "Blinks this session", "0"),
            ("avg_interval", "Avg blink interval", "—"),
            ("alerts", "Alerts fired", "0"),
        ]
        for key, label, default in stats:
            row = ctk.CTkFrame(stats_card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=3)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row, text=label, text_color=TEXT_MUTED,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            val = ctk.CTkLabel(
                row, text=default, text_color=TEXT_PRIMARY,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                anchor="e",
            )
            val.grid(row=0, column=1, sticky="e")
            self._stat_labels[key] = val

        ctk.CTkFrame(stats_card, fg_color="transparent", height=8).pack()

        # --- Escalation indicator ---
        esc_card = self._make_card(self._stats_frame, "Alert Escalation")

        esc_inner = ctk.CTkFrame(esc_card, fg_color="transparent")
        esc_inner.pack(fill="x", padx=16, pady=(4, 12))

        self._esc_dots: list[ctk.CTkLabel] = []
        self._esc_labels_list: list[ctk.CTkLabel] = []
        dot_frame = ctk.CTkFrame(esc_inner, fg_color="transparent")
        dot_frame.pack(anchor="w")

        for i in range(3):
            dot = ctk.CTkLabel(
                dot_frame, text="●", width=28, height=28,
                font=ctk.CTkFont(family="Segoe UI", size=18),
                text_color=BORDER,
            )
            dot.pack(side="left", padx=4)
            self._esc_dots.append(dot)

        self._esc_status = ctk.CTkLabel(
            esc_inner, text="No alerts active",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self._esc_status.pack(anchor="w", pady=(4, 0))

        # --- Phase + threshold card ---
        phase_card = self._make_card(self._stats_frame, "Current Phase")

        self._phase_badge = ctk.CTkLabel(
            phase_card, text="OBSERVING",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#1e1e1e",
            fg_color="#569cd6",
            corner_radius=6,
            width=140, height=28,
        )
        self._phase_badge.pack(padx=16, pady=(4, 8))

        self._threshold_label = ctk.CTkLabel(
            phase_card, text="Threshold: —",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self._threshold_label.pack(padx=16, pady=(0, 12))

        # --- EAR Graph ---
        ear_card = self._make_card(self._stats_frame, "Eye Aspect Ratio (live)")

        self._ear_canvas = ctk.CTkCanvas(
            ear_card, bg="#1a1a1a", highlightthickness=0, height=100
        )
        self._ear_canvas.pack(fill="x", padx=12, pady=(4, 12))

        legend = ctk.CTkFrame(ear_card, fg_color="transparent")
        legend.pack(padx=16, pady=(0, 8))
        ctk.CTkLabel(
            legend, text="— Left eye", text_color=ACCENT,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        ).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            legend, text="— Right eye", text_color=GREEN,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        ).pack(side="left")

    def _make_card(self, parent, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=8)
        card.pack(fill="x", padx=0, pady=(0, 10))

        header = ctk.CTkLabel(
            card, text=title, text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            anchor="w",
        )
        header.pack(fill="x", padx=16, pady=(10, 2))

        return card

    # ---- State updates --------------------------------------------------

    def update_live_state(self, state: dict) -> None:
        if not state:
            return

        # Timer
        last_blink_ms = state.get("last_blink_ms_ago", 0)
        elapsed_s = last_blink_ms / 1000.0
        threshold = state.get("current_threshold")

        timer_color = TEXT_PRIMARY
        if threshold and threshold > 0:
            ratio = elapsed_s / threshold
            if ratio >= 1.0:
                timer_color = RED
            elif ratio >= 0.75:
                timer_color = ORANGE

        self._timer_label.configure(text=f"{elapsed_s:.1f}s", text_color=timer_color)

        # Session stats
        self._stat_labels["blinks"].configure(text=str(state.get("blink_count", 0)))
        avg = state.get("avg_interval")
        self._stat_labels["avg_interval"].configure(text=f"{avg:.1f}s" if avg else "—")
        self._stat_labels["alerts"].configure(text=str(state.get("alerts_fired", 0)))

        # Escalation indicator
        esc_level = state.get("escalation_level", 0)
        esc_colors = [GREEN, YELLOW, RED]
        for i in range(3):
            if i < esc_level:
                self._esc_dots[i].configure(text_color=esc_colors[i])
            else:
                self._esc_dots[i].configure(text_color=BORDER)

        if esc_level == 0:
            self._esc_status.configure(text="No alerts active", text_color=TEXT_MUTED)
        elif esc_level == 1:
            self._esc_status.configure(text="Level 1 — Soft reminder", text_color=GREEN)
        elif esc_level == 2:
            self._esc_status.configure(text="Level 2 — Please blink", text_color=YELLOW)
        else:
            self._esc_status.configure(text="Level 3 — Urgent!", text_color=RED)

        # DND badge
        dnd_active = state.get("dnd_active", False)
        dnd_end = state.get("dnd_end_time")
        if dnd_active:
            self._dnd_badge.configure(text=f"🔕 DND until {dnd_end or '?'}")
        else:
            self._dnd_badge.configure(text="")

        # Phase badge
        phase = state.get("phase", "observing")
        phase_color = PHASE_COLORS.get(phase, ACCENT)
        phase_label = PHASE_LABELS.get(phase, phase.upper())
        self._phase_badge.configure(text=phase_label, fg_color=phase_color)

        # Threshold
        if threshold:
            self._threshold_label.configure(text=f"Alerting at {threshold:.1f}s")
        else:
            self._threshold_label.configure(text="Threshold: —")

        # Face detection
        face_detected = state.get("face_detected", False)
        if not self._feed_paused:
            if not face_detected:
                self._overlay_text.configure(text="Face not detected")
                self._overlay_text.tkraise()
            else:
                self._overlay_text.configure(text="")

        # EAR history
        ear_hist = state.get("ear_history")
        if ear_hist and isinstance(ear_hist, list):
            self._ear_history_left.clear()
            self._ear_history_right.clear()
            for entry in ear_hist[-100:]:
                if isinstance(entry, dict):
                    self._ear_history_left.append(entry.get("left", 0))
                    self._ear_history_right.append(entry.get("right", 0))
        else:
            ear_left = state.get("ear_left", 0)
            ear_right = state.get("ear_right", 0)
            self._ear_history_left.append(ear_left)
            self._ear_history_right.append(ear_right)

        self._draw_ear_graph()

        # Camera feed
        if not self._feed_paused:
            self._update_camera_frame()

        # Blink flash
        if last_blink_ms < 400:
            self._cam_frame.configure(border_color=GREEN, border_width=2)
            self._last_blink_flash = time.time()
        elif time.time() - self._last_blink_flash > 0.3:
            self._cam_frame.configure(border_color=SURFACE, border_width=0)

    def _update_camera_frame(self) -> None:
        """Render the latest camera frame fetched by the IPC worker thread."""
        frame_bytes = self.app._latest_frame
        if not frame_bytes:
            return
        try:
            img = Image.open(io.BytesIO(frame_bytes))
            # Resize to fit the label
            label_w = self._cam_label.winfo_width()
            label_h = self._cam_label.winfo_height()
            if label_w > 10 and label_h > 10:
                # Maintain aspect ratio
                img_ratio = img.width / img.height
                label_ratio = label_w / label_h
                if img_ratio > label_ratio:
                    new_w = label_w
                    new_h = int(label_w / img_ratio)
                else:
                    new_h = label_h
                    new_w = int(label_h * img_ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._cam_label.configure(image=photo)
            self._cam_label._photo = photo  # prevent garbage collection
            self._overlay_text.configure(text="")
        except Exception:
            logger.exception("Failed to render camera frame")

    def _draw_ear_graph(self) -> None:
        canvas = self._ear_canvas
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 20 or h < 20:
            return

        canvas.create_line(0, h // 2, w, h // 2, fill="#333333", dash=(2, 4))

        ear_threshold_y = h - int(0.2 / 0.5 * h)
        canvas.create_line(0, ear_threshold_y, w, ear_threshold_y,
                          fill="#f4474740", dash=(4, 4))
        canvas.create_text(w - 4, ear_threshold_y - 8, text="0.2",
                          fill=TEXT_MUTED, anchor="e", font=("Segoe UI", 8))

        for history, color in [
            (self._ear_history_left, ACCENT),
            (self._ear_history_right, GREEN),
        ]:
            if len(history) < 2:
                continue
            points = []
            n = len(history)
            for i, val in enumerate(history):
                x = int(i / max(n - 1, 1) * w)
                y = h - int(min(val / 0.5, 1.0) * h)
                points.append(x)
                points.append(y)
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=2, smooth=True)

    # ---- Lifecycle ------------------------------------------------------

    def on_tab_selected(self) -> None:
        pass

    def on_close(self) -> None:
        pass
