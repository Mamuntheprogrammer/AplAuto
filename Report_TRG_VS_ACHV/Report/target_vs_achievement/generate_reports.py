#!/usr/bin/env python3
"""
Generate the Target vs Achievement HTML report for every employee.

    python generate_reports.py                       all employees allowed by config.py
    python generate_reports.py -e EM00013923         one (or more) specific employees
    python generate_reports.py --levels 9 8          only these hierarchy levels
    python generate_reports.py --divisions 1 2       only these divisions
    python generate_reports.py --upto 9              report up to September instead of auto
    python generate_reports.py --db other.db --out build/
    python generate_reports.py --check               data-quality checks, writes nothing
    python generate_reports.py --list                show who would get a report, writes nothing
"""
import argparse
import sys
import time

from tva.pipeline import check_data, load_settings, run, select_employees
from tva import repository


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-e", "--employee", action="append", metavar="ID",
                    help="employee ID to generate (repeat for several). Ignores level/division filters.")
    ap.add_argument("--levels", type=int, nargs="+", metavar="N", help="hierarchy levels to report on")
    ap.add_argument("--divisions", type=int, nargs="+", metavar="N", help="divisions to include")
    ap.add_argument("--all-divisions", action="store_true", help="do not filter by division")
    ap.add_argument("--upto", type=int, metavar="MONTH", choices=range(1, 13),
                    help="last month to show, 1-12 (default: detect from data)")
    ap.add_argument("--db", metavar="FILE", help="SQLite database (default: config.DB_PATH)")
    ap.add_argument("--out", metavar="DIR", help="output folder (default: config.OUTPUT_DIR)")
    ap.add_argument("--include-no-team", action="store_true",
                    help="also write reports for managers with nobody under them")
    ap.add_argument("--check", action="store_true", help="run data-quality checks and exit")
    ap.add_argument("--list", action="store_true", help="list the employees that would get a report and exit")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_settings(
        report_levels=tuple(args.levels) if args.levels else None,
        report_divisions=tuple(args.divisions) if args.divisions else None,
        report_upto_month=args.upto,
        db_path=args.db, output_dir=args.out,
        skip_if_no_team=False if args.include_no_team else None,
    )
    if args.all_divisions:
        cfg.REPORT_DIVISIONS = None

    try:
        if args.check:
            print("\n".join(check_data(cfg)))
            return 0

        if args.list:
            conn = repository.connect(cfg.DB_PATH)
            try:
                people = repository.load_sales(conn)
                index = repository.load_team_index(conn, cfg.LEVELS, cfg.VACANT_ID)
            finally:
                conn.close()
            chosen = select_employees(cfg, people, index, args.employee)
            for p in chosen:
                print(f"{p.emp_id}  {cfg.LEVELS.get(p.level, (p.level,))[0]:<9} {p.territory:<9} {p.name}")
            print(f"{len(chosen)} employees")
            return 0

        t0 = time.time()
        print(f"Database : {cfg.DB_PATH}")
        result = run(cfg, only=args.employee, progress=print)
    except repository.DatabaseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for emp_id in result.not_found:
        print(f"  ! {emp_id} was not found in the sales table", file=sys.stderr)
    if result.skipped_no_team:
        print(f"Skipped {len(result.skipped_no_team)} managers with no team in zemp "
              f"(use --include-no-team to write them anyway)")
    print(f"Done: {len(result.written)} reports in {result.output_dir} ({time.time() - t0:.1f}s)")
    return 0 if result.written else 2


if __name__ == "__main__":
    sys.exit(main())
