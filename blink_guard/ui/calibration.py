"""
calibration.py — First-launch Calibration Wizard.

A small CustomTkinter window (separate from the dashboard) that:
  1. Welcome screen
  2. Environment check (lighting analysis)
  3. Blink collection (15 blinks)
  4. Compute personal EAR thresholds
  5. Completion screen

Stores calibration data in settings.json and sets "calibrated": true.
"""

import time
import threading
import logging
import json
import os
import sys
import datetime

import cv2
import mediapipe as mp
import customtkinter as ctk
from PIL import Image, ImageTk
import numpy as np

logger = logging.getLogger("BlinkGuard")

# Palette
BG_DARK = "#1e1e1e"
SURFACE = "#252526"
ACCENT = "#007acc"
TEXT = "#d4d4d4"
MUTED = "#858585"
BORDER = "#3c3c3c"
GREEN = "#4ec94e"
RED = "#f44747"

# EAR landmarks
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

REQUIRED_BLINKS = 15
MIN_BRIGHTNESS = 60     # avg pixel value threshold for "poor lighting"
MAX_VARIANCE = 3500     # variance threshold for "uneven lighting"


from blink_guard.defaults import load_settings_from_disk, save_settings_to_disk


def _load_settings() -> dict:
    return load_settings_from_disk()


def _save_settings(settings: dict):
    save_settings_to_disk(settings)


def _distance(p1, p2) -> float:
    return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5


def _ear(landmarks, indices) -> float:
    p1, p2, p3, p4, p5, p6 = [landmarks[i] for i in indices]
    v1 = _distance(p2, p6)
    v2 = _distance(p3, p5)
    h = _distance(p1, p4)
    if h < 1e-6:
        return 0.0
    return (v1 + v2) / (2.0 * h)


def _compute_ear(landmarks) -> float:
    return (_ear(landmarks, LEFT_EYE) + _ear(landmarks, RIGHT_EYE)) / 2.0


def needs_calibration() -> bool:
    """Check if calibration is needed (first launch)."""
    settings = _load_settings()
    return not settings.get("calibrated", False)


