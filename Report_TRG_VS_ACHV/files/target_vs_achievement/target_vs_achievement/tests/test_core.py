"""Run with:  python -m pytest -q"""
import sqlite3

import pytest

from tva import charts, metrics, repository, team
from tva.models import MONTHS
from tva.pipeline import load_settings, run


def _sales_row(emp, name, level, division, tar, sol):
    """tar / sol: dict {month_index: value}; everything else is 0."""
    row = {"emp_id": emp, "emp_name": name, "depot_code": 1, "depot_name": "D", "emp_terri": "T-" + emp,
           "division": division, "hieararchy": level, "year": 2026,
           "Total_Tar": sum(tar.values()), "Total_Sol": sum(sol.values()),
           "Total_Ach": (sum(sol.values()) / sum(tar.values()) * 100) if tar else 0}
    for i, m in enumerate(MONTHS):
        t, s = tar.get(i, 0), sol.get(i, 0)
        row[f"{m}_Tar"], row[f"{m}_Sol"] = t, s
        row[f"{m}_Ach"] = s / t * 100 if t else 0
    return row


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "t.db"
    con = sqlite3.connect(path)
    cols = ["emp_id", "emp_name", "depot_code", "depot_name", "emp_terri", "division", "hieararchy", "year"]
    for m in MONTHS:
        cols += [f"{m}_Tar", f"{m}_Sol", f"{m}_Ach"]
    cols += ["Total_Tar", "Total_Sol", "Total_Ach"]
    con.execute("CREATE TABLE sales (" + ",".join(f'"{c}"' for c in cols) + ")")
    rows = [
        _sales_row("M1", "Boss", 6, 1, {0: 100, 1: 100, 2: 100}, {0: 80, 1: 90, 2: 100}),
        _sales_row("A1", "Alpha", 2, 1, {0: 50, 1: 50, 2: 50}, {0: 40, 1: 60, 2: 55}),
        _sales_row("A2", "Bravo", 2, 1, {1: 50, 2: 50}, {1: 20, 2: 30}),      # joined in Feb
        _sales_row("O1", "Other", 2, 1, {0: 10}, {0: 10}),                     # not in M1's team
    ]
    for r in rows:
        con.execute("INSERT INTO sales (" + ",".join(f'"{k}"' for k in r) + ") VALUES (" +
                    ",".join("?" * len(r)) + ")", list(r.values()))
    con.execute('CREATE TABLE zemp ("Employee ID", "Hierarchy Level", "AM/ SAM", "DSM")')
    con.executemany("INSERT INTO zemp VALUES (?,?,?,?)", [
        ("A1", 2, "A1", "M1"), ("A2", 2, "A2", "M1"), ("O1", 2, "O1", "ZZ"),
        ("M1", 6, "EM00000000", "M1"), ("EM00000000", 2, "EM00000000", "M1"),   # vacant position
    ])
    con.commit()
    con.close()
    return path


def test_loading_and_none_for_missing_target(db):
    con = repository.connect(db)
    people = repository.load_sales(con)
    assert people["A2"].months[0].ach is None           # no target in Jan
    assert people["A1"].months[1].ach == pytest.approx(120)
    assert repository.detect_last_month(people.values()) == 2


def test_team_only_contains_own_downline(db):
    cfg = load_settings(db_path=db)
    con = repository.connect(db)
    people = repository.load_sales(con)
    index = repository.load_team_index(con, cfg.LEVELS, cfg.VACANT_ID)
    tables = team.build_tables(people["M1"], people, index, cfg.LEVELS, sort_by="ach")
    assert [t.label for t in tables] == ["DSM", "AM/SAM"]
    assert [p.emp_id for p in tables[1].people] == ["A1", "A2"]
    assert "O1" not in {p.emp_id for t in tables for p in t.people}
    assert "EM00000000" not in {p.emp_id for t in tables for p in t.people}


def test_quarter_is_sales_over_target_not_average_of_percentages(db):
    people = repository.load_sales(repository.connect(db))
    q1 = metrics.quarters(people["A2"], last_month=2)[0]
    assert q1.target == 100 and q1.sales == 50 and q1.ach == pytest.approx(50)
    assert q1.partial and q1.current and q1.span == "Feb–Mar"


def test_quarters_after_cutoff_are_empty(db):
    people = repository.load_sales(repository.connect(db))
    qs = metrics.quarters(people["A1"], last_month=2)
    assert qs[1].ach is None and qs[3].ach is None
    assert qs[1].delta is None


def test_chart_splits_line_at_gaps_and_keeps_target_visible(db):
    people = repository.load_sales(repository.connect(db))
    p = people["A1"]
    qs = metrics.quarters(p, 2)
    ch = charts.build_chart(p, qs, 2, 100)
    assert len(ch["points"]) == 3 and len(ch["lines"]) == 1
    assert any(t["is_target"] for t in ch["ticks"])
    assert ch["nodata"] is not None


