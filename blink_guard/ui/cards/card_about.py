"""
card_about.py — About card.

Version info, privacy notice, and log file shortcut.
"""

import os
import sys
import subprocess
import logging

import customtkinter as ctk

from blink_guard.ui.cards._base import (
    BaseCard, BORDER, TEXT_PRIMARY, TEXT_MUTED,
)

logger = logging.getLogger("BlinkGuard.Dashboard")


class AboutCard(BaseCard):
    """About: version, privacy, log file opener."""

    def __init__(self, parent, app):
        super().__init__(parent, app, title="ℹ️ About")

    def build(self) -> None:
        from blink_guard import __version__

        info_items = [
            ("Version", __version__),
            ("Privacy", "All processing is local.\nNo data ever leaves your device."),
        ]

        for label, value in info_items:
            row = ctk.CTkFrame(self, fg_color="transparent")
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
            self, text="📂 Open Log File Location", width=200, height=28,
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

    def refresh(self, settings: dict) -> None:
        pass  # About card has no dynamic data
