"""
card_alert.py — Alert Settings card.

Sound toggle, volume slider, alert sound type (default/custom),
custom sound file browser, and preview button.
"""

import os
import logging

import customtkinter as ctk

from blink_guard.ui.cards._base import (
    BaseCard, _load_settings, _save_settings,
    ACCENT, ACCENT_HOVER, BORDER, TEXT_PRIMARY, TEXT_MUTED, RED, GREEN,
)

logger = logging.getLogger("BlinkGuard.Dashboard")


class AlertCard(BaseCard):
    """Alert settings: sound toggle, volume, sound type, preview."""

    def __init__(self, parent, app):
        super().__init__(parent, app, title="🔊 Alert Settings")

    def build(self) -> None:
        # Sound toggle
        row = self._make_row("Sound enabled")
        self._sound_switch = ctk.CTkSwitch(
            row, text="", onvalue=True, offvalue=False,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=44, command=self._on_sound_toggle,
        )
        self._sound_switch.grid(row=0, column=1, sticky="e")

        # Volume slider
        row = self._make_row("Alert volume")
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
        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x", padx=20, pady=8)

        row = self._make_row("Alert sound")
        self._sound_type_var = ctk.StringVar(value="default")
        ctk.CTkRadioButton(
            row, text="Default beep", variable=self._sound_type_var,
            value="default", text_color=TEXT_PRIMARY,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_sound_type_change,
        ).grid(row=0, column=1, sticky="e", padx=(0, 8))

        row2 = self._make_row("")
        ctk.CTkRadioButton(
            row2, text="Custom sound", variable=self._sound_type_var,
            value="custom", text_color=TEXT_PRIMARY,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_sound_type_change,
        ).grid(row=0, column=1, sticky="e")

        # Custom sound file controls (hidden initially)
        self._custom_sound_frame = ctk.CTkFrame(self, fg_color="transparent")
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
            self, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        self._custom_sound_status.pack(fill="x", padx=20, pady=(0, 4))

        # Preview button
        row = self._make_row("")
        ctk.CTkButton(
            row, text="▶ Preview Sound", width=130, height=28,
            fg_color=BORDER, hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._preview_sound,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkFrame(self, fg_color="transparent", height=8).pack()
        self._update_custom_sound_visibility()

    # ---- Callbacks -------------------------------------------------------

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
        import tkinter.filedialog as filedialog
        path = filedialog.askopenfilename(
            title="Select Alert Sound",
            filetypes=[("Audio files", "*.wav *.mp3"), ("All files", "*.*")],
        )
        if not path:
            return
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
            import array
            import math
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

    # ---- Refresh ---------------------------------------------------------

    def refresh(self, settings: dict) -> None:
        if settings.get("sound_enabled", True):
            self._sound_switch.select()
        else:
            self._sound_switch.deselect()

        vol = settings.get("volume", 75)
        self._volume_slider.set(vol)
        self._volume_label.configure(text=f"{vol}%")

        sound_type = settings.get("alert_sound", "default")
        self._sound_type_var.set(sound_type)
        self._update_custom_sound_visibility()

        custom_path = settings.get("custom_sound_path")
        if custom_path:
            self._custom_path_entry.delete(0, "end")
            self._custom_path_entry.insert(0, custom_path)