class CalibrationWizard(ctk.CTkToplevel):
    """Self-contained calibration wizard window."""

    def __init__(self, master=None, on_complete=None):
        super().__init__(master)
        self.title("BlinkGuard — Calibration")
        self.geometry("560x520")
        self.configure(fg_color=BG_DARK)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._on_complete = on_complete
        self._step = 0
        self._running = True

        # Camera / detection state
        self._cap = None
        self._face_mesh = None
        self._camera_thread = None
        self._current_photo = None
        self._frame_lock = threading.Lock()
        self._latest_frame = None  # latest BGR frame from camera thread

        # Calibration data
        self._blink_count = 0
        self._blink_ear_lows: list[float] = []    # EAR at lowest point of each blink
        self._open_ear_values: list[float] = []    # EAR during open-eye periods
        self._current_ear_min = 1.0                # tracking min during a blink
        self._frames_below = 0
        self._in_blink = False
        self._grace_until = 0.0

        # Computed thresholds
        self._ear_blink_threshold = 0.20
        self._ear_open_threshold = 0.35

        # Content frame
        self._content = ctk.CTkFrame(self, fg_color=BG_DARK)
        self._content.pack(fill="both", expand=True, padx=20, pady=20)

        self._show_welcome()

    def _clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()

    # ---- Step 1: Welcome ------------------------------------------------

    def _show_welcome(self):
        self._clear_content()
        self._step = 1

        ctk.CTkLabel(
            self._content, text="👁 Welcome to BlinkGuard",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=TEXT,
        ).pack(pady=(40, 16))

        ctk.CTkLabel(
            self._content,
            text="Before we start, we need to learn how your\n"
                 "eyes look when you blink.\n\n"
                 "This takes about 60 seconds.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=MUTED,
            justify="center",
        ).pack(pady=(0, 30))

        ctk.CTkButton(
            self._content, text="Begin Calibration",
            width=200, height=42,
            fg_color=ACCENT, hover_color="#1a8ad4",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self._show_environment_check,
        ).pack(pady=20)

    # ---- Step 2: Environment Check --------------------------------------

    def _show_environment_check(self):
        self._clear_content()
        self._step = 2

        ctk.CTkLabel(
            self._content, text="🔦 Environment Check",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=TEXT,
        ).pack(pady=(10, 8))

        # Camera preview — use raw tkinter.Label for reliable video
        import tkinter as tk
        self._env_preview = tk.Label(
            self._content, text="Starting camera...",
            bg="#111111", fg=MUTED,
            borderwidth=0, highlightthickness=0,
            width=56, height=18,  # approximate char-based sizing
        )
        self._env_preview.pack(pady=(8, 8), fill="both", expand=True)

        self._env_status = ctk.CTkLabel(
            self._content, text="Analyzing lighting...",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=MUTED,
        )
        self._env_status.pack(pady=(4, 8))

        btn_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        btn_frame.pack(pady=(8, 0))

        self._env_retry_btn = ctk.CTkButton(
            btn_frame, text="Re-check", width=120, height=34,
            fg_color=BORDER, hover_color="#4a4a4a",
            text_color=TEXT,
            command=self._retry_env_check,
        )
        self._env_retry_btn.pack(side="left", padx=(0, 10))

        self._env_proceed_btn = ctk.CTkButton(
            btn_frame, text="Continue →", width=120, height=34,
            fg_color=ACCENT, hover_color="#1a8ad4",
            text_color="#ffffff",
            command=self._show_blink_collection,
        )
        self._env_proceed_btn.pack(side="left")

        # Start camera
        self._start_camera()
        # Wait 2 seconds for camera to warm up before lighting analysis
        self.after(2000, self._analyze_lighting)

    def _start_camera(self):
        if self._cap is not None:
            return

        settings = _load_settings()
        cam_idx = settings.get("camera_index", 0)

        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1, refine_landmarks=True,
            min_detection_confidence=0.5, min_tracking_confidence=0.5,
        )
        self._cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self._camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self._camera_thread.start()

    def _camera_loop(self):
        """Background thread that continuously reads frames."""
        while self._running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            # Store latest frame for lighting analysis (thread-safe)
            with self._frame_lock:
                self._latest_frame = frame.copy()

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._face_mesh.process(rgb)

            # Draw on frame for preview
            if results.multi_face_landmarks:
                lms = results.multi_face_landmarks[0].landmark
                h, w = frame.shape[:2]
                for idx_list in [LEFT_EYE, RIGHT_EYE]:
                    for idx in idx_list:
                        cx, cy = int(lms[idx].x * w), int(lms[idx].y * h)
                        cv2.circle(frame, (cx, cy), 2, (0, 122, 204), -1)

                ear = _compute_ear(lms)

                # Blink collection (step 3 only)
                if self._step == 3:
                    self._process_blink(ear, lms)

            # Update preview
            try:
                self._update_preview(frame)
            except Exception:
                pass  # Widget may have been destroyed

            time.sleep(0.033)  # ~30 fps

    def _update_preview(self, frame):
        """Update the camera preview label from the camera thread."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        # Get target widget
        target = None
        if self._step == 2 and hasattr(self, "_env_preview"):
            target = self._env_preview
        elif self._step == 3 and hasattr(self, "_blink_preview"):
            target = self._blink_preview

        if target is None:
            return

        try:
            tw = target.winfo_width()
            th = target.winfo_height()
            if tw > 10 and th > 10:
                # Maintain aspect ratio
                img_ratio = pil_img.width / pil_img.height
                label_ratio = tw / th
                if img_ratio > label_ratio:
                    new_w = tw
                    new_h = int(tw / img_ratio)
                else:
                    new_h = th
                    new_w = int(th * img_ratio)
                pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
        except Exception:
            pass

        photo = ImageTk.PhotoImage(pil_img)

        def _set():
            try:
                target.configure(image=photo)
                target._photo = photo  # prevent garbage collection
            except Exception:
                pass

        self.after(0, _set)

    def _analyze_lighting(self):
        """Analyze lighting using the latest frame from camera thread."""
        # Use the buffered frame instead of calling cap.read() (avoids race)
        with self._frame_lock:
            frame = self._latest_frame.copy() if self._latest_frame is not None else None

        if frame is None:
            self._env_status.configure(text="❌ Waiting for camera...", text_color=RED)
            # Retry in 1 second
            self.after(1000, self._analyze_lighting)
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg_brightness = float(np.mean(gray))
        variance = float(np.var(gray))

        if avg_brightness < MIN_BRIGHTNESS:
            self._env_status.configure(
                text=f"⚠ Low lighting detected (brightness: {avg_brightness:.0f}).\n"
                     f"Face a light source for best results.",
                text_color="#e5c07b",
            )
        elif variance > MAX_VARIANCE:
            self._env_status.configure(
                text=f"⚠ Uneven lighting detected (variance: {variance:.0f}).\n"
                     f"Try to reduce shadows on your face.",
                text_color="#e5c07b",
            )
        else:
            self._env_status.configure(
                text=f"✓ Lighting looks good! (brightness: {avg_brightness:.0f})",
                text_color=GREEN,
            )

    def _retry_env_check(self):
        self._analyze_lighting()

    # ---- Step 3: Blink Collection ---------------------------------------

    def _show_blink_collection(self):
        self._clear_content()
        self._step = 3
        self._blink_count = 0
        self._blink_ear_lows = []
        self._open_ear_values = []
        self._frames_below = 0
        self._in_blink = False
        self._current_ear_min = 1.0

        ctk.CTkLabel(
            self._content, text="👁 Blink Collection",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=TEXT,
        ).pack(pady=(10, 4))

        ctk.CTkLabel(
            self._content,
            text="Blink naturally at your own pace.\nWe need 15 blinks to calibrate.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=MUTED, justify="center",
        ).pack(pady=(0, 8))

        # Camera preview — use raw tkinter.Label for reliable video
        import tkinter as tk
        self._blink_preview = tk.Label(
            self._content, text="",
            bg="#111111",
            borderwidth=0, highlightthickness=0,
        )
        self._blink_preview.pack(pady=(4, 8), fill="both", expand=True)

        # Blink counter
        self._blink_counter_label = ctk.CTkLabel(
            self._content, text="Blinks detected: 0 / 15",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=ACCENT,
        )
        self._blink_counter_label.pack(pady=(4, 4))

        # Checkmark row
        self._check_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        self._check_frame.pack(pady=(4, 8))

        self._check_labels: list[ctk.CTkLabel] = []
        for i in range(REQUIRED_BLINKS):
            lbl = ctk.CTkLabel(
                self._check_frame, text="○", width=24,
                font=ctk.CTkFont(family="Segoe UI", size=14),
                text_color=BORDER,
            )
            lbl.pack(side="left", padx=2)
            self._check_labels.append(lbl)

        self._blink_status = ctk.CTkLabel(
            self._content, text="Watching for blinks...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=MUTED,
        )
        self._blink_status.pack(pady=(4, 0))

    def _process_blink(self, ear: float, landmarks):
        """Process EAR value during blink collection (called from camera thread)."""
        BLINK_THRESHOLD = 0.22  # slightly generous for collection
        CONSEC_FRAMES = 2

        if self._blink_count >= REQUIRED_BLINKS:
            return

        if ear < BLINK_THRESHOLD:
            self._frames_below += 1
            self._current_ear_min = min(self._current_ear_min, ear)
            self._in_blink = True
        else:
            if self._in_blink and self._frames_below >= CONSEC_FRAMES:
                now = time.time()
                if now > self._grace_until:
                    # Valid blink detected
                    self._blink_ear_lows.append(self._current_ear_min)
                    self._blink_count += 1
                    self._grace_until = now + 0.3

                    # Update UI from main thread
                    def _update():
                        try:
                            self._blink_counter_label.configure(
                                text=f"Blinks detected: {self._blink_count} / {REQUIRED_BLINKS}"
                            )
                            if self._blink_count <= len(self._check_labels):
                                self._check_labels[self._blink_count - 1].configure(
                                    text="✓", text_color=GREEN,
                                )
                            if self._blink_count >= REQUIRED_BLINKS:
                                self._blink_status.configure(
                                    text="✓ Collection complete!",
                                    text_color=GREEN,
                                )
                                self.after(1000, self._show_results)
                        except Exception:
                            pass
                    self.after(0, _update)

            if not self._in_blink or self._frames_below < CONSEC_FRAMES:
                # Open-eye reading
                self._open_ear_values.append(ear)

            self._frames_below = 0
            self._in_blink = False
            self._current_ear_min = 1.0

    # ---- Step 4+5: Results & Completion ---------------------------------

    def _show_results(self):
        self._clear_content()
        self._step = 4

        # Compute thresholds
        if self._blink_ear_lows:
            avg_low = sum(self._blink_ear_lows) / len(self._blink_ear_lows)
            self._ear_blink_threshold = round(avg_low * 0.9, 3)  # 10% buffer
        else:
            self._ear_blink_threshold = 0.20

        if self._open_ear_values:
            self._ear_open_threshold = round(
                sum(self._open_ear_values) / len(self._open_ear_values), 3
            )
        else:
            self._ear_open_threshold = 0.35

        # Clamp to sane range
        self._ear_blink_threshold = max(0.10, min(0.30, self._ear_blink_threshold))
        self._ear_open_threshold = max(0.25, min(0.50, self._ear_open_threshold))

        ctk.CTkLabel(
            self._content, text="✅ Calibration Complete!",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=GREEN,
        ).pack(pady=(30, 16))

        # Show thresholds
        results_frame = ctk.CTkFrame(self._content, fg_color=SURFACE, corner_radius=10)
        results_frame.pack(fill="x", padx=30, pady=(0, 16))

        for label, value, note in [
            ("Blink threshold", f"{self._ear_blink_threshold:.3f}",
             "EAR below this = blink detected"),
            ("Open-eye baseline", f"{self._ear_open_threshold:.3f}",
             "Your normal open-eye EAR value"),
        ]:
            row = ctk.CTkFrame(results_frame, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=8)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row, text=label, text_color=MUTED,
                font=ctk.CTkFont(family="Segoe UI", size=12),
            ).grid(row=0, column=0, sticky="w")

            ctk.CTkLabel(
                row, text=value, text_color=TEXT,
                font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            ).grid(row=0, column=1, sticky="e")

            ctk.CTkLabel(
                row, text=note, text_color=MUTED,
                font=ctk.CTkFont(family="Segoe UI", size=10),
            ).grid(row=1, column=0, columnspan=2, sticky="w")

        ctk.CTkLabel(
            self._content,
            text="BlinkGuard is now tuned for your eyes.\n"
                 "You can recalibrate anytime from Settings → Camera.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=MUTED, justify="center",
        ).pack(pady=(8, 20))

        ctk.CTkButton(
            self._content, text="Finish",
            width=180, height=42,
            fg_color=ACCENT, hover_color="#1a8ad4",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self._finish,
        ).pack(pady=8)

    def _finish(self):
        """Save calibration data and close."""
        settings = _load_settings()
        settings["calibrated"] = True
        settings["calibration_date"] = datetime.date.today().isoformat()
        settings["ear_blink_threshold"] = self._ear_blink_threshold
        settings["ear_open_threshold"] = self._ear_open_threshold
        _save_settings(settings)

        logger.info("Calibration complete: blink=%.3f, open=%.3f",
                     self._ear_blink_threshold, self._ear_open_threshold)

        self._stop_camera()
        if self._on_complete:
            self._on_complete()
        self.destroy()

    def _on_close(self):
        """Window close button pressed — save partial or skip."""
        self._stop_camera()
        # If we at least have some data, save it
        if self._blink_ear_lows:
            self._show_results()
        else:
            self.destroy()

    def _stop_camera(self):
        self._running = False
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        if self._face_mesh:
            try:
                self._face_mesh.close()
            except Exception:
                pass
            self._face_mesh = None


def run_calibration_wizard(master=None, on_complete=None) -> CalibrationWizard:
    """Launch the calibration wizard. Returns the window instance."""
    ctk.set_appearance_mode("dark")
    wizard = CalibrationWizard(master=master, on_complete=on_complete)
    wizard.lift()
    wizard.focus_force()
    return wizard
