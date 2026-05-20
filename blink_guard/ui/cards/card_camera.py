"""
card_camera.py — Camera Settings card.

Camera selector with auto-detection, EAR threshold slider,
landmark overlay toggle, calibration info display, and recalibrate button.
"""

import logging
import threading

import customtkinter as ctk

from blink_guard.ui.cards._base import (
    BaseCard, _load_settings, _save_settings,
    ACCENT, ACCENT_HOVER, BORDER, TEXT_PRIMARY, TEXT_MUTED, GREEN, YELLOW,
)

logger = logging.getLogger("BlinkGuard.Dashboard")

MAX_CAMERA_SCAN = 5  # probe indices 0..4


def _enumerate_cameras() -> list[dict]:
    """Detect available cameras by probing OpenCV indices.

    Returns a list of dicts: [{"index": 0, "name": "Camera 0 — Integrated Webcam"}, ...]
    """
    import cv2

    # Try to get friendly names via WMI on Windows
    friendly_names: dict[int, str] = {}
    try:
        import subprocess, re
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_PnPEntity | "
             "Where-Object { $_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image' } | "
             "Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=5,
        )
        names = [n.strip() for n in result.stdout.strip().splitlines() if n.strip()]
        for i, name in enumerate(names):
            friendly_names[i] = name
    except Exception:
        pass

    cameras = []
    for idx in range(MAX_CAMERA_SCAN):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            # Read one frame to confirm it's real
            ret, _ = cap.read()
            cap.release()
            if ret:
                friendly = friendly_names.get(idx, "")
                if friendly:
                    label = f"Camera {idx} — {friendly}"
                else:
                    label = f"Camera {idx}"
                cameras.append({"index": idx, "name": label})
        else:
            cap.release()

    return cameras


class CameraCard(BaseCard):
    """Camera settings: index, EAR threshold, landmarks, calibration."""

    def __init__(self, parent, app):
        super().__init__(parent, app, title="📷 Camera")
        self._cameras: list[dict] = []
        self._scanning = False

    def build(self) -> None:
        # Camera selector row
        row = self._make_row("Camera")
        self._camera_dropdown = ctk.CTkOptionMenu(
            row, values=["Scanning..."],
            fg_color="#1a1a1a", button_color=BORDER,
            button_hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=220, height=28,
            command=self._on_camera_change,
        )
        self._camera_dropdown.set("Scanning...")
        self._camera_dropdown.grid(row=0, column=1, sticky="e")

        self._scan_btn = ctk.CTkButton(
            row, text="🔄", width=28, height=28,
            fg_color=BORDER, hover_color="#4a4a4a",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=13),
            command=self._scan_cameras,
        )
        self._scan_btn.grid(row=0, column=2, sticky="e", padx=(6, 0))

        self._cam_status = ctk.CTkLabel(
            self, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        self._cam_status.pack(fill="x", padx=20, pady=(0, 4))

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

    # ---- Camera scanning -------------------------------------------------

    def _scan_cameras(self) -> None:
        """Scan for available cameras in a background thread."""
        if self._scanning:
            return
        self._scanning = True
        self._camera_dropdown.configure(values=["Scanning..."])
        self._camera_dropdown.set("Scanning...")
        self._cam_status.configure(text="Scanning for cameras...", text_color=TEXT_MUTED)
        self._scan_btn.configure(state="disabled")

        def _worker():
            try:
                cameras = _enumerate_cameras()
                self._cameras = cameras
                # Update UI from main thread
                self.after(0, lambda: self._on_scan_complete(cameras))
            except Exception:
                logger.exception("Camera scan failed")
                self.after(0, lambda: self._on_scan_complete([]))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_scan_complete(self, cameras: list[dict]) -> None:
        """Update dropdown after camera scan completes."""
        self._scanning = False
        self._scan_btn.configure(state="normal")

        if not cameras:
            self._camera_dropdown.configure(values=["No cameras found"])
            self._camera_dropdown.set("No cameras found")
            self._cam_status.configure(
                text="No cameras detected. Check connections and retry.",
                text_color=YELLOW,
            )
            return

        names = [c["name"] for c in cameras]
        self._camera_dropdown.configure(values=names)

        # Select the currently configured camera
        settings = _load_settings()
        current_idx = settings.get("camera_index", 0)
        selected = names[0]
        for c in cameras:
            if c["index"] == current_idx:
                selected = c["name"]
                break
        self._camera_dropdown.set(selected)
        self._cam_status.configure(
            text=f"{len(cameras)} camera(s) detected",
            text_color=GREEN,
        )

    # ---- Callbacks -------------------------------------------------------

    def _on_camera_change(self, value) -> None:
        # Find the index from the name
        idx = 0
        for c in self._cameras:
            if c["name"] == value:
                idx = c["index"]
                break

        settings = _load_settings()
        settings["camera_index"] = idx
        _save_settings(settings)
        if self.app.ipc.connected:
            self.app.ipc.set_setting("camera_index", idx)
        self._cam_status.configure(
            text=f"Camera {idx} selected. Restart BlinkGuard to apply.",
            text_color=YELLOW,
        )

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
        # Trigger camera scan on first refresh (tab open)
        if not self._cameras and not self._scanning:
            self._scan_cameras()

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

