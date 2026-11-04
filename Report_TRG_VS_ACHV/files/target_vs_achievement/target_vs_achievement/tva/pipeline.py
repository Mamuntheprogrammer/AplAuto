"""
Ties everything together:  database -> who gets a report -> HTML files.

    from tva.pipeline import load_settings, run
    run(load_settings(), only=["EM00013923"])
"""
from __future__ import annotations

import csv
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import config as default_config

from . import metrics, repository, team
from .models import MONTHS, Person
from .render import ReportRenderer


def load_settings(**overrides) -> types.SimpleNamespace:
    """config.py as an object, with optional overrides (None values are ignored)."""
    values = {k: getattr(default_config, k) for k in dir(default_config) if k.isupper()}
    values.update({k.upper(): v for k, v in overrides.items() if v is not None})
    for key in ("DB_PATH", "OUTPUT_DIR"):
        values[key] = Path(values[key])
    return types.SimpleNamespace(**values)


@dataclass
class RunResult:
    written: List[Path] = field(default_factory=list)
    skipped_no_team: List[str] = field(default_factory=list)
    not_found: List[str] = field(default_factory=list)
    last_month: int = -1
    output_dir: Optional[Path] = None


# --------------------------------------------------------------------------
def select_employees(cfg, people: Dict[str, Person], index: repository.TeamIndex,
                     only: Optional[Iterable[str]] = None, result: Optional[RunResult] = None
                     ) -> List[Person]:
    """Employees who get a report, according to the settings (or an explicit list)."""
    if only:
        chosen = []
        for emp_id in only:
            person = people.get(emp_id)
            if person is None:
                if result is not None:
                    result.not_found.append(emp_id)
            else:
                chosen.append(person)
        return chosen

    chosen = []
    for p in people.values():
        if p.level not in cfg.REPORT_LEVELS:
            continue
        if cfg.REPORT_DIVISIONS is not None and p.division not in cfg.REPORT_DIVISIONS:
            continue
        if cfg.SKIP_IF_NO_TEAM and not index.has_team(p.emp_id, p.level):
            if result is not None:
                result.skipped_no_team.append(p.emp_id)
            continue
        chosen.append(p)
    chosen.sort(key=lambda p: (-p.level, p.emp_id))
    return chosen


def run(cfg, only: Optional[Iterable[str]] = None,
        progress: Callable[[str], None] = lambda _m: None) -> RunResult:
    result = RunResult(output_dir=cfg.OUTPUT_DIR)
    conn = repository.connect(cfg.DB_PATH)
    try:
        people = repository.load_sales(conn)
        index = repository.load_team_index(conn, cfg.LEVELS, cfg.VACANT_ID)
    finally:
        conn.close()

    if cfg.REPORT_UPTO_MONTH:
        last_month = int(cfg.REPORT_UPTO_MONTH) - 1
    else:
        last_month = repository.detect_last_month(people.values())
    result.last_month = last_month

    employees = select_employees(cfg, people, index, only, result)
    renderer = ReportRenderer(cfg)
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest: List[Dict] = []
    for n, emp in enumerate(employees, 1):
        tables = team.build_tables(emp, people, index, cfg.LEVELS,
                                   sort_by=cfg.SORT_TEAM_BY, include_own=cfg.SHOW_OWN_TABLE)
        main_file = mobile_file = ""
        if "html" in cfg.OUTPUT_FORMATS:
            path = cfg.OUTPUT_DIR / f"{emp.emp_id}.html"
            path.write_text(renderer.render(emp, tables, last_month, emp.year), encoding="utf-8")
            result.written.append(path)
            main_file = path.name
        if "mobile" in cfg.OUTPUT_FORMATS:
            mpath = cfg.OUTPUT_DIR / f"{emp.emp_id}_mobile.html"
            mpath.write_text(renderer.render_mobile(emp, tables, last_month, emp.year), encoding="utf-8")
            result.written.append(mpath)
            mobile_file = mpath.name
        manifest.append({
            "file": main_file, "mobile_file": mobile_file, "emp_id": emp.emp_id, "name": emp.name,
            "level": cfg.LEVELS.get(emp.level, (str(emp.level),))[0],
            "territory": emp.territory, "depot": emp.depot_name, "division": emp.division,
            "team": team.team_size(tables), "target": emp.total_target,
            "sales": emp.total_sales, "ach": emp.total_ach,
            "cls": metrics.ach_class(emp.total_ach, cfg.ACH_GOOD, cfg.ACH_OK),
        })
        if n % 50 == 0 or n == len(employees):
            progress(f"  {n}/{len(employees)} reports written")

    if manifest and not only:
        _write_manifest(cfg.OUTPUT_DIR / "manifest.csv", manifest)
        month = MONTHS[last_month] if last_month >= 0 else ""
        year = employees[0].year if employees else ""
        index_html = renderer.render_index(sorted(manifest, key=lambda r: (r["level"], r["name"])),
                                           f"Report index – upto {month}, {year}")
        (cfg.OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    return result


def _write_manifest(path: Path, rows: List[Dict]) -> None:
    fields = ["emp_id", "name", "level", "territory", "depot", "division",
              "team", "target", "sales", "ach", "file", "mobile_file"]
    with path.open("w", newline="", encoding="utf-8-sig") as fh:   # utf-8-sig: opens cleanly in Excel
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({**r, **{k: (round(r[k], 2) if isinstance(r[k], float) else r[k]) for k in ("target", "sales", "ach")}})


# --------------------------------------------------------------------------
def check_data(cfg) -> List[str]:
    """Data-quality findings.  Run with:  python generate_reports.py --check"""
    conn = repository.connect(cfg.DB_PATH)
    try:
        people = repository.load_sales(conn)
        index = repository.load_team_index(conn, cfg.LEVELS, cfg.VACANT_ID)
        zemp_ids = {r[0] for r in conn.execute('SELECT DISTINCT "Employee ID" FROM zemp')}
    finally:
        conn.close()

    out: List[str] = []
    out.append(f"sales rows: {len(people)}   latest month with sales: "
               f"{MONTHS[repository.detect_last_month(people.values())]}")

    unknown_levels = sorted({p.level for p in people.values()} - set(cfg.LEVELS))
    if unknown_levels:
        out.append(f"! sales has hierarchy levels not defined in config.LEVELS: {unknown_levels}")

    no_zemp = [p for p in people.values() if p.emp_id not in zemp_ids]
    by_level: Dict[int, int] = {}
    for p in no_zemp:
        by_level[p.level] = by_level.get(p.level, 0) + 1
    out.append(f"! {len(no_zemp)} employees in sales are not in zemp (no position in the tree), "
               f"by level: {dict(sorted(by_level.items()))}")
    missing_managers = [p.emp_id for p in no_zemp if p.level in cfg.REPORT_LEVELS]
    if missing_managers:
        out.append(f"  of those, {len(missing_managers)} are manager levels and cannot show a team")

    sales_missing = sorted(zemp_ids - set(people) - {cfg.VACANT_ID})
    out.append(f"! {len(sales_missing)} zemp employees have no row in sales")

    bad_total = bad_ach = 0
    for p in people.values():
        if abs(sum(m.target for m in p.months) - p.total_target) > 0.01:
            bad_total += 1
        for m in p.months:
            if m.target > 0 and m.ach is not None and abs(m.sales / m.target * 100 - m.ach) > 0.05:
                bad_ach += 1
    out.append(f"Total_Tar differs from the sum of months: {bad_total} rows")
    out.append(f"<Mon>_Ach differs from Sol/Tar: {bad_ach} month-cells")
    return out
