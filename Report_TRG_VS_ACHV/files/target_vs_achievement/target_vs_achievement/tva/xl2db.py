"""
Excel (.xlsx / .xlsm) or CSV  ->  SQLite database used by the report generators.

Two source files, two tables:

  sales file -> table `sales`   one row per employee, monthly Target / Sales / Ach %
  zemp file  -> table `zemp`    the organisation tree (one row per position)

The first row of each sheet must be the column headings.  Headings are matched
loosely (case, spaces and punctuation are ignored), so "AM/SAM" and "AM/ SAM" are
the same column.  Extra columns are kept as they are.  If a heading appears twice,
the second one becomes "<name>.1", the third "<name>.2" ... (this is what pandas
does, and it is how the existing data.db was built).

Columns that may be left out of the sales sheet and are then calculated:
    <Mon>_Ach  = Sol / Tar * 100,   Total_Tar, Total_Sol, Total_Ach,   year (= this year)

Command line:
    python -m tva.xl2db --sales sales.xlsx --zemp zemp.xlsx [--db data/data.db]
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import config as default_config

from .models import MONTHS

Log = Callable[[str], None]


class ImportProblem(Exception):
    """A problem with the Excel file that the user can fix (shown as plain text)."""


@dataclass
class ImportSummary:
    db_path: Path
    sales_rows: Optional[int] = None
    zemp_rows: Optional[int] = None
    latest_month: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    backup: Optional[Path] = None


# --------------------------------------------------------------------------
# column naming
# --------------------------------------------------------------------------
def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def sales_columns() -> Tuple[List[str], Dict[str, str]]:
    """(canonical column list, {loose key -> canonical name}) for the sales table."""
    cols = ["emp_id", "emp_name", "depot_code", "depot_name", "emp_terri",
            "division", "hieararchy", "year"]
    for m in MONTHS:
        cols += [f"{m}_Tar", f"{m}_Sol", f"{m}_Ach"]
    cols += ["Total_Tar", "Total_Sol", "Total_Ach"]
    lookup = {_key(c): c for c in cols}
    lookup.update({"hierarchy": "hieararchy", "employeeid": "emp_id", "employeename": "emp_name",
                   "territory": "emp_terri", "year": "year"})
    suffixes = {"tar": "Tar", "target": "Tar", "sol": "Sol", "sal": "Sol", "sale": "Sol",
                "sales": "Sol", "ach": "Ach", "achv": "Ach", "achievement": "Ach"}
    for m in MONTHS + ["Total"]:
        for alias, canon in suffixes.items():
            lookup.setdefault(_key(m + alias), f"{m}_{canon}")
    return cols, lookup


def zemp_columns() -> Dict[str, str]:
    """{loose key -> canonical name} for the zemp columns the generators read."""
    canon = ["Employee ID", "Hierarchy Level", "Division"]
    for _label, zcols in default_config.LEVELS.values():
        canon += list(zcols)
    return {_key(c): c for c in canon}


def _dedupe(headers: Sequence[str]) -> List[str]:
    """pandas-style: second 'X' -> 'X.1', third -> 'X.2'; blank headings -> 'Unnamed: n'."""
    seen: Dict[str, int] = {}
    out = []
    for i, h in enumerate(headers):
        h = str(h).strip() if h is not None else ""
        if not h:
            h = f"Unnamed: {i}"
        n = seen.get(h, 0)
        seen[h] = n + 1
        out.append(h if n == 0 else f"{h}.{n}")
    return out


# --------------------------------------------------------------------------
# reading files
# --------------------------------------------------------------------------
def _clean(v):
    if isinstance(v, str):
        v = v.strip()
        return v if v != "" else None
    return v


def read_table(path: Path, sheet_hint: str = "") -> Tuple[List[str], List[List], str]:
    """(headings, rows, sheet name) from the first suitable sheet of an Excel/CSV file."""
    path = Path(path)
    if not path.exists():
        raise ImportProblem(f"File not found: {path}")
    ext = path.suffix.lower()

    if ext == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as fh:
            raw = [list(r) for r in csv.reader(fh)]
        sheet = path.name
        rows_iter = ([_to_number(c) for c in r] for r in raw)
    elif ext in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:                                     # pragma: no cover
            raise ImportProblem("The 'openpyxl' package is needed to read Excel files:  pip install openpyxl") from exc
        try:
            wb = load_workbook(str(path), read_only=True, data_only=True)
        except Exception as exc:
            raise ImportProblem(f"Could not open {path.name}: {exc}") from exc
        names = [s for s in wb.sheetnames if wb[s].sheet_state == "visible"] or wb.sheetnames
        pick = next((n for n in names if sheet_hint and sheet_hint in _key(n)), names[0])
        sheet = pick
        rows_iter = wb[pick].iter_rows(values_only=True)
    elif ext == ".xls":
        raise ImportProblem(f"{path.name} is an old .xls file. Open it in Excel and use "
                            f"Save As -> Excel Workbook (.xlsx), then select that file.")
    else:
        raise ImportProblem(f"Unsupported file type '{ext}'. Use .xlsx or .csv")

    headers: Optional[List[str]] = None
    rows: List[List] = []
    for r in rows_iter:
        r = [_clean(c) for c in r]
        if all(c is None for c in r):
            continue
        if headers is None:
            while r and r[-1] is None:          # trailing empty header cells
                r.pop()
            headers = _dedupe(r)
            continue
        r = (r + [None] * len(headers))[:len(headers)]
        rows.append(r)
    if headers is None:
        raise ImportProblem(f"{path.name}: the sheet is empty")
    return headers, rows, sheet


def _to_number(c):
    """CSV cells arrive as text; turn numeric-looking ones into numbers."""
    c = _clean(c)
    if isinstance(c, str):
        try:
            return int(c)
        except ValueError:
            try:
                return float(c)
            except ValueError:
                return c
    return c


# --------------------------------------------------------------------------
# preparing each table
# --------------------------------------------------------------------------
def _rename(headers: List[str], lookup: Dict[str, str], log: Log, who: str) -> List[str]:
    out, renamed = [], []
    used = set()
    for h in headers:
        canon = lookup.get(_key(h))
        # never let two columns end up with the same name
        if canon and canon not in used:
            if canon != h:
                renamed.append(f"'{h}' -> '{canon}'")
            used.add(canon)
            out.append(canon)
        else:
            out.append(h)
    if renamed:
        log(f"  {who}: matched headings: " + ", ".join(renamed[:8]) + (" ..." if len(renamed) > 8 else ""))
    return out


def prepare_sales(headers: List[str], rows: List[List], log: Log) -> Tuple[List[str], List[List]]:
    canon, lookup = sales_columns()
    headers = _rename(headers, lookup, log, "sales")
    have = set(headers)

    needed = ["emp_id", "emp_name", "hieararchy"] + [f"{m}_{k}" for m in MONTHS for k in ("Tar", "Sol")]
    missing = [c for c in needed if c not in have]
    if missing:
        raise ImportProblem("The sales file is missing these columns:\n  " + ", ".join(missing) +
                            "\n\nFound: " + ", ".join(headers[:25]) + (" ..." if len(headers) > 25 else ""))

    idx = {h: i for i, h in enumerate(headers)}

    def num(row, col):
        v = row[idx[col]]
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    extra: List[str] = []
    for m in MONTHS:                                    # columns that can be calculated
        if f"{m}_Ach" not in have:
            extra.append(f"{m}_Ach")
    for c in ("Total_Tar", "Total_Sol", "Total_Ach", "year"):
        if c not in have:
            extra.append(c)
    if extra:
        log("  sales: calculating missing columns: " + ", ".join(extra))
        idx_extra = {c: len(headers) + i for i, c in enumerate(extra)}
        full_idx = {**idx, **idx_extra}
        new_rows = []
        for r in rows:
            r = r + [None] * len(extra)
            for m in MONTHS:
                if f"{m}_Ach" in idx_extra:
                    t, s = num(r, f"{m}_Tar"), num(r, f"{m}_Sol")
                    r[full_idx[f"{m}_Ach"]] = s / t * 100 if t > 0 else 0.0
            tt = sum(num(r, f"{m}_Tar") for m in MONTHS)
            ts = sum(num(r, f"{m}_Sol") for m in MONTHS)
            if "Total_Tar" in idx_extra:
                r[full_idx["Total_Tar"]] = tt
            if "Total_Sol" in idx_extra:
                r[full_idx["Total_Sol"]] = ts
            if "Total_Ach" in idx_extra:
                r[full_idx["Total_Ach"]] = ts / tt * 100 if tt > 0 else 0.0
            if "year" in idx_extra:
                r[full_idx["year"]] = date.today().year
            new_rows.append(r)
        headers, rows = headers + extra, new_rows

    # integer-looking text in numeric id columns -> numbers, so filters like "division in (1,2,4)" work
    idx = {h: i for i, h in enumerate(headers)}
    for col in ("hieararchy", "division", "depot_code", "year"):
        if col in idx:
            for r in rows:
                v = r[idx[col]]
                if isinstance(v, str):
                    try:
                        r[idx[col]] = int(float(v))
                    except ValueError:
                        pass
                elif isinstance(v, float) and v.is_integer():
                    r[idx[col]] = int(v)

    ids = [r[idx["emp_id"]] for r in rows]
    if any(i is None for i in ids):
        raise ImportProblem("The sales file has rows with an empty emp_id.")
    dups = sorted({i for i in ids if ids.count(i) > 1})[:5] if len(set(ids)) != len(ids) else []
    if dups:
        log(f"  ! sales: duplicate emp_id values (later rows win when reports are built): {', '.join(map(str, dups))}")
    return headers, rows


def prepare_zemp(headers: List[str], rows: List[List], log: Log) -> Tuple[List[str], List[List]]:
    headers = _rename(headers, zemp_columns(), log, "zemp")
    have = set(headers)
    if "Employee ID" not in have:
        raise ImportProblem("The hierarchy (zemp) file has no 'Employee ID' column.\n\nFound: " +
                            ", ".join(headers[:25]))
    level_cols = [c for _l, zc in default_config.LEVELS.values() for c in zc if c in have]
    if not level_cols:
        raise ImportProblem("The hierarchy (zemp) file has none of the level columns "
                            "(MIO/ SMIO, AM/ SAM, RSM, DSM, SM, SSM, AGM ...).\n\nFound: " + ", ".join(headers[:25]))
    return headers, rows


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------
def _sql_type(values: List) -> str:
    seen = [v for v in values if v is not None]
    if not seen:
        return "TEXT"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in seen):
        return "INTEGER"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in seen):
        return "REAL"
    return "TEXT"


def _plain(v):
    """SQLite-friendly value (dates become ISO text)."""
    if hasattr(v, "isoformat"):
        return v.isoformat(sep=" ") if hasattr(v, "hour") else v.isoformat()
    if isinstance(v, bool):
        return int(v)
    if not isinstance(v, (int, float, str, type(None))):
        return str(v)
    return v


def _write_table(con: sqlite3.Connection, name: str, headers: List[str], rows: List[List]) -> None:
    types = [_sql_type([r[i] for r in rows]) for i in range(len(headers))]
    # a text column that holds some numbers must be all text, or sorting/joining gets odd
    for i, t in enumerate(types):
        if t == "TEXT":
            for r in rows:
                if isinstance(r[i], (int, float)):
                    r[i] = str(r[i]) if not (isinstance(r[i], float) and r[i].is_integer()) else str(int(r[i]))
    con.execute(f'DROP TABLE IF EXISTS "{name}"')
    con.execute(f'CREATE TABLE "{name}" (' + ", ".join(f'"{h}" {t}' for h, t in zip(headers, types)) + ")")
    con.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" * len(headers))})',
                    ([_plain(v) for v in r] for r in rows))


def build_database(sales_path: Optional[Path], zemp_path: Optional[Path], db_path: Path,
                   log: Log = lambda _m: None, keep_backup: bool = True) -> ImportSummary:
    """
    Create/refresh the database from the Excel files.  Give one or both files; a table
    whose file is not given is kept from the existing database.
    The old database is saved next to it as <name>.bak.
    """
    db_path = Path(db_path)
    if not sales_path and not zemp_path:
        raise ImportProblem("Choose at least one Excel file.")
    if (not sales_path or not zemp_path) and not db_path.exists():
        raise ImportProblem("There is no database yet, so both Excel files are needed "
                            "(sales and hierarchy).")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_name(db_path.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    if db_path.exists() and (not sales_path or not zemp_path):
        shutil.copyfile(db_path, tmp)            # keep the table we are not replacing

    summary = ImportSummary(db_path=db_path)
    con = sqlite3.connect(str(tmp))
    try:
        if sales_path:
            log(f"Reading sales file: {Path(sales_path).name}")
            h, r, sheet = read_table(Path(sales_path), "sales")
            log(f"  sheet '{sheet}': {len(r):,} rows, {len(h)} columns")
            h, r = prepare_sales(h, r, log)
            _write_table(con, "sales", h, r)
            con.execute('CREATE INDEX IF NOT EXISTS idx_sales_emp ON sales(emp_id)')
            summary.sales_rows = len(r)
        if zemp_path:
            log(f"Reading hierarchy file: {Path(zemp_path).name}")
            h, r, sheet = read_table(Path(zemp_path), "zemp")
            log(f"  sheet '{sheet}': {len(r):,} rows, {len(h)} columns")
            h, r = prepare_zemp(h, r, log)
            _write_table(con, "zemp", h, r)
            con.execute('CREATE INDEX IF NOT EXISTS idx_zemp_emp ON zemp("Employee ID")')
            summary.zemp_rows = len(r)
        con.commit()

        # quick look at what was loaded
        try:
            summary.sales_rows = con.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
            summary.zemp_rows = con.execute("SELECT COUNT(*) FROM zemp").fetchone()[0]
            for m in reversed(MONTHS):
                if con.execute(f'SELECT 1 FROM sales WHERE "{m}_Sol" > 0 LIMIT 1').fetchone():
                    summary.latest_month = m
                    break
            ids = {x[0] for x in con.execute('SELECT DISTINCT "Employee ID" FROM zemp')}
            missing = con.execute("SELECT emp_id FROM sales").fetchall()
            n_missing = sum(1 for (e,) in missing if e not in ids)
            if n_missing:
                summary.notes.append(f"{n_missing:,} employees in sales are not in the hierarchy file "
                                     f"(they cannot show a team).")
        except sqlite3.Error:
            pass
    except Exception:
        con.close()
        if tmp.exists():
            tmp.unlink()
        raise
    con.close()

    if db_path.exists() and keep_backup:
        summary.backup = db_path.with_name(db_path.name + ".bak")
        shutil.copyfile(db_path, summary.backup)
    os.replace(tmp, db_path)
    log(f"Database written: {db_path}")
    return summary


# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build data.db from the sales and hierarchy Excel files")
    ap.add_argument("--sales", metavar="FILE", help="Excel/CSV with the sales table")
    ap.add_argument("--zemp", metavar="FILE", help="Excel/CSV with the hierarchy (zemp) table")
    ap.add_argument("--db", metavar="FILE", default=str(default_config.DB_PATH))
    args = ap.parse_args(argv)
    try:
        s = build_database(args.sales, args.zemp, Path(args.db), log=print)
    except ImportProblem as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"sales rows: {s.sales_rows:,}   zemp rows: {s.zemp_rows:,}   latest month with sales: {s.latest_month}")
    for n in s.notes:
        print("  note:", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
