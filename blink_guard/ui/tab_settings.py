"""
tab_settings.py — Settings tab.

Grouped cards:
  1. Alert Settings (sound toggle, volume, custom sound, preview)
  2. Startup (launch on Windows startup)
  3. Habit Journey (sessions planned, target, phase, reset)
  4. Do Not Disturb Schedule
  5. Camera (index, EAR threshold, landmarks, recalibrate)
  6. About
"""

import json
import os
import sys
import subprocess
import logging
import tkinter.filedialog as filedialog

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
YELLOW = "#e5c07b"

PHASE_LABELS = {
    "observing": "OBSERVING",
    "active": "ACTIVE",
    "maintenance": "MAINTENANCE",
    "wean_off": "WEAN-OFF",
}

PHASE_COLORS = {
    "observing": "#569cd6",
    "active": "#dcdcaa",
    "maintenance": "#4ec94e",
    "wean_off": "#c586c0",
}

DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


from blink_guard.defaults import load_settings_from_disk, save_settings_to_disk


def _load_settings() -> dict:
    return load_settings_from_disk()


def _save_settings(settings: dict) -> None:
    save_settings_to_disk(settings)


class SettingsTab(ctk.CTkFrame):
    """Settings tab with grouped configuration cards."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG_DARK, corner_radius=0)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=BG_DARK, corner_radius=0,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color="#555555",
        )
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self._scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._scroll, text="Settings",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 12))

        self._build_alert_settings()
        self._build_startup_settings()
        self._build_journey_settings()
        self._build_dnd_settings()
        self._build_camera_settings()
        self._build_about()

    # ---- Card helpers ---------------------------------------------------

    def _make_card(self, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self._scroll, fg_color=SURFACE, corner_radius=10)
        card.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(
            card, text=title,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 8))
        return card

    def _make_row(self, parent, label: str) -> ctk.CTkFrame:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=4)
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            row, text=label, text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        return row

    # ---- Group 1: Alert Settings ----------------------------------------

    def _build_alert_settings(self) -> None:
        card = self._make_card("🔊 Alert Settings")

        # Sound toggle
        row = self._make_row(card, "Sound enabled")
        self._sound_switch = ctk.CTkSwitch(
            row, text="", onvalue=True, offvalue=False,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=44, command=self._on_sound_toggle,
        )
        self._sound_switch.grid(row=0, column=1, sticky="e")

        # Volume slider
        row = self._make_row(card, "Alert volume")
        self._volume_slider = ctk.CTkSlider(
            row, from_=0, to=100, number_of_steps=20,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=160, command=self._on_volume_change,
        )
        self._volume_slider.set(75)
        self._volume_slider.grid(row=0, column=1, sticky="e")

        self._volume_label = ctk.CTkLabel(
            row, text="75%", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=36,
        )
        self._volume_label.grid(row=0, column=2, sticky="e", padx=(8, 0))

        # Alert sound type
        ctk.CTkFrame(card, fg_color=BORDER, height=1).pack(fill="x", padx=20, pady=8)

        row = self._make_row(card, "Alert sound")
        self._sound_type_var = ctk.StringVar(value="default")
        ctk.CTkRadioButton(
            row, text="Default beep", variable=self._sound_type_var,
            value="default", text_color=TEXT_PRIMARY,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_sound_type_change,
        ).grid(row=0, column=1, sticky="e", padx=(0, 8))

        row2 = self._make_row(card, "")
        ctk.CTkRadioButton(
            row2, text="Custom sound", variable=self._sound_type_var,
            value="custom", text_color=TEXT_PRIMARY,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_sound_type_change,
        ).grid(row=0, column=1, sticky="e")

        # Custom sound file controls (hidden initially)
        self._custom_sound_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._custom_sound_frame.pack(fill="x", padx=20, pady=(4, 4))

        self._custom_path_entry = ctk.CTkEntry(
            self._custom_sound_frame, width=260, height=28,
            fg_color="#1a1a1a", border_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            placeholder_text="No file selected",
        )
        self._custom_path_entry.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            self._custom_sound_frame, text="Browse", width=80, height=28,
            fg_color=BORDER, hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._browse_custom_sound,
        ).pack(side="left", padx=(0, 6))

        self._custom_sound_status = ctk.CTkLabel(
            card, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        self._custom_sound_status.pack(fill="x", padx=20, pady=(0, 4))

        # Preview button
        row = self._make_row(card, "")
        ctk.CTkButton(
            row, text="▶ Preview Sound", width=130, height=28,
            fg_color=BORDER, hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._preview_sound,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()
        self._update_custom_sound_visibility()

    def _on_sound_toggle(self) -> None:
        enabled = self._sound_switch.get()
        settings = _load_settings()
        settings["sound_enabled"] = bool(enabled)
        _save_settings(settings)
        if self.app.ipc.connected:
            self.app.ipc.set_setting("sound_enabled", bool(enabled))

    def _on_volume_change(self, value) -> None:
        vol = int(value)
        self._volume_label.configure(text=f"{vol}%")
        settings = _load_settings()
        settings["volume"] = vol
        _save_settings(settings)
        if self.app.ipc.connected:
            self.app.ipc.set_setting("volume", vol)

    def _on_sound_type_change(self) -> None:
        sound_type = self._sound_type_var.get()
        settings = _load_settings()
        settings["alert_sound"] = sound_type
        _save_settings(settings)
        if self.app.ipc.connected:
            self.app.ipc.set_setting("alert_sound", sound_type)
        self._update_custom_sound_visibility()

    def _update_custom_sound_visibility(self) -> None:
        if self._sound_type_var.get() == "custom":
            self._custom_sound_frame.pack(fill="x", padx=20, pady=(4, 4))
        else:
            self._custom_sound_frame.pack_forget()

    def _browse_custom_sound(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Alert Sound",
            filetypes=[("Audio files", "*.wav *.mp3"), ("All files", "*.*")],
        )
        if not path:
            return

        # Validate file size
        if os.path.getsize(path) > 5 * 1024 * 1024:
            self._custom_sound_status.configure(
                text="✗ File too large. Please use a sound under 5MB.",
                text_color=RED,
            )
            return

        self._custom_path_entry.delete(0, "end")
        self._custom_path_entry.insert(0, path)

        settings = _load_settings()
        settings["custom_sound_path"] = path
        settings["alert_sound"] = "custom"
        _save_settings(settings)

        if self.app.ipc.connected:
            self.app.ipc.set_setting("custom_sound_path", path)
            self.app.ipc.set_setting("alert_sound", "custom")

        self._custom_sound_status.configure(
            text=f"✓ {os.path.basename(path)}", text_color=GREEN,
        )

    def _preview_sound(self) -> None:
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=512)
                pygame.mixer.init()

            sound_type = self._sound_type_var.get()
            volume = self._volume_slider.get() / 100.0

            if sound_type == "custom":
                path = self._custom_path_entry.get()
                if path and os.path.isfile(path):
                    sound = pygame.mixer.Sound(path)
                    sound.set_volume(volume)
                    sound.play()
                    return

            # Default beep
            import array, math
            sample_rate = 44100
            n_samples = int(sample_rate * 150 / 1000)
            max_amp = int(32767 * volume * 0.5)
            buf = array.array("h")
            for i in range(n_samples):
                t = i / sample_rate
                val = int(max_amp * math.sin(2.0 * math.pi * 440 * t))
                buf.append(val)
            fade = min(200, n_samples // 4)
            for i in range(fade):
                factor = i / fade
                buf[i] = int(buf[i] * factor)
                buf[-(i + 1)] = int(buf[-(i + 1)] * factor)
            sound = pygame.mixer.Sound(buffer=buf)
            sound.play()
        except Exception:
            logger.exception("Failed to preview sound")

    # ---- Group 2: Startup -----------------------------------------------

    def _build_startup_settings(self) -> None:
        card = self._make_card("🚀 Startup")

        row = self._make_row(card, "Launch on Windows startup")
        self._startup_switch = ctk.CTkSwitch(
            row, text="", onvalue=True, offvalue=False,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=44, command=self._on_startup_toggle,
        )
        self._startup_switch.grid(row=0, column=1, sticky="e")

        self._startup_status = ctk.CTkLabel(
            card, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self._startup_status.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkFrame(card, fg_color="transparent", height=4).pack()

    def _on_startup_toggle(self) -> None:
        enabled = self._startup_switch.get()
        settings = _load_settings()
        settings["launch_on_startup"] = bool(enabled)
        _save_settings(settings)
        if self.app.ipc.connected:
            self.app.ipc.set_setting("launch_on_startup", bool(enabled))
        try:
            from blink_guard.startup import set_launch_on_startup
            set_launch_on_startup(bool(enabled))
            self._startup_status.configure(
                text="✓ Registry updated" if enabled else "✓ Removed from startup",
                text_color=GREEN,
            )
        except Exception:
            self._startup_status.configure(
                text="✗ Failed to update registry", text_color=RED,
            )

    # ---- Group 3: Habit Journey -----------------------------------------

    def _build_journey_settings(self) -> None:
        card = self._make_card("🎯 Habit Journey")

        row = self._make_row(card, "Total sessions planned")
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
            card, text="Range: 7–30 sessions",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="e",
        ).pack(fill="x", padx=20, pady=(0, 4))

        row = self._make_row(card, "Target threshold")
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
            card, text="Range: 2.0–6.0 seconds",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="e",
        ).pack(fill="x", padx=20, pady=(0, 8))

        row = self._make_row(card, "Current phase")
        self._phase_label_setting = ctk.CTkLabel(
            row, text="OBSERVING",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#569cd6",
        )
        self._phase_label_setting.grid(row=0, column=1, sticky="e")

        ctk.CTkFrame(card, fg_color=BORDER, height=1).pack(fill="x", padx=20, pady=8)

        ctk.CTkButton(
            card, text="🗑 Reset Entire Progress", width=200, height=32,
            fg_color="#4a2020", hover_color="#6a2020",
            text_color="#f0a0a0",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._confirm_reset,
        ).pack(padx=20, pady=(0, 16))

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
        self._refresh_data()

    # ---- Group 4: Do Not Disturb ----------------------------------------

    def _build_dnd_settings(self) -> None:
        card = self._make_card("🔕 Do Not Disturb")

        # Master toggle
        row = self._make_row(card, "Enable DND schedule")
        self._dnd_switch = ctk.CTkSwitch(
            row, text="", onvalue=True, offvalue=False,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=44, command=self._on_dnd_toggle,
        )
        self._dnd_switch.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            card, text="DND suppresses alerts but continues blink tracking",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        ).pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkFrame(card, fg_color=BORDER, height=1).pack(fill="x", padx=20, pady=4)

        # Rules list
        self._dnd_rules_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._dnd_rules_frame.pack(fill="x", padx=20, pady=(8, 4))

        self._dnd_rules_placeholder = ctk.CTkLabel(
            self._dnd_rules_frame, text="No DND rules configured",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self._dnd_rules_placeholder.pack(pady=4)

        # Add rule button
        ctk.CTkButton(
            card, text="+ Add Rule", width=120, height=28,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._show_add_dnd_rule,
        ).pack(padx=20, pady=(4, 4))

        # Inline form (hidden initially)
        self._dnd_form_frame = ctk.CTkFrame(card, fg_color="#2a2a2a", corner_radius=6)
        # Will be packed when "Add Rule" is clicked

        self._dnd_form_visible = False

        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    def _on_dnd_toggle(self) -> None:
        enabled = self._dnd_switch.get()
        settings = _load_settings()
        settings["dnd_enabled"] = bool(enabled)
        _save_settings(settings)
        if self.app.ipc.connected:
            self.app.ipc.set_setting("dnd_enabled", bool(enabled))

    def _refresh_dnd_rules(self) -> None:
        for w in self._dnd_rules_frame.winfo_children():
            w.destroy()

        settings = _load_settings()
        rules = settings.get("dnd_schedule", [])

        if not rules:
            self._dnd_rules_placeholder = ctk.CTkLabel(
                self._dnd_rules_frame, text="No DND rules configured",
                text_color=TEXT_MUTED,
                font=ctk.CTkFont(family="Segoe UI", size=11),
            )
            self._dnd_rules_placeholder.pack(pady=4)
            return

        for idx, rule in enumerate(rules):
            row = ctk.CTkFrame(self._dnd_rules_frame, fg_color="#2a2a2a", corner_radius=4)
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(0, weight=1)

            days = ", ".join(d.capitalize() for d in rule.get("days", []))
            start = rule.get("start", "?")
            end = rule.get("end", "?")

            ctk.CTkLabel(
                row, text=f"{days}  {start}–{end}",
                text_color=TEXT_PRIMARY,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=8, pady=4)

            ctk.CTkButton(
                row, text="✕", width=28, height=24,
                fg_color="transparent", hover_color="#4a4a4a",
                text_color=RED,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                command=lambda i=idx: self._delete_dnd_rule(i),
            ).grid(row=0, column=1, sticky="e", padx=4, pady=4)

    def _delete_dnd_rule(self, index: int) -> None:
        settings = _load_settings()
        rules = settings.get("dnd_schedule", [])
        if 0 <= index < len(rules):
            rules.pop(index)
            settings["dnd_schedule"] = rules
            _save_settings(settings)
            if self.app.ipc.connected:
                self.app.ipc.set_setting("dnd_schedule", rules)
        self._refresh_dnd_rules()

    def _show_add_dnd_rule(self) -> None:
        # Check max rules
        settings = _load_settings()
        if len(settings.get("dnd_schedule", [])) >= 10:
            return

        if self._dnd_form_visible:
            self._dnd_form_frame.pack_forget()
            self._dnd_form_visible = False
            return

        # Clear and rebuild form
        for w in self._dnd_form_frame.winfo_children():
            w.destroy()

        self._dnd_form_frame.pack(fill="x", padx=20, pady=(4, 4))
        self._dnd_form_visible = True

        ctk.CTkLabel(
            self._dnd_form_frame, text="New DND Rule",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        ).pack(padx=12, pady=(8, 4))

        # Day checkboxes
        days_frame = ctk.CTkFrame(self._dnd_form_frame, fg_color="transparent")
        days_frame.pack(fill="x", padx=12, pady=4)

        self._dnd_day_vars: dict[str, ctk.BooleanVar] = {}
        for i, (label, key) in enumerate(zip(DAY_LABELS, DAY_KEYS)):
            var = ctk.BooleanVar(value=False)
            self._dnd_day_vars[key] = var
            ctk.CTkCheckBox(
                days_frame, text=label, variable=var,
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                text_color=TEXT_PRIMARY,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                width=50,
            ).pack(side="left", padx=2)

        # Time pickers
        time_frame = ctk.CTkFrame(self._dnd_form_frame, fg_color="transparent")
        time_frame.pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(
            time_frame, text="Start:", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(side="left")

        self._dnd_start_entry = ctk.CTkEntry(
            time_frame, width=60, height=26,
            fg_color="#1a1a1a", border_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            justify="center", placeholder_text="09:00",
        )
        self._dnd_start_entry.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(
            time_frame, text="End:", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(side="left")

        self._dnd_end_entry = ctk.CTkEntry(
            time_frame, width=60, height=26,
            fg_color="#1a1a1a", border_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            justify="center", placeholder_text="10:00",
        )
        self._dnd_end_entry.pack(side="left", padx=4)

        # Error label
        self._dnd_error = ctk.CTkLabel(
            self._dnd_form_frame, text="", text_color=RED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        self._dnd_error.pack(padx=12, pady=(0, 4))

        # Save button
        ctk.CTkButton(
            self._dnd_form_frame, text="Save Rule", width=100, height=28,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._save_dnd_rule,
        ).pack(padx=12, pady=(0, 8))

    def _save_dnd_rule(self) -> None:
        days = [k for k, v in self._dnd_day_vars.items() if v.get()]
        start = self._dnd_start_entry.get().strip()
        end = self._dnd_end_entry.get().strip()

        rule = {"days": days, "start": start, "end": end}

        from blink_guard.dnd import validate_rule
        error = validate_rule(rule)
        if error:
            self._dnd_error.configure(text=f"✗ {error}")
            return

        settings = _load_settings()
        rules = settings.setdefault("dnd_schedule", [])
        rules.append(rule)
        _save_settings(settings)

        if self.app.ipc.connected:
            self.app.ipc.set_setting("dnd_schedule", rules)

        # Hide form
        self._dnd_form_frame.pack_forget()
        self._dnd_form_visible = False
        self._refresh_dnd_rules()

    # ---- Group 5: Camera ------------------------------------------------

    def _build_camera_settings(self) -> None:
        card = self._make_card("📷 Camera")

        # Camera index
        row = self._make_row(card, "Camera index")
        self._camera_dropdown = ctk.CTkOptionMenu(
            row, values=["0", "1", "2", "3"],
            fg_color="#1a1a1a", button_color=BORDER,
            button_hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=80, height=28,
            command=self._on_camera_change,
        )
        self._camera_dropdown.set("0")
        self._camera_dropdown.grid(row=0, column=1, sticky="e")

        # EAR threshold
        row = self._make_row(card, "EAR blink threshold")
        self._ear_slider = ctk.CTkSlider(
            row, from_=0.10, to=0.30, number_of_steps=20,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=140, command=self._on_ear_change,
        )
        self._ear_slider.set(0.2)
        self._ear_slider.grid(row=0, column=1, sticky="e")

        self._ear_label = ctk.CTkLabel(
            row, text="0.20", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=36,
        )
        self._ear_label.grid(row=0, column=2, sticky="e", padx=(8, 0))

        ctk.CTkLabel(
            card, text="Lower = more sensitive to blinks",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="e",
        ).pack(fill="x", padx=20, pady=(0, 8))

        # Calibration info
        self._calibration_label = ctk.CTkLabel(
            card, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        self._calibration_label.pack(fill="x", padx=20, pady=(0, 4))

        # Landmark overlay toggle
        row = self._make_row(card, "Show eye landmark overlay")
        self._landmark_switch = ctk.CTkSwitch(
            row, text="", onvalue=True, offvalue=False,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=44, command=self._on_landmark_toggle,
        )
        self._landmark_switch.select()
        self._landmark_switch.grid(row=0, column=1, sticky="e")

        ctk.CTkFrame(card, fg_color=BORDER, height=1).pack(fill="x", padx=20, pady=8)

        # Recalibrate button
        ctk.CTkButton(
            card, text="🔄 Recalibrate Eye Detection", width=240, height=32,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._recalibrate,
        ).pack(padx=20, pady=(0, 16))

    def _on_camera_change(self, value) -> None:
        settings = _load_settings()
        settings["camera_index"] = int(value)
        _save_settings(settings)
        if self.app.ipc.connected:
            self.app.ipc.set_setting("camera_index", int(value))

    def _on_ear_change(self, value) -> None:
        val = round(value, 2)
        self._ear_label.configure(text=f"{val:.2f}")
        settings = _load_settings()
        settings["ear_blink_threshold"] = val
        _save_settings(settings)
        if self.app.ipc.connected:
            self.app.ipc.set_setting("ear_blink_threshold", val)

    def _on_landmark_toggle(self) -> None:
        enabled = self._landmark_switch.get()
        settings = _load_settings()
        settings["show_landmarks"] = bool(enabled)
        _save_settings(settings)
        if self.app.ipc.connected:
            self.app.ipc.set_setting("show_landmarks", bool(enabled))

    def _recalibrate(self) -> None:
        """Launch the calibration wizard from the dashboard."""
        try:
            from blink_guard.ui.calibration import CalibrationWizard

            def on_complete():
                # Reload settings to reflect new calibration
                self._refresh_data()

            wizard = CalibrationWizard(master=self.winfo_toplevel(),
                                       on_complete=on_complete)
            wizard.lift()
            wizard.focus_force()
        except Exception:
            logger.exception("Failed to launch calibration wizard")

    # ---- Group 6: About -------------------------------------------------

    def _build_about(self) -> None:
        card = self._make_card("ℹ️ About")

        info_items = [
            ("Version", "1.0.0"),
            ("Privacy", "All processing is local.\nNo data ever leaves your device."),
        ]

        for label, value in info_items:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                row, text=label, text_color=TEXT_MUTED,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                row, text=value, text_color=TEXT_PRIMARY,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                anchor="e", justify="right",
            ).grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            card, text="📂 Open Log File Location", width=200, height=28,
            fg_color=BORDER, hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._open_log_dir,
        ).pack(padx=20, pady=(8, 16))

    def _open_log_dir(self) -> None:
        if getattr(sys, "frozen", False):
            log_dir = os.path.dirname(sys.executable)
        else:
            log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.dirname(log_dir)
        log_file = os.path.join(log_dir, "blinkguard.log")
        try:
            if os.path.isfile(log_file):
                subprocess.Popen(["explorer", "/select,", log_file])
            else:
                subprocess.Popen(["explorer", log_dir])
        except Exception:
            logger.exception("Failed to open log directory")

    # ---- Refresh --------------------------------------------------------

    def _refresh_data(self) -> None:
        settings = _load_settings()

        # Sound
        if settings.get("sound_enabled", True):
            self._sound_switch.select()
        else:
            self._sound_switch.deselect()

        # Volume
        vol = settings.get("volume", 75)
        self._volume_slider.set(vol)
        self._volume_label.configure(text=f"{vol}%")

        # Sound type
        sound_type = settings.get("alert_sound", "default")
        self._sound_type_var.set(sound_type)
        self._update_custom_sound_visibility()

        custom_path = settings.get("custom_sound_path")
        if custom_path:
            self._custom_path_entry.delete(0, "end")
            self._custom_path_entry.insert(0, custom_path)

        # Startup
        if settings.get("launch_on_startup", True):
            self._startup_switch.select()
        else:
            self._startup_switch.deselect()

        # Journey
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

        # DND
        if settings.get("dnd_enabled", False):
            self._dnd_switch.select()
        else:
            self._dnd_switch.deselect()
        self._refresh_dnd_rules()

        # Camera
        self._camera_dropdown.set(str(settings.get("camera_index", 0)))

        ear_thr = settings.get("ear_blink_threshold", 0.2)
        self._ear_slider.set(ear_thr)
        self._ear_label.configure(text=f"{ear_thr:.2f}")

        if settings.get("show_landmarks", True):
            self._landmark_switch.select()
        else:
            self._landmark_switch.deselect()

        # Calibration info
        if settings.get("calibrated"):
            cal_date = settings.get("calibration_date", "?")
            ear_b = settings.get("ear_blink_threshold", 0.2)
            ear_o = settings.get("ear_open_threshold", 0.35)
            self._calibration_label.configure(
                text=f"✓ Calibrated on {cal_date} (blink: {ear_b:.3f}, open: {ear_o:.3f})",
                text_color=GREEN,
            )
        else:
            self._calibration_label.configure(
                text="Not calibrated — using default thresholds",
                text_color=YELLOW,
            )

    def on_tab_selected(self) -> None:
        self._refresh_data()

    def update_live_state(self, state: dict) -> None:
        pass