def test_end_to_end_writes_files(db, tmp_path):
    cfg = load_settings(db_path=db, output_dir=tmp_path / "out", report_levels=(6,),
                        report_divisions=None)
    result = run(cfg)
    assert [p.name for p in result.written] == ["M1.html"]
    html = (tmp_path / "out" / "M1.html").read_text(encoding="utf-8")
    assert "Boss" in html and "Alpha" in html and "Bravo" in html and "Other" not in html
    assert (tmp_path / "out" / "index.html").exists()
    assert (tmp_path / "out" / "manifest.csv").exists()


def test_unknown_employee_is_reported_not_fatal(db, tmp_path):
    cfg = load_settings(db_path=db, output_dir=tmp_path / "out")
    result = run(cfg, only=["NOPE"])
    assert result.not_found == ["NOPE"] and not result.written


# ---------------------------------------------------------------- mobile output
def test_mobile_html_has_cards_not_wide_tables(db, tmp_path):
    cfg = load_settings(db_path=db, output_dir=tmp_path / "out", report_levels=(6,),
                        report_divisions=None, output_formats=("html", "mobile"))
    run(cfg)
    mobile = (tmp_path / "out" / "M1_mobile.html").read_text(encoding="utf-8")
    assert 'class="pc"' in mobile and "Alpha" in mobile and "Bravo" in mobile
    assert "<table class=\"dt\"" not in mobile            # the wide pinned-column table is not used
    assert (tmp_path / "out" / "M1.html").exists()          # desktop version is still written


# ---------------------------------------------------------------- excel import
def _make_xlsx(path, headers, rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_excel_import_matches_loose_headings_and_calculates_missing(tmp_path):
    from tva import xl2db
    sales_headers = ["Emp ID", "emp_name", "Hierarchy"] + [f"{m}_{k}" for m in MONTHS for k in ("Tar", "Sol")]
    row = ["E1", "Eve", 6] + [0] * 24
    row[3], row[4] = 100, 80                 # Jan target / sales
    _make_xlsx(tmp_path / "s.xlsx", sales_headers, [row])
    _make_xlsx(tmp_path / "z.xlsx", ["Employee ID", "DSM", "AM/SAM", "MIO T. Code", "MIO T. Code"],
               [["E1", "E1", "E1", 1, 2]])
    summary = xl2db.build_database(tmp_path / "s.xlsx", tmp_path / "z.xlsx", tmp_path / "x.db")
    assert summary.sales_rows == 1 and summary.latest_month == "Jan"
    con = sqlite3.connect(tmp_path / "x.db")
    assert con.execute("SELECT Jan_Ach, Total_Tar, Total_Ach FROM sales").fetchone() == (80.0, 100.0, 80.0)
    zcols = [r[1] for r in con.execute('PRAGMA table_info(zemp)')]
    assert "AM/ SAM" in zcols and "MIO T. Code.1" in zcols      # canonical name + pandas-style duplicate name


def test_excel_import_reports_missing_columns_in_plain_words(tmp_path):
    from tva import xl2db
    _make_xlsx(tmp_path / "s.xlsx", ["emp_id", "emp_name"], [["E1", "Eve"]])
    _make_xlsx(tmp_path / "z.xlsx", ["Employee ID", "DSM"], [["E1", "E1"]])
    with pytest.raises(xl2db.ImportProblem) as err:
        xl2db.build_database(tmp_path / "s.xlsx", tmp_path / "z.xlsx", tmp_path / "x.db")
    assert "missing these columns" in str(err.value) and "hieararchy" in str(err.value)
    assert not (tmp_path / "x.db").exists()                      # nothing half-written


def test_old_database_is_kept_as_backup(tmp_path):
    from tva import xl2db
    sales_headers = ["emp_id", "emp_name", "hieararchy"] + [f"{m}_{k}" for m in MONTHS for k in ("Tar", "Sol")]
    _make_xlsx(tmp_path / "s.xlsx", sales_headers, [["E1", "Eve", 6] + [0] * 24])
    _make_xlsx(tmp_path / "z.xlsx", ["Employee ID", "DSM"], [["E1", "E1"]])
    xl2db.build_database(tmp_path / "s.xlsx", tmp_path / "z.xlsx", tmp_path / "x.db")
    second = xl2db.build_database(tmp_path / "s.xlsx", None, tmp_path / "x.db")   # only refresh sales
    assert second.backup and second.backup.exists()
    con = sqlite3.connect(tmp_path / "x.db")
    assert con.execute("SELECT COUNT(*) FROM zemp").fetchone()[0] == 1               # zemp kept
