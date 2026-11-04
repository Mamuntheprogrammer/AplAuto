# Target vs Achievement – report generator

Builds one report per manager from the SQLite file `data/data.db`, as
**HTML (desktop)**, **HTML (mobile)** and/or **PDF (A4)**. A small window (`gui.py`) lets you
load the two Excel files, choose the setup and the output type, and run everything.

## Quick start

```bash
pip install -r requirements.txt
python gui.py                                  # the control panel (recommended)
```
or from a terminal:
```bash
python generate_reports.py                     # HTML desktop, everyone allowed by config.py
python generate_reports.py --format html mobile
python generate_pdf.py                         # PDF, A4 landscape
python -m tva.xl2db --sales sales.xlsx --zemp zemp.xlsx     # Excel -> data/data.db
```
Files go to `output/` (change it in the GUI or `config.py`):
`<ID>.html`, `<ID>_mobile.html`, `<ID>.pdf`, plus `index.html` and `manifest.csv` for HTML runs.

## The control panel (`gui.py`)

* **Clock** – current date and time, top right.
* **1 · Data** – choose the sales Excel and the hierarchy (zemp) Excel, press *Build database from Excel*.
  The old database is kept as `data.db.bak`. If you choose only one Excel file, the other table is kept.
  The line next to the button shows what is in the database now.
* **2 · Report setup** – levels, divisions, “report up to” month, or a list of employee IDs.
  *Reset to config.py defaults* puts the original values back.
* **3 · Output** – HTML desktop, HTML mobile, PDF (landscape or portrait), and the output folder.
  You can tick several; each is written side by side.
* Your last choices are remembered in `gui_settings.json`.

## Versions of the report

| File | For | Notes |
|---|---|---|
| `<ID>.html` | PC | Wide tables with a pinned ID/Name, search box. |
| `<ID>_mobile.html` | Phone | One card per person (big Ach %, 12 mini bars, Target/Sales/Gap); tap *Monthly detail* for a short vertical month list. Level tabs, search, sort and “show more” paging. No pinned columns, no sideways scrolling. |
| `<ID>.pdf` | Print / share | A4 landscape (or `--portrait`). Page 1 = figures, chart, quarters, own months; then one table per level with Ach % per month and quarter. |

## Excel import (`tva/xl2db.py`)

* Reads `.xlsx`/`.xlsm` (or `.csv`); the first row must be the headings; the first sheet is used
  (a sheet whose name contains “sales” / “zemp” is preferred).
* Headings are matched loosely: `AM/SAM` = `AM/ SAM`, `Hierarchy` = `hieararchy`, `Emp ID` = `emp_id`, `Jan_Sal` = `Jan_Sol` …
  The log shows every heading it renamed.
* A repeated heading becomes `name.1`, `name.2` (this is how your current `data.db` was built).
* In the sales file you may leave out `<Mon>_Ach`, `Total_Tar`, `Total_Sol`, `Total_Ach`, `year` – they are calculated.
* Required in sales: `emp_id`, `emp_name`, `hieararchy`, and `<Mon>_Tar` / `<Mon>_Sol` for all 12 months.
  Required in zemp: `Employee ID` and at least one level column. Problems are explained in plain words and nothing is
  half-written.

> **Please check:** `xl2db.py` from your data folder was not uploaded, so this importer was written from the
> *structure of data.db*, not from your script. If your script does anything else (extra calculations, renaming,
> filtering rows, a different sheet layout), send it and the importer can be matched exactly.

## Where to change things

| I want to… | Edit |
|---|---|
| who gets a report, titles, sort, colour thresholds, DB path, default formats | `config.py` |
| add/rename a hierarchy level | `LEVELS` in `config.py` |
| desktop look | `tva/static/report.css`, `tva/templates/report.html`, `_table.html`, `_chart.html`, `_quarters.html` |
| **mobile look / behaviour** | `tva/static/mobile.css`, `mobile.js`, `tva/templates/mobile.html` |
| chart geometry (desktop and phone sizes) | `tva/charts.py` (`DESKTOP`, `MOBILE`) |
| PDF design, columns | `generate_pdf.py` (settings at the top) |
| Excel import rules | `tva/xl2db.py` |
| the window | `gui.py` |
| how the team is found | `tva/repository.py`, `tva/team.py` |

## How it works

```
Excel ─ tva/xl2db.py ─► data/data.db ─ tva/repository.py ─► people + team index
                                                │
            generate_reports.py (HTML) ◄────────┤────────► generate_pdf.py (PDF)
              tva/pipeline.py, render.py,        │            (self-contained)
              templates/, static/                 │
                                gui.py runs all three
```

`zemp` is one row per *position*: `Employee ID` is who sits there and `DSM`, `RSM`, `AM/ SAM`, `AGM` … say who
that position reports to. “Everyone under AGM X” = rows where `AGM = X`. `EM00000000` = vacant.
Levels: 1 MIO/SMIO · 2 AM/SAM · 4 RSM/ASM · 6 DSM · 7 SM · 8 SSM · 9 AGM.

* **Achievement %** = sales ÷ target × 100 (“–” when there is no target).
* **Quarter %** = quarter sales ÷ quarter target for months with data (not an average of monthly %).
* **Latest month** = last month in which anyone has sales; force it with *Report up to* / `--upto`.
* **pts** = percentage points.

## Command line reference

`generate_reports.py` and `generate_pdf.py` share these options: `-e ID` (repeatable), `--levels 9 8`,
`--divisions 1 2`, `--all-divisions`, `--upto 9`, `--include-no-team`, `--db FILE`, `--out DIR`, `--list`.
Extra: `generate_reports.py --format html mobile --check`, `generate_pdf.py --portrait`.
`python -m pytest -q` runs the tests.

## Known data notes (`python generate_reports.py --check`)

1,416 people in `sales` have no row in `zemp` (1,147 MIOs, 269 managers) so they cannot show a team; 100 people in
`zemp` have no `sales` row. Totals and achievement % are internally consistent.
