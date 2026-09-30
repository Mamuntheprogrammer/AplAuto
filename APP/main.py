"""App entry point: window setup, layout, and event orchestration."""

from __future__ import annotations

import logging
import re
import threading
import tkinter as tk
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable

import customtkinter as ctk
import pandas as pd

from data_loader import frame_summary, get_sheet_names, load_sheet
from operations import (
    DIVISION_NAMES,
    Z_REPORTS,
    division_codes,
    get_operation,
    period_month_label,
    validate_period,
)
from ui.busy import BusyOverlay
from ui.data_table import DataTable
from ui.error_dialog import show_error_dialog
from ui.helpers import center_over
from ui.log_panel import LogPanel
from ui.ops_panel import OperationsPanel

logging.basicConfig(
    filename="app.log", level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT = "#1f6aa5"
SOURCE_HEADER = "#217346"  # Excel green
RESULT_HEADER = "#2b579a"  # Office/Excel blue — distinct from source

_BENIGN_TEARDOWN = (
    "bad window path name",
    "invalid command name",
    "can't delete Tcl command",
    "application has been destroyed",
    "was deleted before its visibility changed",
)


def _is_benign_teardown_msg(message: str) -> bool:
    """True for harmless CustomTkinter/Tk races during dialog/window teardown."""
    return any(hint in message for hint in _BENIGN_TEARDOWN)


def _install_teardown_guards(root: ctk.CTk) -> None:
    """Swallow benign Tk teardown races (Python callbacks AND Tcl bgerror).

    CustomTkinter leaves pending `after` jobs (dpi check, animations) that
    fire after a dialog/window is destroyed. Tcl-level `after` failures go
    to the Tcl bgerror handler — NOT through report_callback_exception —
    so both must be filtered.
    """
    _orig_report = root.report_callback_exception

    def _report(exc: Any, val: Any, tb: Any) -> None:
        if isinstance(val, tk.TclError) and _is_benign_teardown_msg(str(val)):
            logging.error("Ignored benign Tk teardown race: %s", val)
            return
        _orig_report(exc, val, tb)

    root.report_callback_exception = _report  # type: ignore[method-assign]

    def _bgerror(*args: Any) -> None:
        msg = " ".join(str(a) for a in args)
        if _is_benign_teardown_msg(msg):
            logging.error("Ignored benign Tk teardown race: %s", msg)
            return
        import sys

        print(f"Tcl background error: {msg}", file=sys.stderr)

    try:
        root.tk.createcommand("::tk::bgerror", _bgerror)
    except tk.TclError:
        pass
    try:
        # Explicitly point this interpreter's bgerror at our filter as well,
        # in case the default ::tk::bgerror lookup is bypassed during teardown.
        bg_name = root.tk.createcommand("::reporting_bgerror", _bgerror)
        root.tk.call("interp", "bgerror", "", bg_name)
    except tk.TclError:
        pass


class SetupPage(ctk.CTkFrame):
    """Setup workspace (existing Excel processing GUI) as an embeddable page."""

    def __init__(self, master, on_back: Callable[[], None] | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.on_back = on_back

        self.file_path: str = ""
        self.sheets: list[str] = []
        self.source_df: pd.DataFrame = pd.DataFrame()
        self.result_df: pd.DataFrame = pd.DataFrame()
        self.last_op: str = ""
        self.last_divisions: list[str] = []
        self.last_variant: str = ""
        self._busy_overlay: BusyOverlay | None = None
        self._last_tb: str = ""

        self._build_topbar()
        self._build_main()
        self._build_bottom()

        # Optional drag-and-drop if tkinterdnd2 is installed; else file dialog only.
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore[import]  # noqa: F401
            self.log("info", "Tip: install tkinterdnd2 to enable file drag-and-drop.")
        except ImportError:
            pass

        self.log("info", "Ready. Click 'Import File' to load an Excel / CSV file.")

    # ------------------------------------------------------------------ layout
    def _build_topbar(self) -> None:
        bar = ctk.CTkFrame(self, corner_radius=12)
        bar.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkButton(
            bar, text="← Back", width=80, fg_color="#3a3a3a", hover_color="#4a4a4a",
            command=self._on_back_pressed,
        ).pack(side="left", padx=(10, 0), pady=10)
        ctk.CTkButton(
            bar, text="📂 Import File", fg_color=ACCENT, hover_color="#185a8d",
            command=self.on_import,
        ).pack(side="left", padx=10, pady=10)
        self.path_label = ctk.CTkLabel(
            bar, text="No file loaded", font=("Segoe UI", 11), text_color="gray70",
        )
        self.path_label.pack(side="left", padx=6)

        ctk.CTkButton(
            bar, text="⟳ Refresh", width=90, fg_color="#3a3a3a", hover_color="#4a4a4a",
            command=self.on_refresh,
        ).pack(side="right", padx=10, pady=10)
        ctk.CTkButton(
            bar, text="Reset", width=70, fg_color="#3a3a3a", hover_color="#4a4a4a",
            command=self.on_reset,
        ).pack(side="right", pady=10)
        self.sheet_menu = ctk.CTkOptionMenu(
            bar, values=["(no sheets)"], width=200, command=self.on_sheet_change
        )
        self.sheet_menu.pack(side="right", padx=6, pady=10)
        ctk.CTkLabel(bar, text="Sheet:", font=("Segoe UI", 11, "bold")).pack(side="right")

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=6)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=0)
        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self.source_table = DataTable(main, "📄 Source Data View", header_color=SOURCE_HEADER,
                                      on_hover_info=self._hover_tip)
        self.source_table.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        self.result_table = DataTable(main, "✨ Result View", header_color=RESULT_HEADER,
                                      on_hover_info=self._hover_tip)
        self.result_table.grid(row=1, column=0, sticky="nsew", padx=(0, 6))

        self.ops_panel = OperationsPanel(main, on_apply=self.on_apply)
        self.ops_panel.grid(row=0, column=1, rowspan=2, sticky="ns", padx=(6, 0))
        self.ops_panel.configure(width=320)

    def _build_bottom(self) -> None:
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(6, 12))
        ctk.CTkButton(
            bottom, text="💾 Export Result", fg_color=RESULT_HEADER, hover_color="#0b5f45",
            command=self.on_export,
        ).pack(anchor="w", pady=(0, 6))
        self.log_panel = LogPanel(bottom)
        self.log_panel.pack(fill="x")

    # ------------------------------------------------------------------ helpers
    def log(self, level: str, message: str) -> None:
        """Write to the status panel (full tracebacks go to app.log)."""
        self.log_panel.log(level, message)

    def _hover_tip(self, text: str) -> None:
        self.log("info", f"Column info — {text}")

    def _short_path(self, path: str, limit: int = 70) -> str:
        return path if len(path) <= limit else "…" + path[-(limit - 1):]

    # ------------------------------------------------- background runner + loader
    def _run_background(
        self, message: str, worker: Callable[[], Any],
        on_done: Callable[[Any, BaseException | None], None],
    ) -> None:
        """Run ``worker`` in a thread with a loader; ``on_done(result, error)`` on UI thread."""
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
        """Hide the loader, then handle the worker outcome (always UI thread)."""
        overlay, self._busy_overlay = self._busy_overlay, None
        if overlay is not None:
            overlay.close()
        on_done(result, error)

    # ------------------------------------------------------------------ events
    def _on_back_pressed(self) -> None:
        """Page navigation back to the start page (same window, no reopen)."""
        if self.on_back is not None:
            self.on_back()

    def on_import(self) -> None:
        """Open file dialog, then load sheet names + first sheet in background."""
        if self._busy_overlay is not None:
            self.log("warning", "Please wait — another task is still running.")
            return
        path = filedialog.askopenfilename(
            title="Select Excel / CSV file",
            filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        self._run_background("Loading file…", lambda: self._worker_open(path), self._done_open)

    def _worker_open(self, path: str) -> dict[str, Any]:
        """Background part of file open: sheet names + first sheet data."""
        sheets = get_sheet_names(path)
        return {"path": path, "sheets": sheets, "df": load_sheet(path, sheets[0])}

    def _done_open(self, result: Any, error: BaseException | None) -> None:
        """UI-thread handling of the file-open outcome."""
        if error is not None:
            self.log("error", str(error))
            logging.error("File open failed:\n%s", self._last_tb)
            return
        path, sheets, df = result["path"], result["sheets"], result["df"]
        self.file_path = path
        self.path_label.configure(text=self._short_path(path))
        self.sheet_menu.configure(values=sheets)
        self.sheet_menu.set(sheets[0])
        self.log("success", f"Loaded file: {Path(path).name} ({len(sheets)} sheet(s))")
        self._show_sheet(sheets[0], df)

    def on_sheet_change(self, sheet: str) -> None:
        """User picked a different sheet — load it in background."""
        if self.file_path and self._busy_overlay is None:
            self._run_background(
                f"Loading {sheet}…",
                lambda: load_sheet(self.file_path, sheet),
                lambda df, err: self._done_sheet(sheet, df, err),
            )

    def on_reset(self) -> None:
        """Clear file selection, both views, and operation state."""
        if self._busy_overlay is not None:
            self.log("warning", "Please wait — another task is still running.")
            return
        self.file_path = ""
        self.sheets = []
        self.source_df = pd.DataFrame()
        self.result_df = pd.DataFrame()
        self.last_op = ""
        self.last_divisions = []
        self.last_variant = ""
        self.path_label.configure(text="No file loaded")
        self.sheet_menu.configure(values=["(no sheets)"])
        self.sheet_menu.set("(no sheets)")
        self.source_table.set_dataframe(pd.DataFrame())
        self.result_table.set_dataframe(pd.DataFrame())
        self.ops_panel.reset_params()
        self.log("info", "Reset — file selection and views cleared.")

    def on_refresh(self) -> None:
        """Reload the current file/sheet in background (picks up external edits)."""
        if not self.file_path:
            self.log("warning", "Nothing to refresh — import a file first.")
            return
        sheet = self.sheet_menu.get()
        self._run_background(
            "Refreshing…",
            lambda: (get_sheet_names(self.file_path), load_sheet(self.file_path, sheet)),
            lambda res, err: self._done_refresh(sheet, res, err),
        )

    def _done_refresh(self, sheet: str, result: Any, error: BaseException | None) -> None:
        """UI-thread handling of the refresh outcome."""
        if error is not None:
            self.log("error", str(error))
            logging.error("Refresh failed:\n%s", self._last_tb)
            return
        sheets, df = result
        self.sheets = sheets
        self.sheet_menu.configure(values=sheets)
        if sheet in sheets:
            self.sheet_menu.set(sheet)
            self._show_sheet(sheet, df)
        else:  # selected sheet vanished — fall back to the first one
            self.sheet_menu.set(sheets[0])
            self.on_sheet_change(sheets[0])
        self.log("info", "Refreshed current file/sheet.")

    def _done_sheet(self, sheet: str, df: Any, error: BaseException | None) -> None:
        """UI-thread handling of a sheet-load outcome."""
        if error is not None:
            self.source_df = pd.DataFrame()
            self.source_table.set_dataframe(self.source_df)
            self.log("error", str(error))
            logging.error("load_sheet failed:\n%s", self._last_tb)
            return
        self._show_sheet(sheet, df)

    def _show_sheet(self, sheet: str, df: pd.DataFrame) -> None:
        """Paint an already-loaded sheet into the source view."""
        self.source_df = df
        self.source_table.set_dataframe(df)
        self.ops_panel.set_columns([str(c) for c in df.columns])
        self.log("success", f"Loaded {sheet}: {frame_summary(df)}")

    def _confirm_period(self, op_name: str, start: str, end: str, divisions: list[str]) -> bool:
        """Modal popup showing the selected dates + full month name. Returns True if confirmed."""
        try:
            label = period_month_label(start, end)
        except ValueError:
            label = "—"
        codes = division_codes(divisions)
        root = self.winfo_toplevel()
        dialog = ctk.CTkToplevel(root)
        dialog.title("Confirm Period")
        center_over(dialog, root, 380, 260)
        dialog.resizable(False, False)
        dialog.transient(root)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=op_name, font=("Segoe UI", 14, "bold")).pack(pady=(16, 4))
        ctk.CTkLabel(dialog, text=f"{start.strip()}  →  {end.strip()}",
                     font=("Segoe UI", 12)).pack()
        ctk.CTkLabel(dialog, text=label, font=("Segoe UI", 18, "bold"),
                     text_color="#4cc38a").pack(pady=(8, 4))
        ctk.CTkLabel(dialog, text=f"Division: {', '.join(codes) if codes else '—'}",
                     font=("Segoe UI", 11), text_color="gray70").pack(pady=(0, 12))
        confirmed: list[bool] = []

        def _ok() -> None:
            confirmed.append(True)
            dialog.destroy()

        def _cancel() -> None:
            dialog.destroy()

        btns = ctk.CTkFrame(dialog, fg_color="transparent")
        btns.pack(pady=6)
        ctk.CTkButton(btns, text="OK", width=120, fg_color="#1f6aa5", command=_ok).pack(
            side="left", padx=8
        )
        ctk.CTkButton(btns, text="Cancel", width=120, fg_color="#3a3a3a",
                      command=_cancel).pack(side="left", padx=8)
        dialog.protocol("WM_DELETE_WINDOW", _cancel)
        root.wait_window(dialog)
        return bool(confirmed)

    def on_apply(self, op_name: str, params: dict[str, Any]) -> None:
        """Validate params, then run the operation in background with a loader."""
        if self._busy_overlay is not None:
            self.log("warning", "Please wait — another task is still running.")
            return
        if self.source_df.empty:
            self.log("warning", "Import a file with data before applying an operation.")
            return
        spec = get_operation(op_name)
        # Z-reports: Division + same-month Start/End dates are mandatory.
        if op_name in Z_REPORTS:
            divisions = params.get("divisions", [])
            if not divisions:
                self.log("warning", f"'{op_name}': select a Division radio option.")
                return
            start = str(params.get("start_date", "")).strip()
            end = str(params.get("end_date", "")).strip()
            if not start or not end:
                self.log("warning", f"'{op_name}': Start and End date are required (DD.MM.YYYY).")
                return
            try:
                validate_period(start, end)
                label = period_month_label(start, end)
            except ValueError as exc:
                self.log("warning", f"'{op_name}': {exc}")
                return
            if not self._confirm_period(op_name, start, end, divisions):  # type: ignore[arg-type]
                self.log("info", f"'{op_name}' cancelled by user.")
                return
        if op_name in Z_REPORTS:  # reference files (mvke/zemp) live next to the input
            params["input_dir"] = str(Path(self.file_path).parent) if self.file_path else ""
        missing = [
            p.label for p in spec.params
            if p.required and p.kind not in ("columns", "divisions")
            and not str(params.get(p.name, "")).strip()
        ]
        if missing:
            self.log("warning", f"Missing parameters for '{op_name}': {', '.join(missing)}")
            return
        source = self.source_df
        self._run_background(
            f"Running {op_name}…",
            lambda: spec.func(source, **params),
            lambda res, err: self._done_apply(op_name, params, res, err),
        )

    def _done_apply(
        self, op_name: str, params: dict[str, Any],
        result: Any, error: BaseException | None,
    ) -> None:
        """UI-thread handling of the operation outcome."""
        if error is not None:
            if isinstance(error, ValueError):  # validation: stop, log + popup with Copy
                self.log("error", f"'{op_name}' failed: {error}")
                logging.error("Operation %s failed:\n%s", op_name, self._last_tb)
                show_error_dialog(self.winfo_toplevel(), f"{op_name} — validation failed", str(error))
            else:
                self.log("error", f"'{op_name}' failed: {error}")
                logging.error("Operation %s failed:\n%s", op_name, self._last_tb)
            return
        if not isinstance(result, pd.DataFrame) or result.empty:
            self.log("warning", f"'{op_name}' returned no rows — result view unchanged.")
            return
        self.result_df = result
        self.result_table.set_dataframe(result)
        self.last_op = op_name
        self.last_divisions = (
            division_codes(params.get("divisions", []))  # type: ignore[arg-type]
            if op_name in Z_REPORTS else []
        )
        attrs = getattr(result, "attrs", {}) or {}
        self.last_variant = str(attrs.get("variant", ""))
        extra = ""
        if op_name in Z_REPORTS:
            try:
                extra = (
                    f" | {str(params.get('start_date', '')).strip()} → "
                    f"{str(params.get('end_date', '')).strip()} "
                    f"({period_month_label(str(params.get('start_date', '')), str(params.get('end_date', '')))})"
                    f" | Div: {', '.join(division_codes(params.get('divisions', [])))}"  # type: ignore[arg-type]
                )
            except ValueError:
                extra = ""
        summary = str(attrs.get("summary", ""))
        self.log(
            "info",
            f"Applied operation: {op_name}{extra} → {frame_summary(result)}"
            + (f" | {summary}" if summary else ""),
        )

    def _default_export_name(self) -> str:
        """Build OperationName_Division-Or-Variant_YYYYMMDD_HHMMSS for the save dialog."""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        op = re.sub(r"[^\w\-]+", "_", self.last_op).strip("_") or "Result"
        if self.last_variant:
            middle = re.sub(r"[^\w\-]+", "_", self.last_variant).strip("_")
        elif self.last_divisions:
            middle = re.sub(
                r"[^\w\-]+", "_",
                "-".join(DIVISION_NAMES.get(c, c) for c in self.last_divisions),
            ).strip("_")
        else:
            middle = ""
        return f"{op}_{middle}_{stamp}" if middle else f"{op}_{stamp}"

    def on_export(self) -> None:
        """Save the current result in background; success is logged only when done."""
        if self._busy_overlay is not None:
            self.log("warning", "Please wait — another task is still running.")
            return
        if self.result_df.empty:
            self.log("warning", "Nothing to export — apply an operation first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export result",
            defaultextension=".xlsx",
            initialfile=self._default_export_name() + ".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
        )
        if not path:
            return
        snapshot = self.result_df
        self._run_background(
            "Exporting…",
            lambda: self._worker_export(snapshot, path),
            lambda size, err: self._done_export(snapshot, path, size, err),
        )

    @staticmethod
    def _worker_export(df: pd.DataFrame, path: str) -> int:
        """Background file write; returns bytes written."""
        if Path(path).suffix.lower() == ".csv":
            df.to_csv(path, index=False)
        else:
            df.to_excel(path, index=False, engine="openpyxl")
        return Path(path).stat().st_size

    def _done_export(
        self, df: pd.DataFrame, path: str, size: Any, error: BaseException | None
    ) -> None:
        """UI-thread handling of the export outcome (size = bytes written)."""
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
            f"Exported result → {Path(path).name} ({frame_summary(df)}, {sizestr})",
        )


