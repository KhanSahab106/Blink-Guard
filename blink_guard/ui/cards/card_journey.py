"""
card_journey.py — Habit Journey card.

Sessions planned input, target threshold input, current phase display,
and full progress reset with confirmation dialog.
"""

import logging

import customtkinter as ctk

from blink_guard.ui.cards._base import (
    BaseCard, _load_settings, _save_settings,
    ACCENT, ACCENT_HOVER, BORDER, SURFACE,
    TEXT_PRIMARY, TEXT_MUTED, RED, PHASE_LABELS, PHASE_COLORS,
)

logger = logging.getLogger("BlinkGuard.Dashboard")


class JourneyCard(BaseCard):
    """Habit journey: sessions planned, target threshold, phase, reset."""

    def __init__(self, parent, app):
        super().__init__(parent, app, title="🎯 Habit Journey")

    def build(self) -> None:
        row = self._make_row("Total sessions planned")
        self._sessions_spin = ctk.CTkEntry(
            row, width=60, height=28,
            fg_color="#1a1a1a", border_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            justify="center",
        )
        self._sessions_spin.insert(0, "14")
        self._sessions_spin.grid(row=0, column=1, sticky="e")
        self._sessions_spin.bind("<FocusOut>", self._on_sessions_change)

        ctk.CTkLabel(
            self, text="Range: 7–30 sessions",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="e",
        ).pack(fill="x", padx=20, pady=(0, 4))

        row = self._make_row("Target threshold")
        self._target_entry = ctk.CTkEntry(
            row, width=60, height=28,
            fg_color="#1a1a1a", border_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            justify="center",
        )
        self._target_entry.insert(0, "4.0")
        self._target_entry.grid(row=0, column=1, sticky="e")
        self._target_entry.bind("<FocusOut>", self._on_target_change)

        ctk.CTkLabel(
            self, text="Range: 2.0–6.0 seconds",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="e",
        ).pack(fill="x", padx=20, pady=(0, 8))

        row = self._make_row("Current phase")
        self._phase_label_setting = ctk.CTkLabel(
            row, text="OBSERVING",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#569cd6",
        )
        self._phase_label_setting.grid(row=0, column=1, sticky="e")

        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x", padx=20, pady=8)

        ctk.CTkButton(
            self, text="🗑 Reset Entire Progress", width=200, height=32,
            fg_color="#4a2020", hover_color="#6a2020",
            text_color="#f0a0a0",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._confirm_reset,
        ).pack(padx=20, pady=(0, 16))

    # ---- Callbacks -------------------------------------------------------

    def _on_sessions_change(self, _event=None) -> None:
        try:
            val = int(self._sessions_spin.get())
            val = max(7, min(30, val))
            self._sessions_spin.delete(0, "end")
            self._sessions_spin.insert(0, str(val))
            settings = _load_settings()
            settings["total_sessions_planned"] = val
            _save_settings(settings)
            if self.app.ipc.connected:
                self.app.ipc.set_setting("total_sessions_planned", val)
        except ValueError:
            pass

    def _on_target_change(self, _event=None) -> None:
        try:
            val = float(self._target_entry.get())
            val = max(2.0, min(6.0, val))
            self._target_entry.delete(0, "end")
            self._target_entry.insert(0, f"{val:.1f}")
            settings = _load_settings()
            settings["target_threshold"] = val
            _save_settings(settings)
            if self.app.ipc.connected:
                self.app.ipc.set_setting("target_threshold", val)
        except ValueError:
            pass

    def _confirm_reset(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Reset")
        dialog.geometry("440x200")
        dialog.configure(fg_color=SURFACE)
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - 440) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - 200) // 2
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog, text="⚠️ Reset All Progress",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(padx=24, pady=(20, 8))

        ctk.CTkLabel(
            dialog,
            text="This will erase all session history and\nrestart from observation. This cannot be undone.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_MUTED,
        ).pack(padx=24, pady=(0, 16))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 16))

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=BORDER, hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY, command=dialog.destroy,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_frame, text="Reset Everything", width=140,
            fg_color=RED, hover_color="#d43a3a",
            text_color="#ffffff",
            command=lambda: self._do_reset(dialog),
        ).pack(side="right")

    def _do_reset(self, dialog) -> None:
        dialog.destroy()
        settings = _load_settings()
        settings["phase"] = "observing"
        settings["baseline_interval"] = None
        settings["sessions_completed"] = 0
        settings["current_threshold"] = None
        settings["maintenance_sessions"] = 0
        settings["session_history"] = []
        settings["hourly_data"] = {}
        _save_settings(settings)
        if self.app.ipc.connected:
            for key in ["phase", "baseline_interval", "sessions_completed",
                        "current_threshold", "maintenance_sessions"]:
                self.app.ipc.set_setting(key, settings[key])
        self.refresh(settings)

    # ---- Refresh ---------------------------------------------------------

    def refresh(self, settings: dict) -> None:
        total = settings.get("total_sessions_planned", 14)
        self._sessions_spin.delete(0, "end")
        self._sessions_spin.insert(0, str(total))

        target = settings.get("target_threshold", 4.0)
        self._target_entry.delete(0, "end")
        self._target_entry.insert(0, f"{target:.1f}")

        phase = settings.get("phase", "observing")
        self._phase_label_setting.configure(
            text=PHASE_LABELS.get(phase, phase.upper()),
            text_color=PHASE_COLORS.get(phase, ACCENT),
        )
