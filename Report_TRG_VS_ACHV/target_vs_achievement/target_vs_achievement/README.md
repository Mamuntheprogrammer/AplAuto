# Target vs Achievement – report generator

Builds one self-contained HTML report per manager from the SQLite file
`data/data.db`. It replaces `Target_vs_achvment.py` (MySQL, 1,000 lines of
copy-pasted SQL) with a small package where each concern lives in one place.

Each report has: headline figures, a **monthly achievement line chart**
shaded by **quarter**, four **quarter cards**, and one table per level below the
manager (sorted highest Ach % first, searchable, with colour-coded badges).

## Quick start

```bash
pip install -r requirements.txt          # only needs Jinja2
python generate_reports.py               # every employee allowed by config.py
python generate_reports.py -e EM00013923 # just one (open output/EM00013923.html)
```

Output goes to `output/`: `<EmployeeID>.html` for each employee, plus
`index.html` (clickable list of all reports) and `manifest.csv` (same list for Excel
or for your mailer). Each HTML file is standalone – CSS, JS and the chart are
inside it – so you can email or copy it anywhere.

## Command line

| Command | What it does |
|---|---|
| `python generate_reports.py` | all employees allowed by `config.py` |
| `-e EM00013923` (repeatable) | only these employees (ignores level/division filters) |
| `--levels 9 8` | only these hierarchy levels |
| `--divisions 1 2` / `--all-divisions` | filter by `sales.division` |
| `--upto 9` | stop at September instead of auto-detecting the latest month |
| `--include-no-team` | also write managers who have nobody under them |
| `--db FILE`, `--out DIR` | other database / output folder |
| `--list` | show who would get a report, write nothing |
| `--check` | data-quality checks, write nothing |
| `python -m pytest -q` | run the tests |

## Where to change things

| I want to… | Edit |
|---|---|
| change who gets a report (levels, divisions), titles, sort order, colour thresholds, DB path | `config.py` |
| add or rename a hierarchy level | `LEVELS` in `config.py` |
| change colours, fonts, spacing, chart look | `tva/static/report.css` (colours are variables at the top) |
| change page layout / wording / add a section | `tva/templates/report.html` |
| change table columns | `tva/templates/_table.html` (+ `_row` in `tva/render.py` if you need new data) |
| change quarter cards | `tva/templates/_quarters.html`, calculation in `tva/metrics.py` |
| change the chart drawing / scale | `tva/templates/_chart.html`, geometry in `tva/charts.py` |
| change how the team is found | `tva/repository.py` (`load_team_index`) and `tva/team.py` |
| change the search box | `tva/static/report.js` |

## How it works

```
data.db ──repository.py──► Person objects + TeamIndex
                               │
 pipeline.py: pick employees ──┤
                               ▼
        team.py  → which people go in which table
        metrics.py → quarters, best month, colour band
        charts.py → chart geometry
                               ▼
        render.py + templates/ + static/  →  output/<EmployeeID>.html
```

### The hierarchy (`zemp`)
`zemp` is one row per *position*. `Employee ID` is the person in that position and the
columns `DSM`, `RSM`, `AM/ SAM`, `AGM`, … say who that position reports to at each
level. So "everyone under AGM X" is every row where `AGM = X`. This is exactly the
old script's `zemp.Level<n> = <employee>` join. `EM00000000` means a vacant
position and is ignored.

Level numbers come from `sales.hieararchy` (the spelling is the database's):

| 1 | 2 | 4 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|
| MIO/SMIO | AM/SAM | RSM/ASM | DSM | SM | SSM | AGM |

### Calculations
* **Achievement %** is `sales ÷ target × 100`. A month with no target shows "–".
* **Quarter %** is quarter sales ÷ quarter target for months that have data, *not* the
  average of the three monthly percentages. A quarter with fewer than three months of data
  is marked *partial* (or *to date* if it is the current quarter).
* **Latest month** is detected as the last month in which anyone has sales (October now).
  Set `REPORT_UPTO_MONTH` in `config.py` to force it.
* **pts** = percentage points (the difference between two percentages).

## Things the data check found (`python generate_reports.py --check`)

* 1,416 people in `sales` have no row in `zemp` (1,147 MIOs and 269 managers). They
  can't be placed in a tree, so those managers show no team – with the default settings
  213 of them are skipped rather than getting an empty report.
* 100 people in `zemp` have no `sales` row, so they are missing from team tables.
* Targets, totals and achievement % are internally consistent (0 mismatches).

The earlier HTML you sent showed `0.00` sales for April–October; that is **not** the case in
this database, so no workaround is used.

## Common edits, step by step

**Add a level (e.g. SAM = 3).** Add `3: ("SAM", ("SAM",))` to `LEVELS` and, if they should
get reports, add `3` to `REPORT_LEVELS`. Tables appear automatically.

**Add a column to the tables.** In `_table.html` add a `<th>` in the header and a `<td>` in the
row. If the value isn't already on `Person`, add it in `repository.load_sales` and
`models.Person`.

**Change the year / month.** The year comes from `sales.year`. Month: see `--upto`.

**Email the reports.** `output/manifest.csv` has `emp_id, name, level, … file`; join it with your
address list and attach the matching file.
