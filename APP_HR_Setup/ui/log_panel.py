"""Scrollable timestamped status/log panel."""

from __future__ import annotations

from datetime import datetime

import customtkinter as ctk

LEVEL_ICON = {"success": "✅", "warning": "⚠️", "error": "❌", "info": "ℹ️"}
MAX_LINES = 200  # keep last ~50+ visible; cap buffer for perf


class LogPanel(ctk.CTkFrame):
    """Read-only auto-scrolling log with timestamped entries."""

    def __init__(self, parent: ctk.CTkBaseClass) -> None:
        super().__init__(parent, corner_radius=12)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(8, 2))
        ctk.CTkLabel(header, text="📋 Status Log", font=("Segoe UI", 12, "bold")).pack(
            side="left"
        )
        ctk.CTkButton(
            header, text="Clear", width=70, height=24, fg_color="#3a3a3a",
            hover_color="#4a4a4a", command=self.clear,
        ).pack(side="right")
        self.textbox = ctk.CTkTextbox(self, height=110, state="disabled", font=("Consolas", 11))
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._lines = 0

    def clear(self) -> None:
        """Remove all lines from the log view."""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
        self._lines = 0

    def log(self, level: str, message: str) -> None:
        """Append one timestamped line and auto-scroll to the newest."""
        icon = LEVEL_ICON.get(level, "•")
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {icon} {message}\n"
        self.textbox.configure(state="normal")
        self.textbox.insert("end", line)
        self._lines += 1
        if self._lines > MAX_LINES:  # trim oldest to bound memory
            self.textbox.delete("1.0", "2.0")
            self._lines -= 1
        self.textbox.see("end")
        self.textbox.configure(state="disabled")
