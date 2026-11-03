"""Small UI helpers shared by dialogs."""

from __future__ import annotations

import customtkinter as ctk


def center_over(win: ctk.CTkToplevel, parent: ctk.CTkBaseClass, width: int, height: int) -> None:
    """Position ``win`` in the middle of the app window (multi-monitor safe)."""
    top = parent.winfo_toplevel()
    try:
        top.update_idletasks()
        win.update_idletasks()
        x = top.winfo_rootx() + (top.winfo_width() - width) // 2
        y = top.winfo_rooty() + (top.winfo_height() - height) // 2
    except Exception:  # noqa: BLE001 - fall back to default placement
        return
    win.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
