"""
card_camera.py — Camera Settings card.

Camera index selector, EAR threshold slider, landmark overlay toggle,
calibration info display, and recalibrate button.
"""

import logging

import customtkinter as ctk

from blink_guard.ui.cards._base import (
    BaseCard, _load_settings, _save_settings,
    ACCENT, ACCENT_HOVER, BORDER, TEXT_PRIMARY, TEXT_MUTED, GREEN, YELLOW,
)

logger = logging.getLogger("BlinkGuard.Dashboard")


class CameraCard(BaseCard):
    """Camera settings: index, EAR threshold, landmarks, calibration."""

    def __init__(self, parent, app):
        super().__init__(parent, app, title="📷 Camera")

    def build(self) -> None:
        # Camera index
        row = self._make_row("Camera index")
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
        row = self._make_row("EAR blink threshold")
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
            self, text="Lower = more sensitive to blinks",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            anchor="e",
        ).pack(fill="x", padx=20, pady=(0, 8))

        # Calibration info
        self._calibration_label = ctk.CTkLabel(
            self, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        self._calibration_label.pack(fill="x", padx=20, pady=(0, 4))

        # Landmark overlay toggle
        row = self._make_row("Show eye landmark overlay")
        self._landmark_switch = ctk.CTkSwitch(
            row, text="", onvalue=True, offvalue=False,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=44, command=self._on_landmark_toggle,
        )
        self._landmark_switch.select()
        self._landmark_switch.grid(row=0, column=1, sticky="e")

        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x", padx=20, pady=8)

        # Recalibrate button
        ctk.CTkButton(
            self, text="🔄 Recalibrate Eye Detection", width=240, height=32,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._recalibrate,
        ).pack(padx=20, pady=(0, 16))

    # ---- Callbacks -------------------------------------------------------

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
        try:
            from blink_guard.ui.calibration import CalibrationWizard

            def on_complete():
                self.refresh(_load_settings())

            wizard = CalibrationWizard(master=self.winfo_toplevel(),
                                       on_complete=on_complete)
            wizard.lift()
            wizard.focus_force()
        except Exception:
            logger.exception("Failed to launch calibration wizard")

    # ---- Refresh ---------------------------------------------------------

    def refresh(self, settings: dict) -> None:
        self._camera_dropdown.set(str(settings.get("camera_index", 0)))

        ear_thr = settings.get("ear_blink_threshold", 0.2)
        self._ear_slider.set(ear_thr)
        self._ear_label.configure(text=f"{ear_thr:.2f}")

        if settings.get("show_landmarks", True):
            self._landmark_switch.select()
        else:
            self._landmark_switch.deselect()

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
