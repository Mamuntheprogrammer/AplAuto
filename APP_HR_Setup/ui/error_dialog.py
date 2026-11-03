"""Modal error popup with a Copy button for validation messages."""

from __future__ import annotations

import customtkinter as ctk

from ui.helpers import center_over


def show_error_dialog(parent: ctk.CTkBaseClass, title: str, message: str) -> None:
    """Show ``message`` in a modal dialog with Copy + Close buttons."""
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    center_over(dialog, parent, 540, 330)
    dialog.resizable(True, True)

    ctk.CTkLabel(
        dialog, text=f"❌ {title}", font=("Segoe UI", 13, "bold")
    ).pack(anchor="w", padx=14, pady=(12, 2))
    ctk.CTkLabel(
        dialog, text="The previous result was left unchanged.",
        font=("Segoe UI", 11), text_color="gray70",
    ).pack(anchor="w", padx=14, pady=(0, 6))

    box = ctk.CTkTextbox(dialog, font=("Consolas", 11))
    box.pack(fill="both", expand=True, padx=14, pady=(0, 8))
    box.insert("1.0", message)
    box.configure(state="disabled")

    btns = ctk.CTkFrame(dialog, fg_color="transparent")
    btns.pack(pady=(0, 12))
    copy_btn = ctk.CTkButton(btns, text="⧉ Copy", width=120, fg_color="#1f6aa5",
                             hover_color="#185a8d")

    reset_id: list = [None]

    def _copy() -> None:
        dialog.clipboard_clear()
        dialog.clipboard_append(message)
        copy_btn.configure(text="✓ Copied")

        def _reset() -> None:
            reset_id[0] = None
            try:
                if copy_btn.winfo_exists():
                    copy_btn.configure(text="⧉ Copy")
            except Exception:  # noqa: BLE001 - dialog already closed
                pass

        try:
            reset_id[0] = dialog.after(1500, _reset)
        except Exception:  # noqa: BLE001 - dialog already closing
            pass

    def _close() -> None:
        try:
            if reset_id[0] is not None:
                dialog.after_cancel(reset_id[0])
        except Exception:  # noqa: BLE001 - already fired / dialog gone
            pass
        try:
            dialog.destroy()
        except Exception:  # noqa: BLE001
            pass

    copy_btn.configure(command=_copy)
    copy_btn.pack(side="left", padx=8)
    ctk.CTkButton(btns, text="Close", width=120, fg_color="#3a3a3a",
                  hover_color="#4a4a4a", command=_close).pack(side="left", padx=8)
    dialog.protocol("WM_DELETE_WINDOW", _close)

    dialog.transient(parent)
    dialog.grab_set()
