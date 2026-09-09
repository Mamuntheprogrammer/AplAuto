"""Read-only scrollable table built on styled ttk.Treeview.

Lives inside a CustomTkinter card frame so the rest of the app
keeps the modern CTk look. Caps rendered rows to stay responsive.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

import customtkinter as ctk
import pandas as pd

ROW_LIMIT = 2000

# Excel banded-row palette.
EVEN_ROW_BG = "#ffffff"
ODD_ROW_BG = "#e9f2e9"
SELECT_BG = "#c6e0f2"
GRID_BORDER = "#d4d4d4"


def style_treeview(header_color: str) -> str:
    """Apply an Excel-like light style; returns the unique style name."""
    tag = "".join(c for c in header_color if c.isalnum())
    base = f"Excel{tag}.Treeview"
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        base,
        background="#ffffff",
        fieldbackground="#ffffff",
        foreground="#1a1a1a",
        rowheight=22,
        borderwidth=1,
        bordercolor=GRID_BORDER,
        lightcolor=GRID_BORDER,
        darkcolor=GRID_BORDER,
        font=("Calibri", 10),  # Excel's default font
    )
    style.configure(
        f"{base}.Heading",
        background=header_color,
        foreground="white",
        relief="flat",
        borderwidth=1,
        font=("Calibri", 10, "bold"),
    )
    style.map(base, background=[("selected", SELECT_BG)],
              foreground=[("selected", "#1a1a1a")])
    style.map(f"{base}.Heading",
              background=[("active", header_color), ("pressed", header_color)])
    return base


class DataTable(ctk.CTkFrame):
    """Labeled card with a Treeview grid + row/col info bar."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        title: str,
        header_color: str = "#1f6aa5",
        on_hover_info: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, corner_radius=12)
        self._df: pd.DataFrame = pd.DataFrame()
        self._on_hover_info = on_hover_info

        self.title_label = ctk.CTkLabel(self, text=title, font=("Segoe UI", 13, "bold"))
        self.title_label.pack(anchor="w", padx=14, pady=(10, 2))
        self.info_label = ctk.CTkLabel(
            self, text="No data loaded", font=("Segoe UI", 11), text_color="gray70"
        )
        self.info_label.pack(anchor="w", padx=14, pady=(0, 6))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        style_name = style_treeview(header_color)
        self.tree = ttk.Treeview(body, style=style_name, show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("even", background=EVEN_ROW_BG, foreground="#1a1a1a")
        self.tree.tag_configure("odd", background=ODD_ROW_BG, foreground="#1a1a1a")
        vsb = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Motion>", self._on_motion)

    # ------------------------------------------------------------- public API
    @property
    def dataframe(self) -> pd.DataFrame:
        """The full (untruncated) DataFrame backing this view."""
        return self._df

    def set_dataframe(self, df: pd.DataFrame) -> None:
        """Replace grid contents; renders at most ROW_LIMIT rows."""
        self._df = df.copy() if not df.empty else pd.DataFrame()
        self.tree.delete(*self.tree.get_children())
        if self._df.empty:
            self.tree["columns"] = []
            self.info_label.configure(text="Empty — no rows to display")
            return
        cols = ["#"] + [str(c) for c in self._df.columns]
        self.tree["columns"] = cols
        self.tree.heading("#", text="")
        self.tree.column("#", width=48, minwidth=40, stretch=False, anchor="center")
        for c in [str(c) for c in self._df.columns]:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=130, minwidth=60, stretch=True, anchor="w")
        view = self._df.head(ROW_LIMIT)
        # Insert in one go per column-chunk for speed.
        rows = [[str(v) for v in row] for row in view.itertuples(index=False, name=None)]
        for i, row in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", iid=str(i), values=[i + 1] + row, tags=(tag,))
        note = f"  (showing first {ROW_LIMIT:,})" if len(self._df) > ROW_LIMIT else ""
        self.info_label.configure(
            text=f"{len(self._df):,} rows × {len(cols)} cols{note}"
        )

    # ------------------------------------------------------------------ events
    def _on_motion(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        """Show column dtype in the info bar on hover (cheap tooltip)."""
        if self._df.empty or self._on_hover_info is None:
            return
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            col_id = self.tree.identify_column(event.x)  # e.g. "#3"
            try:
                idx = int(col_id.replace("#", "")) - 2  # -1 for "#" row-num col, -1 for 1-based
                if idx < 0:
                    return
                col = str(self._df.columns[idx])
                dtype = self._df[col].dtype
                self._on_hover_info(f"{col}: {dtype}  •  {self._df[col].notna().sum():,} non-null")
            except (IndexError, ValueError):
                pass
