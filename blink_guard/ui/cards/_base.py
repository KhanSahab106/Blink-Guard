"""
_base.py — Shared palette constants and helper methods for settings cards.
"""

import logging

import customtkinter as ctk

from blink_guard.defaults import load_settings_from_disk, save_settings_to_disk

logger = logging.getLogger("BlinkGuard.Dashboard")

# ---------------------------------------------------------------------------
# VS Code dark palette (shared across all cards)
# ---------------------------------------------------------------------------

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


def _load_settings() -> dict:
    return load_settings_from_disk()


def _save_settings(settings: dict) -> None:
    save_settings_to_disk(settings)


class BaseCard(ctk.CTkFrame):
    """Base class for all settings cards.

    Provides shared helpers for building consistent card UIs.
    Subclasses must implement ``build()`` and ``refresh(settings)``.
    """

    def __init__(self, parent, app, *, title: str):
        super().__init__(parent, fg_color=SURFACE, corner_radius=10)
        self.pack(fill="x", padx=20, pady=(0, 12))
        self.app = app

        ctk.CTkLabel(
            self, text=title,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 8))

        self.build()

    # ---- Helpers ---------------------------------------------------------

    def _make_row(self, label: str) -> ctk.CTkFrame:
        """Create a label + control row inside this card."""
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=4)
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            row, text=label, text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        return row

    # ---- Abstract --------------------------------------------------------

    def build(self) -> None:
        """Build the card UI.  Called once in __init__."""
        raise NotImplementedError

    def refresh(self, settings: dict) -> None:
        """Refresh widget values from *settings* dict."""
        raise NotImplementedError
