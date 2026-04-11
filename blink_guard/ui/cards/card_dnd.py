"""
card_dnd.py — Do Not Disturb card.

DND master toggle, rules list, add/delete rules with inline form.
"""

import logging

import customtkinter as ctk

from blink_guard.ui.cards._base import (
    BaseCard, _load_settings, _save_settings,
    ACCENT, ACCENT_HOVER, BORDER, TEXT_PRIMARY, TEXT_MUTED, RED,
    DAY_LABELS, DAY_KEYS,
)

logger = logging.getLogger("BlinkGuard.Dashboard")


class DNDCard(BaseCard):
    """Do Not Disturb schedule management."""

    def __init__(self, parent, app):
        self._dnd_form_visible = False
        super().__init__(parent, app, title="🔕 Do Not Disturb")

    def build(self) -> None:
        # Master toggle
        row = self._make_row("Enable DND schedule")
        self._dnd_switch = ctk.CTkSwitch(
            row, text="", onvalue=True, offvalue=False,
            fg_color=BORDER, progress_color=ACCENT,
            button_color=TEXT_PRIMARY, button_hover_color="#ffffff",
            width=44, command=self._on_dnd_toggle,
        )
        self._dnd_switch.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            self, text="DND suppresses alerts but continues blink tracking",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=10),
        ).pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x", padx=20, pady=4)

        # Rules list
        self._dnd_rules_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._dnd_rules_frame.pack(fill="x", padx=20, pady=(8, 4))

        self._dnd_rules_placeholder = ctk.CTkLabel(
            self._dnd_rules_frame, text="No DND rules configured",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self._dnd_rules_placeholder.pack(pady=4)

        # Add rule button
        ctk.CTkButton(
            self, text="+ Add Rule", width=120, height=28,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._show_add_dnd_rule,
        ).pack(padx=20, pady=(4, 4))

        # Inline form (hidden initially)
        self._dnd_form_frame = ctk.CTkFrame(self, fg_color="#2a2a2a", corner_radius=6)

        ctk.CTkFrame(self, fg_color="transparent", height=8).pack()

    # ---- Callbacks -------------------------------------------------------

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
        settings = _load_settings()
        if len(settings.get("dnd_schedule", [])) >= 10:
            return

        if self._dnd_form_visible:
            self._dnd_form_frame.pack_forget()
            self._dnd_form_visible = False
            return

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
        for label, key in zip(DAY_LABELS, DAY_KEYS):
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

        self._dnd_form_frame.pack_forget()
        self._dnd_form_visible = False
        self._refresh_dnd_rules()

    # ---- Refresh ---------------------------------------------------------

    def refresh(self, settings: dict) -> None:
        if settings.get("dnd_enabled", False):
            self._dnd_switch.select()
        else:
            self._dnd_switch.deselect()
        self._refresh_dnd_rules()
