"""
app.py — Main CustomTkinter window with sidebar tab navigation.

This is the root UI component for the BlinkGuard Dashboard. It manages
the sidebar, tab switching, connection status banner, and periodic IPC polling.
"""

import os
import sys
import subprocess
import threading
import time
import logging

import customtkinter as ctk

from blink_guard.ipc import IPCClient
from blink_guard.ui.tab_live import LiveTab
from blink_guard.ui.tab_progress import ProgressTab
from blink_guard.ui.tab_history import HistoryTab
from blink_guard.ui.tab_settings import SettingsTab
from blink_guard import __version__

logger = logging.getLogger("BlinkGuard.Dashboard")

# ---------------------------------------------------------------------------
# VS Code dark palette
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
ORANGE = "#cca700"
SIDEBAR_BG = "#181818"
SIDEBAR_ACTIVE = "#2a2d2e"

# Phase colors
PHASE_COLORS = {
    "observing": "#569cd6",
    "active": "#dcdcaa",
    "maintenance": "#4ec94e",
    "wean_off": "#c586c0",
}


class DashboardApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # -- Window Setup --
        self.title(f"BlinkGuard Dashboard v{__version__}")
        self.geometry("960x640")
        self.minsize(800, 560)
        self.configure(fg_color=BG_DARK)

        # Set icon (reuse the tray eye icon concept)
        self._set_icon()

        # -- IPC Client --
        self.ipc = IPCClient()
        self._bg_running = False
        self._live_state: dict = {}

        # -- Layout: sidebar + content --
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Banner (row 0, spans both columns)
        self._banner_frame = ctk.CTkFrame(self, fg_color="#3c1f1f", corner_radius=0, height=44)
        self._banner_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        self._banner_frame.grid_columnconfigure(1, weight=1)

        self._banner_dot = ctk.CTkLabel(
            self._banner_frame, text="●", text_color=RED,
            font=ctk.CTkFont(size=14), width=24
        )
        self._banner_dot.grid(row=0, column=0, padx=(16, 4), pady=8)

        self._banner_label = ctk.CTkLabel(
            self._banner_frame,
            text="BlinkGuard is not running — alerts are paused",
            text_color="#f0a0a0",
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self._banner_label.grid(row=0, column=1, sticky="w", padx=4, pady=8)

        self._launch_btn = ctk.CTkButton(
            self._banner_frame, text="Launch", width=80, height=28,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._launch_background,
        )
        self._launch_btn.grid(row=0, column=2, padx=(8, 16), pady=8)

        # Sidebar (row 1, column 0)
        self._sidebar = ctk.CTkFrame(self, fg_color=SIDEBAR_BG, corner_radius=0, width=200)
        self._sidebar.grid(row=1, column=0, sticky="nsw")
        self._sidebar.grid_propagate(False)

        # Content area (row 1, column 1)
        self._content = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        self._content.grid(row=1, column=1, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        # -- Tabs --
        self._tabs: dict[str, ctk.CTkFrame] = {}
        self._tab_buttons: dict[str, ctk.CTkButton] = {}
        self._active_tab: str = ""

        self._build_sidebar()
        self._build_tabs()

        # -- Start IPC polling --
        self._poll_id: str | None = None
        self._start_polling()

        # -- Select first tab --
        self._select_tab("live")

        # Cleanup on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- Icon -----------------------------------------------------------

    def _set_icon(self) -> None:
        """Set the window icon."""
        try:
            from PIL import Image, ImageDraw
            size = 64
            img = Image.new("RGBA", (size, size), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)
            cx, cy = size // 2, size // 2
            ir = size * 0.22
            draw.ellipse(
                (cx - ir, cy - ir, cx + ir, cy + ir),
                fill=(0, 122, 204, 255),
                outline=(90, 170, 230, 255),
                width=2,
            )
            pr = size * 0.09
            draw.ellipse(
                (cx - pr, cy - pr, cx + pr, cy + pr),
                fill=(20, 20, 40, 255),
            )
            # CTk uses iconbitmap; we'll skip if it fails
            import tempfile
            icon_path = os.path.join(tempfile.gettempdir(), "blinkguard_icon.ico")
            img.save(icon_path, format="ICO", sizes=[(64, 64)])
            self.iconbitmap(icon_path)
        except Exception:
            pass

    # ---- Sidebar --------------------------------------------------------

    def _build_sidebar(self) -> None:
        """Build the sidebar with tab buttons."""
        # Logo / title area
        title_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        title_frame.pack(fill="x", padx=12, pady=(20, 8))

        logo_label = ctk.CTkLabel(
            title_frame, text="👁", font=ctk.CTkFont(size=28),
            text_color=ACCENT,
        )
        logo_label.pack(side="left", padx=(4, 8))

        app_name = ctk.CTkLabel(
            title_frame, text="BlinkGuard",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        app_name.pack(side="left")

        # Separator
        sep = ctk.CTkFrame(self._sidebar, fg_color=BORDER, height=1)
        sep.pack(fill="x", padx=12, pady=(8, 16))

        # Tab items
        tabs = [
            ("live", "📹", "Live Monitor"),
            ("progress", "🎯", "Progress"),
            ("history", "📊", "History"),
            ("settings", "⚙️", "Settings"),
        ]

        for tab_id, icon, label in tabs:
            btn = ctk.CTkButton(
                self._sidebar,
                text=f"  {icon}  {label}",
                anchor="w",
                fg_color="transparent",
                hover_color=SIDEBAR_ACTIVE,
                text_color=TEXT_MUTED,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                height=40,
                corner_radius=6,
                command=lambda t=tab_id: self._select_tab(t),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._tab_buttons[tab_id] = btn

        # Spacer
        spacer = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Connection status at bottom
        self._conn_label = ctk.CTkLabel(
            self._sidebar,
            text="● Disconnected",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self._conn_label.pack(side="bottom", padx=12, pady=(0, 16))

        # Version
        ver_label = ctk.CTkLabel(
            self._sidebar,
            text=f"v{__version__}",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        ver_label.pack(side="bottom", padx=12, pady=(0, 4))

    # ---- Tabs -----------------------------------------------------------

    def _build_tabs(self) -> None:
        """Create all tab frames."""
        self._tabs["live"] = LiveTab(self._content, self)
        self._tabs["progress"] = ProgressTab(self._content, self)
        self._tabs["history"] = HistoryTab(self._content, self)
        self._tabs["settings"] = SettingsTab(self._content, self)

        for tab in self._tabs.values():
            tab.grid(row=0, column=0, sticky="nsew")

    def _select_tab(self, tab_id: str) -> None:
        """Switch the visible tab and update sidebar highlight."""
        if tab_id == self._active_tab:
            return

        # Update sidebar button styles
        for tid, btn in self._tab_buttons.items():
            if tid == tab_id:
                btn.configure(fg_color=SIDEBAR_ACTIVE, text_color=TEXT_PRIMARY)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_MUTED)

        # Show the selected tab
        self._tabs[tab_id].tkraise()
        self._active_tab = tab_id

        # Notify the tab it's now visible
        tab = self._tabs[tab_id]
        if hasattr(tab, "on_tab_selected"):
            tab.on_tab_selected()

    # ---- IPC Polling ----------------------------------------------------

    def _start_polling(self) -> None:
        """Begin polling the background process every 500ms."""
        self._poll()

    def _poll(self) -> None:
        """Single polling tick."""
        try:
            if not self.ipc.connected:
                success = self.ipc.connect()
                self._bg_running = success
                self._update_banner(success)
                self._update_conn_label(success)
            else:
                state = self.ipc.get_live_state()
                if state is None:
                    self.ipc.disconnect()
                    self._bg_running = False
                    self._update_banner(False)
                    self._update_conn_label(False)
                else:
                    self._bg_running = True
                    self._live_state = state
                    self._update_banner(True)
                    self._update_conn_label(True)

                    # Push state to the active tab
                    active = self._tabs.get(self._active_tab)
                    if active and hasattr(active, "update_live_state"):
                        active.update_live_state(state)
        except Exception:
            logger.exception("Poll error")

        # Schedule next poll
        self._poll_id = self.after(500, self._poll)

    def _update_banner(self, connected: bool) -> None:
        """Show/hide the 'not running' banner."""
        if connected:
            self._banner_frame.grid_remove()
        else:
            self._banner_frame.grid()

    def _update_conn_label(self, connected: bool) -> None:
        """Update sidebar connection indicator."""
        if connected:
            self._conn_label.configure(text="● Connected", text_color=GREEN)
        else:
            self._conn_label.configure(text="● Disconnected", text_color=RED)

    # ---- Launch background process --------------------------------------

    def _launch_background(self) -> None:
        """Launch the BlinkGuard background process."""
        try:
            if getattr(sys, "frozen", False):
                # Running as packaged exe — find BlinkGuard.exe next to us
                exe_dir = os.path.dirname(sys.executable)
                bg_exe = os.path.join(exe_dir, "BlinkGuard.exe")
                if os.path.isfile(bg_exe):
                    subprocess.Popen([bg_exe], creationflags=subprocess.DETACHED_PROCESS)
                    logger.info("Launched BlinkGuard.exe")
                else:
                    logger.error("BlinkGuard.exe not found at %s", bg_exe)
            else:
                # Dev mode — run main.py
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                main_py = os.path.join(base, "blink_guard", "main.py")
                subprocess.Popen(
                    [sys.executable, main_py],
                    creationflags=subprocess.DETACHED_PROCESS
                )
                logger.info("Launched main.py in background")
        except Exception:
            logger.exception("Failed to launch background process")

    # ---- Cleanup --------------------------------------------------------

    def _on_close(self) -> None:
        """Clean shutdown."""
        if self._poll_id:
            self.after_cancel(self._poll_id)
        self.ipc.disconnect()

        # Let tabs clean up
        for tab in self._tabs.values():
            if hasattr(tab, "on_close"):
                tab.on_close()

        self.destroy()
