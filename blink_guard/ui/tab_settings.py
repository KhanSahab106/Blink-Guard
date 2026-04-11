"""
tab_settings.py — Settings tab (thin container).

Delegates all UI to card components in ``blink_guard.ui.cards``.
"""

import logging

import customtkinter as ctk

from blink_guard.defaults import load_settings_from_disk
from blink_guard.ui.cards._base import BG_DARK, BORDER, TEXT_PRIMARY
from blink_guard.ui.cards.card_alert import AlertCard
from blink_guard.ui.cards.card_startup import StartupCard
from blink_guard.ui.cards.card_journey import JourneyCard
from blink_guard.ui.cards.card_dnd import DNDCard
from blink_guard.ui.cards.card_camera import CameraCard
from blink_guard.ui.cards.card_about import AboutCard

logger = logging.getLogger("BlinkGuard.Dashboard")


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

        # Build card components
        self._cards = [
            AlertCard(self._scroll, app),
            StartupCard(self._scroll, app),
            JourneyCard(self._scroll, app),
            DNDCard(self._scroll, app),
            CameraCard(self._scroll, app),
            AboutCard(self._scroll, app),
        ]

    # ---- Tab lifecycle ---------------------------------------------------

    def _refresh_data(self) -> None:
        settings = load_settings_from_disk()
        for card in self._cards:
            card.refresh(settings)

    def on_tab_selected(self) -> None:
        self._refresh_data()

    def update_live_state(self, state: dict) -> None:
        pass
