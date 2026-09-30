"""Reporting workspace page: folder select + load + Master_File operation."""

from __future__ import annotations

import logging
import threading
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable

import customtkinter as ctk
import pandas as pd
import tkinter as tk

from data_loader import frame_summary
from reporting import (
    VACANT_SHEETS,
    build_master_file,
    build_vacant_files,
    export_vacant_workbook,
    load_reporting_files,
)
from ui.busy import BusyOverlay
from ui.data_table import DataTable
from ui.error_dialog import show_error_dialog
from ui.log_panel import LogPanel

ACCENT = "#1f6aa5"
MASTER_HEADER = "#2b579a"


class ReportingPage(ctk.CTkFrame):
    """Folder → Master-Data (Marketing Employee + Merged) → Master_File view."""

    def __init__(self, master, on_back: Callable[[], None] | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.on_back = on_back

        self.root_folder: str = ""
        self.merged_df: pd.DataFrame = pd.DataFrame()
        self.marketing_df: pd.DataFrame = pd.DataFrame()
        self.master_df: pd.DataFrame = pd.DataFrame()
        self.vacant_sheets: dict[str, pd.DataFrame] = {}
        self.current_view: str = "Master_File"
        self._busy_overlay: BusyOverlay | None = None
        self._last_tb: str = ""

        self._build_topbar()
        self._build_main()
        self._build_bottom()
        self.log("info", "Select the root folder (containing Master-Data), then Load.")

    # ------------------------------------------------------------------ layout
    def _build_topbar(self) -> None:
        bar = ctk.CTkFrame(self, corner_radius=12)
        bar.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkButton(
            bar, text="← Back", width=80, fg_color="#3a3a3a",
            hover_color="#4a4a4a", command=self._on_back_pressed,
        ).pack(side="left", padx=(10, 0), pady=10)
        ctk.CTkButton(
            bar, text="📁 Select Folder", fg_color=ACCENT, hover_color="#185a8d",
            command=self.on_select_folder,
        ).pack(side="left", padx=10, pady=10)
        self.path_label = ctk.CTkLabel(
            bar, text="No folder selected", font=("Segoe UI", 11), text_color="gray70",
        )
        self.path_label.pack(side="left", padx=6)
        ctk.CTkButton(
            bar, text="⬇ Load", width=90, fg_color="#217346", hover_color="#1a5c38",
            command=self.on_load,
        ).pack(side="right", padx=10, pady=10)

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=6)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=0)
        main.grid_rowconfigure(0, weight=1)

        self.master_table = DataTable(
            main, "📊 Master Data View", header_color=MASTER_HEADER,
            on_hover_info=self._hover_tip,
        )
        self.master_table.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ops = ctk.CTkFrame(main, corner_radius=12, width=280)
        ops.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        ops.configure(width=280)
        ctk.CTkLabel(ops, text="⚙ Operations", font=("Segoe UI", 13, "bold")).pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        self.status_label = ctk.CTkLabel(
            ops, text="Files not loaded", font=("Segoe UI", 11),
            text_color="gray70", wraplength=240, justify="left",
        )
        self.status_label.pack(anchor="w", padx=14, pady=(0, 8))
        ctk.CTkButton(
            ops, text="▶ Master_File", fg_color=ACCENT, hover_color="#185a8d",
            command=self.on_master_file,
        ).pack(fill="x", padx=14, pady=6)
        ctk.CTkButton(
            ops, text="▶ Vacant_File", fg_color=ACCENT, hover_color="#185a8d",
            command=self.on_vacant_file,
        ).pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(ops, text="View:", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=14, pady=(8, 2)
        )
        self.view_menu = ctk.CTkOptionMenu(
            ops, values=["Master_File"], command=self.on_view_change
        )
        self.view_menu.pack(fill="x", padx=14, pady=(0, 6))
        # Placeholders for later operations — add buttons here.
        for name in ("Operation 3", "Operation 4"):
            ctk.CTkButton(
                ops, text=name, fg_color="#3a3a3a", hover_color="#4a4a4a",
                state="disabled",
            ).pack(fill="x", padx=14, pady=6)

    def _build_bottom(self) -> None:
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(6, 12))
        row = ctk.CTkFrame(bottom, fg_color="transparent")
        row.pack(anchor="w", pady=(0, 6))
        ctk.CTkButton(
            row, text="💾 Export Master_File", fg_color=MASTER_HEADER,
            hover_color="#1a3f75", command=self.on_export,
        ).pack(side="left", padx=(0, 8))
        self.export_vacant_btn = ctk.CTkButton(
            row, text="💾 Export Vacant_File", fg_color="#3a3a3a",
            hover_color="#4a4a4a", command=self.on_export_vacant,
            state="disabled",
        )
        self.export_vacant_btn.pack(side="left")
        self.log_panel = LogPanel(bottom)
        self.log_panel.pack(fill="x")

    # ------------------------------------------------------------------ helpers
    def log(self, level: str, message: str) -> None:
        self.log_panel.log(level, message)

    def _hover_tip(self, text: str) -> None:
        self.log("info", f"Column info — {text}")

    def _on_back_pressed(self) -> None:
        if self.on_back is not None:
            self.on_back()

    def _run_background(
        self, message: str, worker: Callable[[], Any],
        on_done: Callable[[Any, BaseException | None], None],
    ) -> None:
        if self._busy_overlay is not None:
            self.log("warning", "Please wait — another task is still running.")
            return
        self._busy_overlay = BusyOverlay.show(self.winfo_toplevel(), message)
        state: dict[str, Any] = {"result": None, "error": None, "done": False}

        def _target() -> None:
            # Never touch Tk from this thread — just park the outcome.
            try:
                state["result"] = worker()
            except Exception as exc:  # noqa: BLE001 - forwarded to on_done
                state["error"] = exc
                self._last_tb = traceback.format_exc()
            state["done"] = True

        threading.Thread(target=_target, daemon=True).start()
        self._poll_background(on_done, state)

    def _poll_background(
        self, on_done: Callable[[Any, BaseException | None], None],
        state: dict[str, Any],
    ) -> None:
        """Main-thread poll for worker completion (Tk calls stay on this thread)."""
        if not state["done"]:
            if self._busy_overlay is None:
                return  # window closed mid-task — drop the outcome
            try:
                self.after(100, lambda: self._poll_background(on_done, state))
            except tk.TclError:
                pass
            return
        self._finish_background(on_done, state["result"], state["error"])

    def _finish_background(
        self, on_done: Callable[[Any, BaseException | None], None],
        result: Any, error: BaseException | None,
    ) -> None:
        overlay, self._busy_overlay = self._busy_overlay, None
        if overlay is not None:
            overlay.close()
        on_done(result, error)

    # ------------------------------------------------------------------ events
    def on_select_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select root folder (contains Master-Data)")
        if not folder:
            return
        self.root_folder = folder
        short = folder if len(folder) <= 70 else "…" + folder[-69:]
        self.path_label.configure(text=short)
        self.log("info", f"Root folder: {Path(folder).name}")

    def on_load(self) -> None:
        if not self.root_folder:
            self.log("warning", "Select the root folder first.")
            return
        root = self.root_folder
        self._run_background(
            "Loading Master-Data…",
            lambda: load_reporting_files(root),
            self._done_load,
        )

    def _done_load(self, result: Any, error: BaseException | None) -> None:
        if error is not None:
            self.merged_df = pd.DataFrame()
            self.marketing_df = pd.DataFrame()
            self.status_label.configure(text="Files not loaded")
            self.log("error", str(error))
            logging.error("Reporting load failed:\n%s", self._last_tb)
            show_error_dialog(self.winfo_toplevel(), "Reporting — load failed", str(error))
            return
        self.merged_df = result["merged_df"]
        self.marketing_df = result["marketing_df"]
        self.status_label.configure(
            text=f"✔ {Path(str(result['merged_path'])).name}\n"
                 f"✔ {Path(str(result['marketing_path'])).name}"
        )
        self.log(
            "success",
            f"Loaded Merged: {frame_summary(self.merged_df)} | "
            f"Marketing Employee: {frame_summary(self.marketing_df)}",
        )

    def on_master_file(self) -> None:
        if self.merged_df.empty or self.marketing_df.empty:
            self.log("warning", "Load both files first (Select Folder → Load).")
            return
        merged, marketing = self.merged_df, self.marketing_df
        self._run_background(
            "Building Master_File…",
            lambda: build_master_file(merged, marketing),
            self._done_master_file,
        )

    def _done_master_file(self, result: Any, error: BaseException | None) -> None:
        if error is not None:
            self.log("error", f"'Master_File' failed: {error}")
            logging.error("Master_File failed:\n%s", self._last_tb)
            show_error_dialog(
                self.winfo_toplevel(), "Master_File — failed", str(error)
            )
            return
        if not isinstance(result, pd.DataFrame) or result.empty:
            self.log("warning", "'Master_File' returned no rows — view unchanged.")
            return
        self.master_df = result
        self.master_table.set_dataframe(result)
        self.master_table.title_label.configure(text="📊 Master_File")
        self.current_view = "Master_File"
        self.view_menu.set("Master_File")
        summary = str((getattr(result, "attrs", {}) or {}).get("summary", ""))
        self.log(
            "info",
            f"Applied operation: Master_File → {frame_summary(result)}"
            + (f" | {summary}" if summary else ""),
        )

    def on_view_change(self, name: str) -> None:
        """Switch the data view between Master_File and vacant sheets."""
        self.current_view = name
        self.master_table.title_label.configure(text=f"📊 {name}")
        if name == "Master_File":
            self.master_table.set_dataframe(self.master_df)
        else:
            self.master_table.set_dataframe(
                self.vacant_sheets.get(name, pd.DataFrame())
            )

    def on_vacant_file(self) -> None:
        if self.master_df.empty:
            self.log("warning", "Build Master_File first.")
            return
        if self.marketing_df.empty:
            self.log("warning", "Load both files first (Select Folder → Load).")
            return
        master, marketing = self.master_df, self.marketing_df
        self._run_background(
            "Building Vacant_File…",
            lambda: build_vacant_files(master, marketing),
            self._done_vacant_file,
        )

    def _done_vacant_file(self, result: Any, error: BaseException | None) -> None:
        if error is not None:
            self.log("error", f"'Vacant_File' failed: {error}")
            logging.error("Vacant_File failed:\n%s", self._last_tb)
            show_error_dialog(
                self.winfo_toplevel(), "Vacant_File — failed", str(error)
            )
            return
        if not isinstance(result, dict) or not result:
            self.log("warning", "'Vacant_File' returned no rows — view unchanged.")
            return
        self.vacant_sheets = result
        self.view_menu.configure(values=["Master_File", *VACANT_SHEETS])
        first = next(
            (s for s in VACANT_SHEETS if not result.get(s, pd.DataFrame()).empty),
            VACANT_SHEETS[0],
        )
        self.current_view = first
        self.view_menu.set(first)
        self.master_table.title_label.configure(text=f"📊 {first}")
        self.master_table.set_dataframe(result.get(first, pd.DataFrame()))
        self.export_vacant_btn.configure(
            state="normal", fg_color=MASTER_HEADER, hover_color="#1a3f75"
        )
        parts = " | ".join(
            f"{name}: {frame_summary(df)}" for name, df in result.items()
        )
        self.log("info", f"Applied operation: Vacant_File → {parts}")
        for name, df in result.items():
            if df.empty:
                self.log(
                    "warning",
                    f"'{name}' has 0 rows — no master rows with "
                    "EMPP_CODE=EM00000000 for that division + Hier 1/2. "
                    "Use the View dropdown to inspect it.",
                )

    def on_export_vacant(self) -> None:
        if not self.vacant_sheets:
            self.log("warning", "Nothing to export — build Vacant_File first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export vacant file",
            defaultextension=".xlsx",
            initialfile=f"Vacant_File_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
        )
        if not path:
            return
        snapshot = dict(self.vacant_sheets)
        self._run_background(
            "Exporting vacant…",
            lambda: export_vacant_workbook(snapshot, path),
            lambda size, err: self._done_export_vacant(path, size, err),
        )

    def _done_export_vacant(
        self, path: str, size: Any, error: BaseException | None
    ) -> None:
        if error is not None:
            self.log("error", f"Vacant export failed: {error}")
            logging.error("Vacant export failed:\n%s", self._last_tb)
            return
        size_bytes = size or 0
        if size_bytes >= 1024 * 1024:
            sizestr = f"{size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes >= 1024:
            sizestr = f"{size_bytes / 1024:.0f} KB"
        else:
            sizestr = f"{size_bytes} B"
        self.log(
            "success", f"Exported vacant → {Path(path).name} ({sizestr})"
        )

    def on_export(self) -> None:
        if self.master_df.empty:
            self.log("warning", "Nothing to export — build Master_File first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export master file",
            defaultextension=".xlsx",
            initialfile=f"Master_File_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
        )
        if not path:
            return
        snapshot = self.master_df
        self._run_background(
            "Exporting…",
            lambda: self._worker_export(snapshot, path),
            lambda size, err: self._done_export(snapshot, path, size, err),
        )

    @staticmethod
    def _worker_export(df: pd.DataFrame, path: str) -> int:
        if Path(path).suffix.lower() == ".csv":
            df.to_csv(path, index=False)
        else:
            df.to_excel(path, index=False, engine="openpyxl")
        return Path(path).stat().st_size

    def _done_export(
        self, df: pd.DataFrame, path: str, size: Any, error: BaseException | None
    ) -> None:
        if error is not None:
            self.log("error", f"Export failed: {error}")
            logging.error("Export failed:\n%s", self._last_tb)
            return
        size_bytes = size or 0
        if size_bytes >= 1024 * 1024:
            sizestr = f"{size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes >= 1024:
            sizestr = f"{size_bytes / 1024:.0f} KB"
        else:
            sizestr = f"{size_bytes} B"
        self.log(
            "success",
            f"Exported master → {Path(path).name} ({frame_summary(df)}, {sizestr})",
        )
