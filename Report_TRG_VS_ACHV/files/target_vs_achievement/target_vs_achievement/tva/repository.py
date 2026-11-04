"""
Reads the SQLite database.

Two tables are used:

sales  one row per employee: monthly target / sales / achievement.
       Column names follow the pattern  <Mon>_Tar, <Mon>_Sol, <Mon>_Ach  and
       Total_Tar, Total_Sol, Total_Ach.  The hierarchy column is spelled
       `hieararchy` in the database - that spelling is kept on purpose.

zemp   the organisation tree, flattened.  Each row is one *position*:
         "Employee ID"  = the person sitting in that position
         "AGM", "DSM", "RSM", "AM/ SAM", ... = who that position reports to at
                          every level above it.
       So "everybody under AGM X" is every zemp row whose AGM column is X.
       This is the same join the old MySQL script did with `zemp.Level<n> = <id>`.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Set, Tuple

from .models import MONTHS, Month, Person


class DatabaseError(RuntimeError):
    pass


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    if not db_path.exists():
        raise DatabaseError(f"Database not found: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    return {r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def _num(value) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _int_or_none(v):
    try:
        return int(float(v)) if v is not None and str(v).strip() != "" else None
    except (TypeError, ValueError):
        return None


def load_sales(conn: sqlite3.Connection) -> Dict[str, Person]:
    """Return {employee_id: Person} for every row of `sales`."""
    cols = _columns(conn, "sales")
    # depot_code, depot_name, emp_terri, division and year are optional
    needed = {"emp_id", "emp_name", "hieararchy", "Total_Tar", "Total_Sol", "Total_Ach"}
    for m in MONTHS:
        needed |= {f"{m}_Tar", f"{m}_Sol", f"{m}_Ach"}
    missing = sorted(needed - cols)
    if missing:
        raise DatabaseError(f"`sales` table is missing columns: {', '.join(missing)}")

    people: Dict[str, Person] = {}
    for r in conn.execute("SELECT * FROM sales"):
        keys = r.keys()
        opt = lambda col: r[col] if col in keys else None
        months = []
        for m in MONTHS:
            tar, sol = _num(r[f"{m}_Tar"]), _num(r[f"{m}_Sol"])
            ach = _num(r[f"{m}_Ach"]) if tar > 0 else None
            months.append(Month(tar, sol, ach))
        total_tar = _num(r["Total_Tar"])
        people[str(r["emp_id"]).strip()] = Person(
            emp_id=str(r["emp_id"]).strip(),
            name=(r["emp_name"] or "").strip(),
            depot_code=opt("depot_code"),
            depot_name=opt("depot_name") or "",
            territory=opt("emp_terri") or "",
            division=_int_or_none(opt("division")),
            level=int(float(r["hieararchy"])),
            year=_int_or_none(opt("year")),
            months=months,
            total_target=total_tar,
            total_sales=_num(r["Total_Sol"]),
            total_ach=_num(r["Total_Ach"]) if total_tar > 0 else None,
        )
    return people


class TeamIndex:
    """
    Answers "who works under manager M at level L?".

    Built once from `zemp`:  index[(L, M)] = {employee ids sitting in rows
    where manager column of level L equals M}.
    """

    def __init__(self) -> None:
        self._index: Dict[Tuple[int, str], Set[str]] = defaultdict(set)

    def add(self, level: int, manager_id: str, employee_id: str) -> None:
        self._index[(level, manager_id)].add(employee_id)

    def under(self, manager_id: str, manager_level: int) -> Set[str]:
        return self._index.get((manager_level, manager_id), set())

    def has_team(self, manager_id: str, manager_level: int) -> bool:
        # the manager's own row is also in the set, so "team" means more than that
        return len(self.under(manager_id, manager_level) - {manager_id}) > 0


def load_team_index(conn: sqlite3.Connection,
                    levels: Dict[int, Tuple[str, Tuple[str, ...]]],
                    vacant_id: str) -> TeamIndex:
    cols = _columns(conn, "zemp")
    if "Employee ID" not in cols:
        raise DatabaseError("`zemp` table has no 'Employee ID' column")

    # keep only the zemp columns that really exist, so a missing optional
    # column (e.g. SAM) does not stop the run
    usable: Dict[int, Tuple[str, ...]] = {}
    for lvl, (_label, zcols) in levels.items():
        found = tuple(c for c in zcols if c in cols)
        if found:
            usable[lvl] = found

    index = TeamIndex()
    wanted = sorted({c for zc in usable.values() for c in zc} | {"Employee ID"})
    sql = "SELECT " + ", ".join(f'"{c}"' for c in wanted) + " FROM zemp"
    for row in conn.execute(sql):
        emp = row["Employee ID"]
        if not emp or emp == vacant_id:
            continue
        for lvl, zcols in usable.items():
            for c in zcols:
                mgr = row[c]
                if mgr and mgr != vacant_id:
                    index.add(lvl, mgr, emp)
    return index


def detect_last_month(people: Iterable[Person]) -> int:
    """Index (0-11) of the latest month in which anybody has sales; -1 if none."""
    last = -1
    for p in people:
        for i, m in enumerate(p.months):
            if m.sales > 0 and i > last:
                last = i
    return last
