# Excel Processor — Modern Python GUI

Desktop app replacing manual Jupyter/pandas cell-by-cell Excel work.
Import a workbook → pick a sheet → apply operations → export the result.

## Run

```bash
pip install -r requirements.txt
python main.py
```

Requires Python 3.10+. Dark mode is the default (CustomTkinter theming).

## Layout

- **Top bar** — Import File, path label, sheet dropdown, Refresh.
- **Source Data View** (blue header) — raw selected sheet, read-only grid.
- **Operations panel** (right) — operation dropdown, auto-built params, Apply.
- **Result View** (green header) — output of the last successful operation.
- **Bottom bar** — Export Result + timestamped status log (full tracebacks go to `app.log`).

## Add a new operation (registry pattern)

1. Write a function in `operations.py` with signature
   `def op_name(df: pd.DataFrame, **params) -> pd.DataFrame`.
2. Register it with `@register("Display Name", "Description", [ParamSpec(...)])`.
3. It appears automatically in the Operations dropdown — no UI edits needed.

## Division-wise logic (edit rules here)

Each division has its own file — edit it to change that division's behavior:

- `divisions/pharma.py` — Pharma (01)
- `divisions/ag.py` — AG (02)
- `divisions/onco.py` — Onco (03)
- `divisions/ophtha.py` — Ophtha (04)
- `divisions/dnr.py` — DNR (11)
- `divisions/ah.py` — AH (09)

Each file holds `DEPOTHEAD_COLUMNS`, `EMPLOYEE_COLS` / `EMPLOYEE_SUFFIX`,
and `MIOTARGET_VARIANTS`. `operations.py` combines them automatically.

`ParamSpec` kinds: `column`, `columns`, `divisions`, `date`, `operator`,
`select`, `text`, `number`, `expression`.

## Project structure

```text
main.py            app entry point + window orchestration
data_loader.py     sheet-name / sheet-load logic (pandas + openpyxl)
operations.py      operation registry + shared engines (combines divisions/)
divisions/         one logic file per division (pharma, ag, onco, ...)
ui/date_picker.py  popup calendar for date params
ui/error_dialog.py validation-error popup with Copy button
ui/data_table.py   read-only Treeview grid card
ui/ops_panel.py    dynamic params panel
ui/log_panel.py    timestamped status log
```