class AppShell(ctk.CTk):
    """Single app window; pages switch inside it (same size, no new windows)."""

    def __init__(self, start_page: str = "start") -> None:
        super().__init__()
        self.title("Excel Processor — Modern GUI")
        self.minsize(1200, 750)
        self.geometry("1280x800")
        _install_teardown_guards(self)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        from ui.reporting_page import ReportingPage
        from ui.start_window import StartPage

        self.start_page = StartPage(
            container,
            on_open_setup=lambda: self.show("setup"),
            on_open_reporting=lambda: self.show("reporting"),
        )
        self.setup_page = SetupPage(container, on_back=lambda: self.show("start"))
        self.reporting_page = ReportingPage(
            container, on_back=lambda: self.show("start")
        )
        for page in (self.start_page, self.setup_page, self.reporting_page):
            page.grid(row=0, column=0, sticky="nsew")
        self.show(start_page if start_page in ("start", "setup", "reporting") else "start")

    def show(self, name: str) -> None:
        """Raise one page; the window itself never closes or resizes."""
        {"start": self.start_page, "setup": self.setup_page,
         "reporting": self.reporting_page}[name].tkraise()

    def _on_close(self) -> None:
        """Hide instantly, cancel pending afters, then quit + destroy.

        CustomTkinter leaves repeating `after` jobs (dpi checks, animations)
        that otherwise fire on half-destroyed dialogs and print
        'bad window path name .!ctktoplevelN' to the console.
        """
        try:
            self.withdraw()
        except Exception:
            pass
        try:
            for after_id in self.tk.call("after", "info"):
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.quit()
        except Exception:
            pass
        try:
            self.destroy()
        except tk.TclError as exc:
            if not _is_benign_teardown_msg(str(exc)):
                raise


# Backward-compat alias (SetupPage was previously named ExcelApp).
ExcelApp = SetupPage


def main() -> None:
    """Launch the single-window app (page navigation, same size)."""
    import sys

    first = "setup" if "--setup" in sys.argv else "start"
    app = AppShell(start_page=first)
    app.mainloop()


if __name__ == "__main__":
    main()
