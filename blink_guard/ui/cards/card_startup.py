"""
card_startup.py — Startup Settings card.

Toggle for launching BlinkGuard on Windows startup.
"""

import logging

import customtkinter as ctk

from blink_guard.ui.cards._base import (
    BaseCard, _load_settings, _save_settings,
    ACCENT, BORDER, TEXT_PRIMARY, TEXT_MUTED, RED, GREEN,
)

logger = logging.getLogger("BlinkGuard.Dashboard")


class StartupCard(BaseCard):
    """Startup settings: launch on Windows startup toggle."""

    def __init__(self, parent, app):
        super().__init__(parent, app, title="🚀 Startup")

    def build(self) -> None:
        row = self._make_row("Launch on Windows startup")
        self._startup_switch = ctk.CTkSwitch(
            row, text="", onvalue=True, offvalue=False,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=44, command=self._on_startup_toggle,
        )
        self._startup_switch.grid(row=0, column=1, sticky="e")

        self._startup_status = ctk.CTkLabel(
            self, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self._startup_status.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkFrame(self, fg_color="transparent", height=4).pack()

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

    def refresh(self, settings: dict) -> None:
        if settings.get("launch_on_startup", True):
            self._startup_switch.select()
        else:
            self._startup_switch.deselect()
