"""Modal busy overlay with indeterminate progress (loader for long tasks)."""

from __future__ import annotations

import customtkinter as ctk

from ui.helpers import center_over


class BusyOverlay:
    """Blocking 'please wait' popup. Show it, run work in a thread, then close."""

    def __init__(self, parent: ctk.CTkBaseClass, message: str) -> None:
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Working…")
        self.dialog.resizable(False, False)
        center_over(self.dialog, parent, 300, 130)
        ctk.CTkLabel(self.dialog, text=message, font=("Segoe UI", 12)).pack(pady=(20, 10))
        self.bar = ctk.CTkProgressBar(self.dialog, mode="indeterminate", width=220)
        self.bar.pack(pady=(0, 20))
        try:
            self.bar.start()
        except Exception:  # noqa: BLE001 - static bar if animation unsupported
            pass
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", lambda: None)  # must wait
        self.dialog.focus_force()

    @classmethod
    def show(cls, parent: ctk.CTkBaseClass, message: str) -> "BusyOverlay":
        """Create and return a visible overlay."""
        return cls(parent, message)

    def close(self) -> None:
        """Release the grab and destroy the popup (call from the UI thread)."""
        try:
            self.bar.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.dialog.grab_release()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.dialog.destroy()
        except Exception:  # noqa: BLE001
            pass
