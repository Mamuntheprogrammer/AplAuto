#!/usr/bin/env python3
"""
Target vs Achievement - control panel.

    python gui.py

1. Data    pick the sales Excel and the hierarchy (zemp) Excel -> builds data/data.db
2. Setup   which levels / divisions / month / employees
3. Output  HTML (desktop), HTML (mobile) and/or PDF, and the folder to write them to

The window runs the same code as the command line tools (generate_reports.py,
generate_pdf.py, tva/xl2db.py), so anything you do here you can also script.
"""
from __future__ import annotations

import contextlib
import json
import os
import queue
import re
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import config

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / "gui_settings.json"
MONTH_CHOICES = ["Auto (latest month with data)", "January", "February", "March", "April", "May",
                 "June", "July", "August", "September", "October", "November", "December"]

NAVY, BRAND, INK, MUTE, LINE, BG = "#0E2A47", "#0B67C2", "#14263B", "#5B6B7F", "#D5DDE7", "#EEF2F6"
FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")


class QueueWriter:
    """File-like object that hands everything printed by the generators to the log window."""

    def __init__(self, q: "queue.Queue[str]") -> None:
        self.q = q

    def write(self, text: str) -> int:
        if text:
            self.q.put(text)
        return len(text)

    def flush(self) -> None:
        pass


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Target vs Achievement - Report Builder")
        self.geometry("940x840")
        self.minsize(860, 700)
        self.configure(bg=BG)
        self._style()

        self.q: "queue.Queue[str]" = queue.Queue()          # text for the log window
        self.done_q: "queue.Queue[tuple]" = queue.Queue()   # (callback, result, error) from worker threads
        self.busy = False

        # ---- variables (defaults come from config.py) -------------------
        self.var_sales = tk.StringVar()
        self.var_zemp = tk.StringVar()
        self.var_db = tk.StringVar(value=str(config.DB_PATH))
        self.var_out = tk.StringVar(value=str(config.OUTPUT_DIR))
        self.var_levels = {lvl: tk.BooleanVar(value=lvl in config.REPORT_LEVELS)
                           for lvl in sorted(config.LEVELS, reverse=True) if lvl != 1}
        self.var_all_div = tk.BooleanVar(value=config.REPORT_DIVISIONS is None)
        self.var_div = tk.StringVar(value=", ".join(map(str, config.REPORT_DIVISIONS or ())))
        self.var_month = tk.StringVar(value=MONTH_CHOICES[config.REPORT_UPTO_MONTH or 0])
        self.var_emp = tk.StringVar()
        self.var_no_team = tk.BooleanVar(value=not config.SKIP_IF_NO_TEAM)
        self.var_fmt_html = tk.BooleanVar(value="html" in config.OUTPUT_FORMATS)
        self.var_fmt_mobile = tk.BooleanVar(value="mobile" in config.OUTPUT_FORMATS)
        self.var_fmt_pdf = tk.BooleanVar(value=False)
        self.var_orient = tk.StringVar(value="landscape")
        self.var_clock = tk.StringVar()
        self.var_dbinfo = tk.StringVar()
        self.var_status = tk.StringVar(value="Ready")

        self._load_settings()
        self._build()
        self._refresh_db_info()
        self._tick()
        self._poll()
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ------------------------------------------------------------------ look
    def _style(self) -> None:
        st = ttk.Style(self)
        with contextlib.suppress(tk.TclError):
            st.theme_use("clam")
        st.configure(".", font=FONT, background=BG, foreground=INK)
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background="white")
        st.configure("TLabel", background="white", foreground=INK)
        st.configure("Mute.TLabel", background="white", foreground=MUTE)
        st.configure("Sec.TLabel", background="white", foreground=INK, font=("Segoe UI", 11, "bold"))
        st.configure("TCheckbutton", background="white")
        st.configure("TRadiobutton", background="white")
        st.configure("TEntry", fieldbackground="white", bordercolor=LINE)
        st.configure("TButton", padding=(12, 5))
        st.configure("Accent.TButton", background=BRAND, foreground="white", font=FONT_B, padding=(18, 8))
        st.map("Accent.TButton", background=[("active", "#0A58A8"), ("disabled", "#9DB9D6")],
               foreground=[("disabled", "white")])
        st.configure("Horizontal.TProgressbar", troughcolor=LINE, background=BRAND)

    def _section(self, parent, title: str, note: str = "", column: int = -1) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12, 16, 14))
        if column < 0:
            card.pack(fill="x", padx=16, pady=(12, 0))
        else:                                                   # side-by-side cards inside a grid frame
            card.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (8, 0))
        ttk.Label(card, text=title, style="Sec.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        if note:
            ttk.Label(card, text=note, style="Mute.TLabel").grid(row=1, column=0, columnspan=4, sticky="w",
                                                                  pady=(0, 6))
        card.columnconfigure(1, weight=1)
        return card

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        head = tk.Frame(self, bg=NAVY)
        head.pack(fill="x")
        tk.Label(head, text="Target vs Achievement", bg=NAVY, fg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=18, pady=(12, 12))
        clock = tk.Frame(head, bg=NAVY)
        clock.pack(side="right", padx=18)
        tk.Label(clock, textvariable=self.var_clock, bg=NAVY, fg="white", font=("Segoe UI", 11),
                 justify="right").pack()

        # ---- 1. data -----------------------------------------------------
        s1 = self._section(self, "1 · Data  (Excel → database)",
                           "Choose the two Excel files. Skip this step if the database is already up to date.")
        self._file_row(s1, 2, "Sales Excel", self.var_sales, self._pick_sales)
        self._file_row(s1, 3, "Hierarchy (zemp) Excel", self.var_zemp, self._pick_zemp)
        self._file_row(s1, 4, "Database file", self.var_db, self._pick_db)
        row = ttk.Frame(s1, style="Card.TFrame")
        row.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self.btn_build = ttk.Button(row, text="Build database from Excel", command=self._build_db)
        self.btn_build.pack(side="left")
        ttk.Label(row, textvariable=self.var_dbinfo, style="Mute.TLabel", wraplength=560,
                  justify="left").pack(side="left", padx=14)

        mid = ttk.Frame(self)
        mid.pack(fill="x", padx=16, pady=(12, 0))
        mid.columnconfigure(0, weight=3, uniform="c")
        mid.columnconfigure(1, weight=2, uniform="c")

        # ---- 2. setup (left) ----------------------------------------------
        s2 = self._section(mid, "2 · Report setup", "Defaults come from config.py.", column=0)
        ttk.Label(s2, text="Levels").grid(row=2, column=0, sticky="nw", pady=4)
        lv = ttk.Frame(s2, style="Card.TFrame")
        lv.grid(row=2, column=1, columnspan=3, sticky="w", pady=4)
        for i, (lvl, var) in enumerate(self.var_levels.items()):
            ttk.Checkbutton(lv, text=config.LEVELS[lvl][0], variable=var).grid(
                row=i // 3, column=i % 3, sticky="w", padx=(0, 18), pady=1)

        ttk.Label(s2, text="Divisions").grid(row=3, column=0, sticky="w", pady=4)
        dv = ttk.Frame(s2, style="Card.TFrame")
        dv.grid(row=3, column=1, columnspan=3, sticky="w", pady=4)
        self.ent_div = ttk.Entry(dv, textvariable=self.var_div, width=12)
        self.ent_div.pack(side="left")
        ttk.Checkbutton(dv, text="All divisions", variable=self.var_all_div,
                        command=self._toggle_div).pack(side="left", padx=(12, 0))

        ttk.Label(s2, text="Report up to").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Combobox(s2, textvariable=self.var_month, values=MONTH_CHOICES, state="readonly",
                     width=28).grid(row=4, column=1, columnspan=3, sticky="w", pady=4)

        ttk.Label(s2, text="Only employees").grid(row=5, column=0, sticky="w", pady=(4, 0), padx=(0, 10))
        ttk.Entry(s2, textvariable=self.var_emp).grid(row=5, column=1, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Label(s2, text="Optional · IDs separated by commas",
                  style="Mute.TLabel").grid(row=6, column=1, columnspan=3, sticky="w", pady=(0, 4))

        ttk.Checkbutton(s2, text="Include managers with nobody under them",
                        variable=self.var_no_team).grid(row=7, column=0, columnspan=4, sticky="w", pady=(2, 0))
        ttk.Button(s2, text="Reset to config.py defaults", command=self._reset_defaults).grid(
            row=8, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self._toggle_div()

        # ---- 3. output (right) --------------------------------------------
        s3 = self._section(mid, "3 · Output", "Choose one or more file types.", column=1)
        ttk.Checkbutton(s3, text="HTML · desktop  (wide tables)", variable=self.var_fmt_html).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=2)
        ttk.Checkbutton(s3, text="HTML · mobile  (cards, no pinned columns)", variable=self.var_fmt_mobile).grid(
            row=3, column=0, columnspan=4, sticky="w", pady=2)
        ttk.Checkbutton(s3, text="PDF  (A4)", variable=self.var_fmt_pdf, command=self._toggle_pdf).grid(
            row=4, column=0, columnspan=4, sticky="w", pady=2)
        self.pdf_opts = ttk.Frame(s3, style="Card.TFrame")
        self.pdf_opts.grid(row=5, column=0, columnspan=4, sticky="w", padx=(24, 0))
        ttk.Radiobutton(self.pdf_opts, text="Landscape", value="landscape", variable=self.var_orient).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(self.pdf_opts, text="Portrait", value="portrait", variable=self.var_orient).pack(side="left")
        ttk.Label(s3, text="Output folder").grid(row=6, column=0, columnspan=4, sticky="w", pady=(10, 2))
        ttk.Entry(s3, textvariable=self.var_out).grid(row=7, column=0, columnspan=3, sticky="ew")
        ttk.Button(s3, text="Browse…", command=self._pick_out).grid(row=7, column=3, padx=(8, 0))
        s3.columnconfigure(0, weight=1)
        self._toggle_pdf()

        # ---- run ---------------------------------------------------------
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=16, pady=(14, 4))
        self.btn_run = ttk.Button(bar, text="Generate reports", style="Accent.TButton", command=self._generate)
        self.btn_run.pack(side="left")
        ttk.Button(bar, text="Open output folder", command=self._open_out).pack(side="left", padx=10)
        ttk.Button(bar, text="Clear log", command=lambda: self.log.delete("1.0", "end")).pack(side="left")
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=160)
        self.progress.pack(side="right")

        self.log = ScrolledText(self, height=7, font=("Consolas", 9), bg="white", fg=INK, relief="flat",
                                highlightthickness=1, highlightbackground=LINE, wrap="word")
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        self.log.insert("end", "Ready. Pick your options and press “Generate reports”.\n")

        ttk.Label(self, textvariable=self.var_status, background=BG, foreground=MUTE).pack(
            anchor="w", padx=18, pady=(0, 8))

    def _file_row(self, parent, row: int, label: str, var: tk.StringVar, command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 12))
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        ttk.Button(parent, text="Browse…", command=command).grid(row=row, column=3, padx=(8, 0), pady=3)

    # ------------------------------------------------------------------ small handlers
    def _tick(self) -> None:
        self.var_clock.set(datetime.now().strftime("%A, %d %B %Y\n%I:%M:%S %p"))
        self.after(1000, self._tick)

    def _toggle_div(self) -> None:
        self.ent_div.configure(state="disabled" if self.var_all_div.get() else "normal")

    def _toggle_pdf(self) -> None:
        for child in self.pdf_opts.winfo_children():
            with contextlib.suppress(tk.TclError):
                child.configure(state="normal" if self.var_fmt_pdf.get() else "disabled")

    def _pick_excel(self, var: tk.StringVar, title: str) -> None:
        path = filedialog.askopenfilename(title=title, filetypes=[("Excel / CSV", "*.xlsx *.xlsm *.csv"),
                                                                  ("All files", "*.*")])
        if path:
            var.set(path)

    def _pick_sales(self) -> None:
        self._pick_excel(self.var_sales, "Select the SALES Excel file")

    def _pick_zemp(self) -> None:
        self._pick_excel(self.var_zemp, "Select the HIERARCHY (zemp) Excel file")

    def _pick_db(self) -> None:
        path = filedialog.asksaveasfilename(title="Database file", defaultextension=".db",
                                            initialfile=Path(self.var_db.get()).name,
                                            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
                                            confirmoverwrite=False)
        if path:
            self.var_db.set(path)
            self._refresh_db_info()

    def _pick_out(self) -> None:
        path = filedialog.askdirectory(title="Output folder", initialdir=self.var_out.get() or str(BASE_DIR))
        if path:
            self.var_out.set(path)

    def _open_out(self) -> None:
        out = Path(self.var_out.get())
        out.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(str(out))                                    # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(out)])
        else:
            subprocess.Popen(["xdg-open", str(out)])

    def _reset_defaults(self) -> None:
        for lvl, var in self.var_levels.items():
            var.set(lvl in config.REPORT_LEVELS)
        self.var_all_div.set(config.REPORT_DIVISIONS is None)
        self.var_div.set(", ".join(map(str, config.REPORT_DIVISIONS or ())))
        self.var_month.set(MONTH_CHOICES[config.REPORT_UPTO_MONTH or 0])
        self.var_emp.set("")
        self.var_no_team.set(not config.SKIP_IF_NO_TEAM)
        self._toggle_div()

    # ------------------------------------------------------------------ database info
    def _refresh_db_info(self) -> None:
        db = Path(self.var_db.get())
        if not db.exists():
            self.var_dbinfo.set("No database yet - build it from the Excel files.")
            return
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            n_sales = con.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
            n_zemp = con.execute("SELECT COUNT(*) FROM zemp").fetchone()[0]
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            last = next((m for m in reversed(months)
                         if con.execute(f'SELECT 1 FROM sales WHERE "{m}_Sol" > 0 LIMIT 1').fetchone()), "-")
            con.close()
            when = datetime.fromtimestamp(db.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
            self.var_dbinfo.set(f"{n_sales:,} sales rows · {n_zemp:,} hierarchy rows · "
                                f"latest month {last} · updated {when}")
        except sqlite3.Error:
            self.var_dbinfo.set("The database could not be read (are the `sales` and `zemp` tables there?)")

    # ------------------------------------------------------------------ settings file
    def _load_settings(self) -> None:
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for key, var in (("sales", self.var_sales), ("zemp", self.var_zemp), ("db", self.var_db),
                         ("out", self.var_out), ("month", self.var_month), ("div", self.var_div),
                         ("orient", self.var_orient)):
            if key in data and isinstance(data[key], str):
                var.set(data[key])
        for key, var in (("all_div", self.var_all_div), ("no_team", self.var_no_team),
                         ("fmt_html", self.var_fmt_html), ("fmt_mobile", self.var_fmt_mobile),
                         ("fmt_pdf", self.var_fmt_pdf)):
            if key in data and isinstance(data[key], bool):
                var.set(data[key])
        for lvl, var in self.var_levels.items():
            if str(lvl) in data.get("levels", {}):
                var.set(bool(data["levels"][str(lvl)]))

    def _save_settings(self) -> None:
        data = {"sales": self.var_sales.get(), "zemp": self.var_zemp.get(), "db": self.var_db.get(),
                "out": self.var_out.get(), "month": self.var_month.get(), "div": self.var_div.get(),
                "orient": self.var_orient.get(), "all_div": self.var_all_div.get(),
                "no_team": self.var_no_team.get(), "fmt_html": self.var_fmt_html.get(),
                "fmt_mobile": self.var_fmt_mobile.get(), "fmt_pdf": self.var_fmt_pdf.get(),
                "levels": {str(k): v.get() for k, v in self.var_levels.items()}}
        with contextlib.suppress(OSError):
            SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _close(self) -> None:
        self._save_settings()
        self.destroy()

    # ------------------------------------------------------------------ running things
    def _set_busy(self, busy: bool, text: str = "") -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.btn_run.configure(state=state)
        self.btn_build.configure(state=state)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(value=0)
        self.var_status.set(text or ("Working…" if busy else "Ready"))

    def _poll(self) -> None:
        try:
            while True:
                text = self.q.get_nowait()
                self.log.insert("end", text)
                self.log.see("end")
        except queue.Empty:
            pass
        try:
            while True:                                      # finished jobs are handled here, in the UI thread
                done, result, error = self.done_q.get_nowait()
                done(result, error)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _run_in_thread(self, work, done) -> None:
        """Run work() in a thread with print() going to the log; then done(result, error) in the UI thread."""
        def target():
            result, error = None, None
            writer = QueueWriter(self.q)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    result = work()
            except Exception as exc:                                  # shown to the user, not swallowed
                error = exc
            self.done_q.put((done, result, error))
        threading.Thread(target=target, daemon=True).start()

    # ---- build database
    def _build_db(self) -> None:
        sales, zemp = self.var_sales.get().strip(), self.var_zemp.get().strip()
        db = Path(self.var_db.get().strip() or config.DB_PATH)
        if not sales and not zemp:
            messagebox.showinfo("Build database", "Choose the sales Excel and/or the hierarchy Excel first.")
            return
        if (not sales or not zemp) and not db.exists():
            messagebox.showwarning("Build database", "There is no database yet, so both Excel files are needed.")
            return
        if db.exists() and not messagebox.askyesno(
                "Replace data?", f"This will replace the data in\n{db}\n\nThe old file is kept as {db.name}.bak. Continue?"):
            return
        from tva import xl2db
        self._set_busy(True, "Building database…")
        self.q.put(f"\n── Build database · {datetime.now():%d/%m/%Y %H:%M:%S} ──\n")

        def work():
            return xl2db.build_database(Path(sales) if sales else None, Path(zemp) if zemp else None, db,
                                        log=lambda m: print(m))

        def done(summary, error):
            self._set_busy(False)
            if error is not None:
                self.q.put(f"✗ {error}\n")
                self.var_status.set("Database build failed")
                messagebox.showerror("Could not build the database", str(error))
                return
            self.q.put(f"✓ {summary.sales_rows:,} sales rows, {summary.zemp_rows:,} hierarchy rows, "
                       f"latest month {summary.latest_month}\n")
            for note in summary.notes:
                self.q.put(f"  note: {note}\n")
            if summary.backup:
                self.q.put(f"  previous database saved as {summary.backup.name}\n")
            self.var_status.set("Database updated")
            self._refresh_db_info()
            self._save_settings()

        self._run_in_thread(work, done)

    # ---- generate reports
    def _common_args(self) -> list:
        args = ["--db", self.var_db.get().strip(), "--out", self.var_out.get().strip()]
        employees = [e for e in re.split(r"[,\s;]+", self.var_emp.get()) if e]
        if employees:
            for e in employees:
                args += ["-e", e]
        else:
            levels = [str(l) for l, v in self.var_levels.items() if v.get()]
            args += ["--levels", *levels]
            if self.var_all_div.get():
                args.append("--all-divisions")
            else:
                divs = re.findall(r"\d+", self.var_div.get())
                if divs:
                    args += ["--divisions", *divs]
            if self.var_no_team.get():
                args.append("--include-no-team")
        month = MONTH_CHOICES.index(self.var_month.get()) if self.var_month.get() in MONTH_CHOICES else 0
        if month:
            args += ["--upto", str(month)]
        return args

    def _generate(self) -> None:
        want_html, want_mobile, want_pdf = (self.var_fmt_html.get(), self.var_fmt_mobile.get(),
                                            self.var_fmt_pdf.get())
        if not (want_html or want_mobile or want_pdf):
            messagebox.showinfo("Generate", "Choose at least one file type (HTML desktop, HTML mobile or PDF).")
            return
        if not Path(self.var_db.get()).exists():
            messagebox.showwarning("Generate", "The database file does not exist yet. Build it from the Excel files first.")
            return
        if not self.var_emp.get().strip() and not any(v.get() for v in self.var_levels.values()):
            messagebox.showinfo("Generate", "Tick at least one level, or type employee IDs.")
            return
        if not self.var_all_div.get() and not self.var_emp.get().strip() and not re.findall(r"\d+", self.var_div.get()):
            messagebox.showinfo("Generate", "Type the division numbers (for example 1, 2, 4) or tick “All divisions”.")
            return

        import generate_reports
        generate_pdf = None
        if want_pdf:
            try:
                import generate_pdf
            except ImportError:
                messagebox.showerror("PDF needs one more package",
                                     "PDF output needs the 'reportlab' package.\n\nOpen a terminal and run:\n    pip install reportlab")
                return

        common = self._common_args()
        orient = self.var_orient.get()                    # read Tk variables here, never inside the worker thread
        pdf_extra = ["--portrait"] if orient == "portrait" else []
        formats = [f for f, on in (("html", want_html), ("mobile", want_mobile)) if on]

        def work():
            codes = {}
            t0 = time.time()
            if formats:
                print(f"\n── HTML ({' + '.join(formats)}) · {datetime.now():%d/%m/%Y %H:%M:%S} ──")
                codes["html"] = generate_reports.main(common + ["--format", *formats])
            if want_pdf:
                print(f"\n── PDF ({orient}) · {datetime.now():%d/%m/%Y %H:%M:%S} ──")
                codes["pdf"] = generate_pdf.main(common + pdf_extra)
            print(f"\nFinished in {time.time() - t0:.1f}s")
            return codes

        def done(codes, error):
            self._set_busy(False)
            if error is not None:
                self.q.put(f"✗ {error}\n")
                self.var_status.set("Failed")
                messagebox.showerror("Something went wrong", str(error))
                return
            ok = all(c == 0 for c in codes.values())
            self.var_status.set("Finished - open the output folder to see the files" if ok
                                else "Finished with problems - see the log")
            self._save_settings()

        self._set_busy(True, "Generating reports…")
        self._run_in_thread(work, done)


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
