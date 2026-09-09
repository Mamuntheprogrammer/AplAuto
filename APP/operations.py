"""Operation registry + Z-report operations (ZDEPOTHEAD, ZEMPLOYEE, ...).

Structure: operations.py = registry + shared engines; divisions/*.py = ONE
FILE PER DIVISION holding that division's rules (edit those to change rules).

Pattern to add a new operation:
    1. Write ``def op_my_op(df: pd.DataFrame, **params) -> pd.DataFrame``.
    2. Register it: ``REGISTRY["My Label"] = OpSpec(...)`` with ParamSpecs.
    3. It automatically appears in the Operations dropdown — no UI changes.

ParamSpec types supported by the dynamic params panel:
    "column"     - single column dropdown
    "columns"    - multi-select checkbox list (from DataFrame columns)
    "divisions"  - single-select radio list (from fixed ``options``)
    "date"       - date entry, format DD.MM.YYYY
    "operator"   - dropdown of fixed choices (uses ``options``)
    "select"     - dropdown of fixed choices (uses ``options``)
    "text"       - free text entry
    "number"     - numeric entry (returned as float/int when possible)
    "expression" - free text entry for pandas.eval expressions
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

import pandas as pd

from data_loader import DataLoadError, load_sheet
from divisions import BY_CODE, MODULES

__all__ = [
    "ParamSpec", "OpSpec", "REGISTRY", "list_operations", "get_operation",
    "DIVISIONS", "DIVISION_OPTIONS", "Z_REPORTS",
    "parse_de_date", "period_month_label", "validate_period",
]


# ---------------------------------------------------------------- Registry types
@dataclass
class ParamSpec:
    """Describes one parameter widget for an operation."""

    name: str
    kind: str  # column | columns | operator | select | text | number | expression
    label: str
    options: list[str] = field(default_factory=list)
    default: str = ""
    required: bool = True


@dataclass
class OpSpec:
    """Binds a callable to its display name, description and params."""

    func: Callable[..., pd.DataFrame]
    description: str
    params: list[ParamSpec]


REGISTRY: dict[str, OpSpec] = {}


def register(name: str, description: str, params: list[ParamSpec]):
    """Decorator registering an operation function under ``name``."""

    def deco(func: Callable[..., pd.DataFrame]) -> Callable[..., pd.DataFrame]:
        REGISTRY[name] = OpSpec(func=func, description=description, params=params)
        return func

    return deco


def list_operations() -> list[str]:
    """Ordered operation names for the dropdown."""
    return list(REGISTRY.keys())


def get_operation(name: str) -> OpSpec:
    """Look up an OpSpec by name (KeyError if unknown)."""
    return REGISTRY[name]


# ------------------------------------------------- Z-reports (dummy for now)
# Division registry — combined from divisions/*.py (edit those files, not here).
DIVISIONS: dict[str, str] = {m.NAME: m.CODE for m in MODULES}
DIVISION_OPTIONS: list[str] = [f"{name} ({code})" for name, code in DIVISIONS.items()]
DIVISION_NAMES: dict[str, str] = {code: name for name, code in DIVISIONS.items()}
Z_REPORTS: set[str] = {"ZDEPOTHEAD", "ZEMPLOYEE", "ZMIO_TARGET", "ZSD_MIO_PROD_TRG"}

DATE_FMT = "%d.%m.%Y"


def parse_de_date(value: str) -> datetime:
    """Parse ``DD.MM.YYYY`` (e.g. 01.01.2026); raise friendly ValueError."""
    try:
        return datetime.strptime((value or "").strip(), DATE_FMT)
    except (ValueError, TypeError):
        raise ValueError(f"Bad date {value!r} — use format DD.MM.YYYY (e.g. 01.01.2026).")


def validate_period(start: str, end: str) -> tuple[datetime, datetime]:
    """Validate start/end dates: both set, start <= end, same month & year."""
    d_start = parse_de_date(start)
    d_end = parse_de_date(end)
    if d_start > d_end:
        raise ValueError("Start date must be before (or equal to) end date.")
    if (d_start.year, d_start.month) != (d_end.year, d_end.month):
        raise ValueError("Start and end date must be in the SAME month (e.g. 01.01.2026 – 31.01.2026).")
    return d_start, d_end


def period_month_label(start: str, end: str) -> str:
    """Return e.g. ``JANUARY - 2026`` after validating the period."""
    d_start, _ = validate_period(start, end)
    return f"{calendar.month_name[d_start.month].upper()} - {d_start.year}"


def division_codes(selected: list[str] | str) -> list[str]:
    """Extract codes (01, 02, …) from ``'Name (code)'`` checkbox values."""
    items = [selected] if isinstance(selected, str) else list(selected or [])
    codes: list[str] = []
    for item in items:
        item = str(item).strip()
        if item in DIVISIONS.values():
            codes.append(item)
        elif "(" in item and item.endswith(")"):
            codes.append(item.rsplit("(", 1)[1].rstrip(") ").strip())
        elif item in DIVISIONS:
            codes.append(DIVISIONS[item])
    return codes


def _z_dummy_impl(
    tag: str, df: pd.DataFrame, divisions: list[str] | str,
    start_date: str = "", end_date: str = "", **_: object,
) -> pd.DataFrame:
    """Shared dummy body for the Z-reports: validate + print, return df unchanged."""
    codes = division_codes(divisions)
    if not codes:
        raise ValueError("Select a Division radio option.")
    d_start, d_end = validate_period(start_date, end_date)
    label = f"{calendar.month_name[d_start.month].upper()} - {d_start.year}"
    print(
        f"[{tag}] divisions={', '.join(codes)} "
        f"period={d_start.strftime(DATE_FMT)} - {d_end.strftime(DATE_FMT)} "
        f"({label}) rows={len(df)}"
    )
    return df.copy()


def _z_params() -> list[ParamSpec]:
    """Shared Division + Start/End date params for all Z-reports."""
    today = datetime.now()
    first = today.replace(day=1)
    last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return [
        ParamSpec("divisions", "divisions", "Division", options=DIVISION_OPTIONS),
        ParamSpec("start_date", "date", "Start Date (DD.MM.YYYY)",
                  default=first.strftime(DATE_FMT)),
        ParamSpec("end_date", "date", "End Date (DD.MM.YYYY)",
                  default=last.strftime(DATE_FMT)),
    ]


@register("ZDEPOTHEAD", "Depot Head template — clean, validate, build template (all divisions).", _z_params())
def op_zdepothead(
    df: pd.DataFrame, divisions: list[str] | str = "",
    start_date: str = "", end_date: str = "", **_: object,
) -> pd.DataFrame:
    """ZDEPOTHEAD: same cleaning/validation/template for every division."""
    codes = division_codes(divisions)
    if not codes:
        raise ValueError("Select a Division radio option.")
    validate_period(start_date, end_date)
    code = codes[0]
    name = DIVISION_NAMES.get(code, code)
    return _zdepothead_template(df, start_date.strip(), end_date.strip(), code, name)


# === EDIT HERE: per-division source columns live in divisions/<name>.py ===
# (DEPOTHEAD_COLUMNS in each file). Combined here automatically.
ZDEPOTHEAD_COLUMNS: dict[str, list[str]] = {
    m.CODE: list(m.DEPOTHEAD_COLUMNS) for m in MODULES
}


def _norm_col(name: str) -> str:
    """Normalize a column name for flexible matching (case/punct/space-insensitive)."""
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def _resolve_columns(df: pd.DataFrame, required: list[str]) -> dict[str, str]:
    """Map logical names to actual columns: exact normalized match, then fuzzy.

    Fuzzy fallback covers variants like 'Hierarchy Level' for 'Hierarchy'.
    """
    actuals = [str(c) for c in df.columns]
    norms = {_norm_col(c): c for c in actuals}
    resolved: dict[str, str] = {}
    claimed: set[str] = set()
    missing: list[str] = []
    for logical in required:
        hit = norms.get(_norm_col(logical))
        if hit is not None and hit not in claimed:
            resolved[logical] = hit
            claimed.add(hit)
        else:
            missing.append(logical)
    still_missing: list[str] = []
    for logical in missing:
        target = _norm_col(logical)
        hit = next(
            (c for c in actuals
             if c not in claimed and len(_norm_col(c)) >= 3
             and (target in _norm_col(c) or _norm_col(c) in target)),
            None,
        )
        if hit is None:
            still_missing.append(logical)
        else:
            resolved[logical] = hit
            claimed.add(hit)
    if still_missing:
        raise ValueError(
            f"Missing required column(s): {', '.join(still_missing)}. "
            f"Available: {', '.join(actuals)}"
        )
    return resolved


def _is_empty(value: object) -> bool:
    """True for NaN / None / blank strings."""
    return pd.isna(value) or str(value).strip() == ""  # type: ignore[arg-type]


def _to_clean_str(value: object) -> str:
    """Normalize a cell: 1234.0 → '1234', strips whitespace."""
    if pd.isna(value):  # type: ignore[arg-type]
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _promote_header_row(df: pd.DataFrame, pos: int, tag: str) -> pd.DataFrame:
    """Promote data row ``pos`` to header; return only the rows below it."""
    raw = [_to_clean_str(v) or f"COL_{i}" for i, v in enumerate(df.iloc[pos])]
    seen: dict[str, int] = {}
    header: list[str] = []
    for h in raw:  # de-duplicate repeated header names
        if h in seen:
            seen[h] += 1
            header.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            header.append(h)
    work = df.iloc[pos + 1:].copy()
    work.columns = header
    print(f"[{tag}] header row detected at sheet row {pos + 2}")
    return work


def _row_cells(df: pd.DataFrame, pos: int) -> set[str]:
    """Normalized non-blank cell values of one row."""
    return {c for c in (_norm_col(_to_clean_str(v)) for v in df.iloc[pos]) if c}


def _detect_header(
    df: pd.DataFrame, required: list[str], max_scan: int = 50, tag: str = "ZDEPOTHEAD"
) -> pd.DataFrame:
    """Find the header row anywhere in the sheet (title/blank rows above it are OK).

    Pass 1: exact match; pass 2: fuzzy ('Hierarchy Level' matches 'Hierarchy').
    Raises ValueError with diagnostics if none found.
    """
    targets = [_norm_col(r) for r in required]
    limit = min(len(df), max_scan)
    for pos in range(limit):  # exact pass
        if all(t in _row_cells(df, pos) for t in targets):
            return _promote_header_row(df, pos, tag)
    best = (0, -1)  # fuzzy pass: most required names contained in one row
    for pos in range(limit):
        cells = _row_cells(df, pos)
        score = sum(
            1 for t in targets
            if any(len(c) >= 3 and (t in c or c in t) for c in cells)
        )
        if score > best[0]:
            best = (score, pos)
    if best[0] == len(targets):
        return _promote_header_row(df, best[1], tag)
    preview = " | ".join(_to_clean_str(v) for v in list(df.iloc[0])[:8])
    cols_seen = ", ".join(str(c) for c in list(df.columns)[:8])
    raise ValueError(
        f"Could not find a header row with {', '.join(required)} "
        f"(scanned first {limit} rows). "
        f"Columns seen: {cols_seen}. First row: {preview}. Check the sheet layout."
    )


def _zdepothead_template(
    df: pd.DataFrame, start_date: str, end_date: str, div_code: str, div_name: str
) -> pd.DataFrame:
    """Cleaning → validation → Depot Head template for one division."""
    # === EDIT HERE [Operation: ZDEPOTHEAD | Division-specific source columns] ===
    # ``required`` comes from ZDEPOTHEAD_COLUMNS above — edit that dict, not here.
    required = ZDEPOTHEAD_COLUMNS.get(
        div_code, ["Depot Code", "Division", "Hierarchy", "Depot Head"]
    )
    try:
        colmap = _resolve_columns(df, required)
        work = df.copy()
    except ValueError:
        # Headers may sit below title/blank rows — search for them in the data.
        work = _detect_header(df, required)
        colmap = _resolve_columns(work, required)

    # 1. If the first row is entirely empty, delete it.
    if not work.empty and all(_is_empty(v) for v in work.iloc[0]):
        work = work.iloc[1:]

    # 2. Delete any row with empty data in the key columns.
    key_cols = [colmap[r] for r in required]
    mask_empty = work[key_cols].apply(
        lambda row: any(_is_empty(v) for v in row), axis=1
    )
    work = work.loc[~mask_empty]
    if work.empty:
        raise ValueError("No data left after cleaning — every row had empty key fields.")

    # 3. Field validations (collect Excel-ish row numbers: header = row 1).
    bad_code: list[int] = []
    bad_hier: list[int] = []
    bad_head: list[int] = []
    normed: list[tuple[str, str, str]] = []
    for idx, row in work.iterrows():
        excel_row = int(idx) + 2  # type: ignore[arg-type]
        code = _to_clean_str(row[colmap["Depot Code"]])
        hier = _to_clean_str(row[colmap["Hierarchy"]])
        head = _to_clean_str(row[colmap["Depot Head"]])
        if not re.fullmatch(r"\d{4}", code):
            bad_code.append(excel_row)
        if not re.fullmatch(r"\d", hier):
            bad_hier.append(excel_row)
        if not re.fullmatch(r"EM[A-Za-z0-9]{8}", head):
            bad_head.append(excel_row)
        normed.append((code, hier, head))

    def _rows(nums: list[int]) -> str:
        shown = ", ".join(map(str, nums[:10]))
        return shown + ("…" if len(nums) > 10 else "")

    problems: list[str] = []
    if bad_code:
        problems.append(f"Depot Code must be a 4-digit number (rows: {_rows(bad_code)})")
    if bad_hier:
        problems.append(f"Hierarchy must be a single digit (rows: {_rows(bad_hier)})")
    if bad_head:
        problems.append(
            "Depot Head must be 10 alphanumeric chars starting with 'EM' "
            f"(rows: {_rows(bad_head)})"
        )
    if problems:
        raise ValueError("Validation failed: " + "; ".join(problems))

    # === EDIT HERE [Operation: ZDEPOTHEAD | Division-specific template values] ===
    # Output template columns + fixed values. MANDT default below is "300",
    # DIVISION is the selected division's code (01/02/03/04/11/09).
    template = pd.DataFrame({
        "MANDT": "300",
        "BEGDA": start_date,
        "ENDDA": end_date,
        "DEPOT_CODE": [c for c, _, _ in normed],
        "DIVISION": div_code,
        "HIERARCHY_LEVEL": [h for _, h, _ in normed],
        "DEPOT_HEAD": [d for _, _, d in normed],
    })
    print(f"[ZDEPOTHEAD] {div_name} ({div_code}) template built: {len(template)} rows "
          f"({start_date} - {end_date})")
    return template


@register("ZEMPLOYEE", "Employee template — validate hierarchy file, build template.", _z_params())
def op_zemployee(
    df: pd.DataFrame, divisions: list[str] | str = "",
    start_date: str = "", end_date: str = "", **_: object,
) -> pd.DataFrame:
    """ZEMPLOYEE: validate the hierarchy input, build the upload template."""
    codes = division_codes(divisions)
    if not codes:
        raise ValueError("Select a Division radio option.")
    validate_period(start_date, end_date)
    code = codes[0]
    name = DIVISION_NAMES.get(code, code)
    return _zemployee_template(df, start_date.strip(), end_date.strip(), code, name)


# === EDIT HERE: per-division values live in divisions/<name>.py ===
# (EMPLOYEE_COLS / EMPLOYEE_SUFFIX in each file). Combined here automatically.
ZEMPLOYEE_EXPECTED_COLS = {m.CODE: m.EMPLOYEE_COLS for m in MODULES}
ZEMPLOYEE_SUFFIX = {m.CODE: set(m.EMPLOYEE_SUFFIX) for m in MODULES}
# Output LEVEL slots in order, filled sequentially from input pairs starting
# at input col 8. LEVEL9 is intentionally omitted (per template spec).
ZEMPLOYEE_LEVEL_SLOTS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15]


def _to_de_date_str(value: object) -> str:
    """Normalize a cell to DD.MM.YYYY (handles Excel datetime objects + text)."""
    if pd.isna(value):  # type: ignore[arg-type]
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime(DATE_FMT)
    return str(value).strip()


def _zemployee_template(
    df: pd.DataFrame, start_date: str, end_date: str, div_code: str, div_name: str
) -> pd.DataFrame:
    """Validate the hierarchy input, then build the employee upload template."""
    # 0. Resolve the header row (anchor on the headers common to all divisions).
    anchor = ["Division", "Start Date", "End Date"]
    try:
        _resolve_columns(df, anchor)
        work = df.copy()
    except ValueError:
        work = _detect_header(df, anchor, tag="ZEMPLOYEE")

    # Drop trailing junk columns (blank/Unnamed header AND fully empty).
    kept = [
        c for c in work.columns
        if not (
            (str(c).startswith("Unnamed") or str(c).strip() == "" or str(c).startswith("COL_"))
            and work[c].apply(_is_empty).all()
        )
    ]
    work = work[kept]
    expected = ZEMPLOYEE_EXPECTED_COLS.get(div_code, 33)
    if len(work.columns) < expected:
        raise ValueError(
            f"Expected {expected} columns for division {div_name}, "
            f"found {len(work.columns)}."
        )
    cols = list(work.columns)[:expected]
    npairs = (expected - 7) // 2
    pairs = [(cols[7 + 2 * k], cols[8 + 2 * k]) for k in range(npairs)]
    # === FUTURE VALIDATIONS: add more per-row checks inside the loop below. ===
    # NOTE: rows are never deleted or filled here — blank cells stay blank.
    # Only FULLY-empty rows are skipped (not data, not in output).

    bad_emp: list[int] = []      # col1 must be EM + 10 chars
    bad_depot: list[int] = []    # col2 must be 4-digit
    bad_terr: list[int] = []     # col3 must be 7 chars
    bad_hier: list[int] = []     # col4 must be integer 1..12
    bad_suffix: list[int] = []   # col3 last char per division (hier 1/2)
    bad_div: list[int] = []      # col5 must equal the selected division
    bad_start: list[int] = []    # col6 must equal selected start date
    bad_end: list[int] = []      # col7 must equal selected end date
    bad_pair_em: list[str] = []  # level ID cols: non-blank must be EM + 10 chars
    bad_pair_terr: list[str] = []  # level terr cols: non-blank must be 7 chars
    bad_eq_em: list[str] = []    # own-level ID must equal col1
    bad_eq_terr: list[str] = []  # own-level terr must equal col3
    seen_keys: dict[str, int] = {}
    dup_rows: set[int] = []
    kept_rows: list[tuple[str, str, str, str, list[tuple[str, str]]]] = []
    skipped = 0

    for idx, row in work.iterrows():
        r = int(idx) + 2  # type: ignore[arg-type]  # Excel-ish row number
        vals = [_to_clean_str(row[c]) for c in cols]
        if all(v == "" for v in vals):
            skipped += 1
            continue
        v1, v2, v3, v4s, v5 = vals[0], vals[1], vals[2], vals[3], vals[4]
        v6 = _to_de_date_str(row[cols[5]])
        v7 = _to_de_date_str(row[cols[6]])
        pairvals = [(_to_clean_str(row[e]), _to_clean_str(row[t])) for e, t in pairs]

        if not re.fullmatch(r"EM[A-Za-z0-9]{8}", v1):
            bad_emp.append(r)
        if not re.fullmatch(r"\d{4}", v2):
            bad_depot.append(r)
        if len(v3) != 7:
            bad_terr.append(r)
        try:
            hier = int(v4s)
            hier_ok = 1 <= hier <= 15
        except (ValueError, TypeError):
            hier_ok = False
            hier = 0
        if not hier_ok:
            bad_hier.append(r)
        if hier in (1, 2) and len(v3) == 7:
            if v3.strip()[-1].upper() not in ZEMPLOYEE_SUFFIX.get(div_code, set()):
                bad_suffix.append(r)
        # Col5 Division check DISABLED for now — re-enable by uncommenting below.
        # if v5 != div_code and v5.upper() != div_name.upper():
        #     bad_div.append(r)
        if v6 != start_date:
            bad_start.append(r)
        if v7 != end_date:
            bad_end.append(r)
        for k, (em, t) in enumerate(pairvals):
            if em and not re.fullmatch(r"EM[A-Za-z0-9]{8}", em):
                bad_pair_em.append(f"{r}/L{k + 1}")
            if t and len(t) != 7:
                bad_pair_terr.append(f"{r}/L{k + 1}")
        if 1 <= hier <= npairs:
            own_em, own_t = pairvals[hier - 1]
            if own_em != v1:
                bad_eq_em.append(f"{r} (level {hier})")
            if own_t != v3:
                bad_eq_terr.append(f"{r} (level {hier})")

        key = f"{v1}\x1f{v2}\x1f{v3}"
        if key in seen_keys:
            dup_rows.add(seen_keys[key])
            dup_rows.add(r)
        else:
            seen_keys[key] = r
        kept_rows.append((v1, v2, v3, str(hier if hier_ok else v4s), pairvals))

    def _rows(nums: list[int]) -> str:
        shown = ", ".join(map(str, nums[:10]))
        return shown + ("…" if len(nums) > 10 else "")

    def _tagged(items: list[str]) -> str:
        return ", ".join(items[:10]) + ("…" if len(items) > 10 else "")

    issues: list[str] = []
    if bad_emp:
        issues.append(f"Col1 Employee must be EM + 10 chars (rows: {_rows(bad_emp)})")
    if bad_depot:
        issues.append(f"Col2 Depot must be 4-digit (rows: {_rows(bad_depot)})")
    if bad_terr:
        issues.append(f"Col3 Terr must be 7 chars (rows: {_rows(bad_terr)})")
    if bad_hier:
        issues.append(f"Col4 Hierarchy must be 1..15 (rows: {_rows(bad_hier)})")
    if bad_suffix:
        suffixes = "/".join(sorted(ZEMPLOYEE_SUFFIX.get(div_code, set())))
        issues.append(
            f"Col3 must end with {suffixes} for {div_name} when hierarchy is 1/2 "
            f"(rows: {_rows(bad_suffix)})"
        )
    if bad_div:
        issues.append(f"Col5 Division must be {div_code}/{div_name} (rows: {_rows(bad_div)})")
    if bad_start:
        issues.append(f"Col6 Start must be {start_date} (rows: {_rows(bad_start)})")
    if bad_end:
        issues.append(f"Col7 End must be {end_date} (rows: {_rows(bad_end)})")
    if bad_pair_em:
        issues.append(
            "Level ID cols must be EM + 10 chars when filled "
            f"(row/level: {_tagged(bad_pair_em)})"
        )
    if bad_pair_terr:
        issues.append(
            f"Level terr cols must be 7 chars when filled (row/level: {_tagged(bad_pair_terr)})"
        )
    if bad_eq_em:
        issues.append(f"Own-level ID must equal col1 (row: {_tagged(bad_eq_em)})")
    if bad_eq_terr:
        issues.append(f"Own-level terr must equal col3 (row: {_tagged(bad_eq_terr)})")
    if dup_rows:
        issues.append(
            "Col1+Col2+Col3 must be unique "
            f"(duplicate rows: {', '.join(map(str, sorted(dup_rows)[:10]))})"
        )
    if issues:
        raise ValueError(
            f"ZEMPLOYEE validation failed ({div_name}):\n" + "\n".join(f"- {i}" for i in issues)
        )
    if not kept_rows:
        raise ValueError("No data rows found (every row is blank).")

    # Build the output template (pairs mapped sequentially from input col 8).
    out_cols = ["MANDT", "KUNNR", "DEPOT", "TERR_CODE", "DIVISION",
                "BEGDA", "ENDDA", "HIERARCHY_LEVEL"]
    for lv in ZEMPLOYEE_LEVEL_SLOTS:
        out_cols += [f"LEVEL{lv}", f"LEVEL{lv}_TERR"]
    out_rows: list[list[str]] = []
    for v1, v2, v3, vh, pairvals in kept_rows:
        line = ["300", v1, v2, v3, div_code, start_date, end_date, vh]
        for i in range(len(ZEMPLOYEE_LEVEL_SLOTS)):
            if i < len(pairvals):
                line += [pairvals[i][0], pairvals[i][1]]
            else:
                line += ["", ""]
        out_rows.append(line)
    template = pd.DataFrame(out_rows, columns=out_cols)
    print(f"[ZEMPLOYEE] {div_name} ({div_code}) template built: {len(template)} rows "
          f"({start_date} - {end_date}, {skipped} blank rows skipped)")
    return template


def _parse_number(value: object) -> float | None:
    """Parse a target value cell; None when blank/non-numeric."""
    if pd.isna(value):  # type: ignore[arg-type]
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", ""))
    except (ValueError, TypeError):
        return None


@register("ZMIO_TARGET", "MIO target template — validate target file, build template.", _z_params())
def op_zmio_target(
    df: pd.DataFrame, divisions: list[str] | str = "",
    start_date: str = "", end_date: str = "", **_: object,
) -> pd.DataFrame:
    """ZMIO_TARGET: validate the target input, build the upload template."""
    codes = division_codes(divisions)
    if not codes:
        raise ValueError("Select a Division radio option.")
    validate_period(start_date, end_date)
    code = codes[0]
    name = DIVISION_NAMES.get(code, code)
    return _zmio_target_template(df, start_date.strip(), end_date.strip(), code, name)


# === EDIT HERE [Operation: ZMIO_TARGET | Divisions: 01 Pharma (2 variants), ===
# === 02 AG, 03 Onco, 04 Ophtha, 11 DNR, 09 AH] ===
# Positional input layout, 8 columns (header WORDING differs, POSITIONS fixed):
#   col1 MIO/SIO Code | col2 Terr Code | col3 Depot | col4 Division |
#   col5 Start | col6 End | col7 Target Value | col8 Currency.
# Pharma has TWO file variants, auto-detected from the col7 header text.
def _zmio_target_template(
    df: pd.DataFrame, start_date: str, end_date: str, div_code: str, div_name: str
) -> pd.DataFrame:
    """Validate the target input, then build the target upload template."""
    # 0. Resolve the header row (anchor on headers common to all variants).
    anchor = ["Division", "Start Date", "End Date"]
    try:
        _resolve_columns(df, anchor)
        work = df.copy()
    except ValueError:
        work = _detect_header(df, anchor, tag="ZMIO_TARGET")

    kept = [
        c for c in work.columns
        if not (
            (str(c).startswith("Unnamed") or str(c).strip() == "" or str(c).startswith("COL_"))
            and work[c].apply(_is_empty).all()
        )
    ]
    work = work[kept]
    if len(work.columns) < 8:
        raise ValueError(
            f"Expected 8 columns for ZMIO_TARGET ({div_name}), "
            f"found {len(work.columns)}."
        )
    cols = list(work.columns)[:8]

    # Variant from the col7 header (drives the output file name).
    # Variants are defined per division file (MIOTARGET_VARIANTS).
    variant = ""
    h7 = _norm_col(cols[6])
    for label, keywords in getattr(BY_CODE.get(div_code), "MIOTARGET_VARIANTS", {}).items():
        if all(k in h7 for k in keywords):
            variant = label
            break
    if getattr(BY_CODE.get(div_code), "MIOTARGET_VARIANTS", {}) and not variant:
        raise ValueError(
            "Unrecognized target column for "
            f"{div_name}. Found: {cols[6]!r}."
        )
    label = f"{div_name} {variant}".strip()

    # NOTE: every row is validated — blank or foreign rows IN BETWEEN the data
    # are INVALID (reported below), never silently skipped.
    bad_mio: list[int] = []    # col1 must be EM + 10 chars
    bad_terr: list[int] = []   # col2 must be 7 chars
    bad_depot: list[int] = []  # col3 must be 4-digit
    bad_val: list[int] = []    # col7 must be numeric
    parsed: list[tuple[str, str, str, float]] = []
    skipped = 0
    for idx, row in work.iterrows():
        r = int(idx) + 2  # type: ignore[arg-type]  # Excel-ish row number
        mio = _to_clean_str(row[cols[0]])
        terr = _to_clean_str(row[cols[1]])
        depot = _to_clean_str(row[cols[2]])
        # Trailing empty / total rows (first three cols blank) are ignored.
        if mio == "" and terr == "" and depot == "":
            skipped += 1
            continue
        num = _parse_number(row[cols[6]])
        if not re.fullmatch(r"EM[A-Za-z0-9]{8}", mio):
            bad_mio.append(r)
        if len(terr) != 7:
            bad_terr.append(r)
        if not re.fullmatch(r"\d{4}", depot):
            bad_depot.append(r)
        if num is None:
            bad_val.append(r)
            num = 0.0
        parsed.append((mio, terr, depot, num))

    def _rows(nums: list[int]) -> str:
        shown = ", ".join(map(str, nums[:10]))
        return shown + ("…" if len(nums) > 10 else "")

    issues: list[str] = []
    if bad_mio:
        issues.append(f"Col1 MIO Code must be EM + 10 chars (rows: {_rows(bad_mio)})")
    if bad_terr:
        issues.append(f"Col2 Terr Code must be 7 chars (rows: {_rows(bad_terr)})")
    if bad_depot:
        issues.append(f"Col3 Depot must be 4-digit (rows: {_rows(bad_depot)})")
    if bad_val:
        issues.append(f"Col7 Target Value must be numeric (rows: {_rows(bad_val)})")
    if issues:
        raise ValueError(
            f"ZMIO_TARGET validation failed ({label}):\n" + "\n".join(f"- {i}" for i in issues)
        )
    if not parsed:
        raise ValueError("No data rows found (every row is blank).")

    template = pd.DataFrame({
        "MANDT": "300",
        "MIO_CODE": [m for m, _, _, _ in parsed],
        "TERR_CODE": [t for _, t, _, _ in parsed],
        "DEPOT": [d for _, _, d, _ in parsed],
        "DIVISION": div_code,
        "BEGDA": start_date,
        "ENDDA": end_date,
        "VALUE": [v for _, _, _, v in parsed],
        "WAERK": "BDT",
    })
    in_sum = round(sum(v for _, _, _, v in parsed), 2)
    out_sum = round(float(template["VALUE"].sum()), 2)
    diff = round(in_sum - out_sum, 2)
    summary = f"Input sum: {in_sum:,.2f} | Output sum: {out_sum:,.2f} | Diff: {diff:,.2f}"
    if skipped:
        summary += f" | {skipped} ignored row(s)"
    print(f"[ZMIO_TARGET] {label} template built: {len(template)} rows "
          f"({start_date} - {end_date}). {summary}")
    template.attrs["variant"] = variant  # picked up for the export file name
    template.attrs["summary"] = summary  # shown in the status log
    return template


@register("ZSD_MIO_PROD_TRG", "MIO product target — mvke/zemp lookups, build template.", _z_params())
def op_zsd_mio_prod_trg(
    df: pd.DataFrame, divisions: list[str] | str = "",
    start_date: str = "", end_date: str = "", input_dir: str = "", **_: object,
) -> pd.DataFrame:
    """ZSD_MIO_PROD_TRG: validate input + reference lookups, build template."""
    codes = division_codes(divisions)
    if not codes:
        raise ValueError("Select a Division radio option.")
    validate_period(start_date, end_date)
    code = codes[0]
    name = DIVISION_NAMES.get(code, code)
    if not input_dir:
        raise ValueError("Could not determine the input file folder.")
    return _zsd_template(df, start_date.strip(), end_date.strip(), code, name, input_dir)


# === EDIT HERE [Operation: ZSD_MIO_PROD_TRG] ===
# Reference + input column requirements. Input is mapped POSITIONALLY
# (col1 Plant | col2 Plant Name | col3 Material | col4 Mat. Desc |
#  col5 Market | col6 Target Qty | col7 Division).
MVKE_FILE = "mvke.xlsx"
ZEMP_FILE = "zemp.xlsx"
MVKE_REQUIRED = ["Material", "Commission Group"]  # PROVG comes from Commission Group
ZEMP_REQUIRED = ["Employee", "Plant", "Industry code 1"]


def _find_ref_file(folder: str, name: str) -> str:
    """Find ``name`` in ``folder`` (exact, else case-insensitive)."""
    from pathlib import Path as _Path

    exact = _Path(folder) / name
    if exact.exists():
        return str(exact)
    for entry in _Path(folder).iterdir():
        if entry.is_file() and entry.name.lower() == name.lower():
            return str(entry)
    raise ValueError(
        f"Reference file '{name}' not found in {folder}. "
        "Place it next to the input file and retry."
    )


def _load_ref(path: str, required: list[str], tag: str) -> tuple[pd.DataFrame, dict[str, str]]:
    """Load a reference workbook (first sheet) + resolve required columns."""
    try:
        ref = load_sheet(path, 0)
    except DataLoadError as exc:
        raise ValueError(f"Could not load {tag} file '{path}': {exc}") from exc
    try:
        colmap = _resolve_columns(ref, required)
    except ValueError as exc:
        raise ValueError(f"{tag} file: {exc}") from exc
    return ref, colmap


def _zsd_template(
    df: pd.DataFrame, start_date: str, end_date: str,
    div_code: str, div_name: str, input_dir: str,
) -> pd.DataFrame:
    """Lookups (mvke/zemp) → validation → product target template."""
    # 0. Resolve the header row (anchor on headers common to all divisions).
    anchor = ["Plant Code", "Material Code", "Division"]
    try:
        _resolve_columns(df, anchor)
        work = df.copy()
    except ValueError:
        work = _detect_header(df, anchor, tag="ZSD_MIO_PROD_TRG")

    kept = [
        c for c in work.columns
        if not (
            (str(c).startswith("Unnamed") or str(c).strip() == "" or str(c).startswith("COL_"))
            and work[c].apply(_is_empty).all()
        )
    ]
    work = work[kept]
    if len(work.columns) < 7:
        raise ValueError(
            f"Expected 7 columns for ZSD_MIO_PROD_TRG ({div_name}), "
            f"found {len(work.columns)}."
        )
    cols = list(work.columns)[:7]

    # 1. Load reference files from the input file's folder.
    mvke, mvke_cols = _load_ref(_find_ref_file(input_dir, MVKE_FILE), MVKE_REQUIRED, "mvke")
    zemp, zemp_cols = _load_ref(_find_ref_file(input_dir, ZEMP_FILE), ZEMP_REQUIRED, "zemp")

    mvke_mat = mvke_cols["Material"]
    mvke_provg = mvke_cols["Commission Group"]
    mat_to_provg: dict[str, str] = {}
    mvke_mats: set[str] = set()
    for _, r in mvke.iterrows():
        m = _to_clean_str(r[mvke_mat])
        if not m or m in mat_to_provg:
            continue
        mat_to_provg[m] = _to_clean_str(r[mvke_provg])
        mvke_mats.add(m)

    zemp_emp = zemp_cols["Employee"]
    zemp_plant = zemp_cols["Plant"]
    zemp_ind = zemp_cols["Industry code 1"]
    key_to_emp: dict[tuple[str, str], str] = {}
    for _, r in zemp.iterrows():
        key = (_to_clean_str(r[zemp_plant]), _to_clean_str(r[zemp_ind]))
        if all(key) and key not in key_to_emp:
            key_to_emp[key] = _to_clean_str(r[zemp_emp])

    # 2. Row validations + lookups (every row validated, none skipped).
    bad_mat: list[int] = []       # material not found in mvke
    bad_emp: list[int] = []       # plant+market combo not found in zemp
    bad_qty: list[int] = []       # target qty not numeric
    input_mats: set[str] = set()
    parsed: list[tuple[str, str, str, str, str, float, str]] = []
    for idx, row in work.iterrows():
        r = int(idx) + 2  # type: ignore[arg-type]  # Excel-ish row number
        plant = _to_clean_str(row[cols[0]])
        mat = _to_clean_str(row[cols[2]])
        desc = _to_clean_str(row[cols[3]])
        market = _to_clean_str(row[cols[4]])
        qty = _parse_number(row[cols[5]])
        input_mats.add(mat) if mat else None
        if mat not in mat_to_provg:
            bad_mat.append(r)
        if (plant, market) not in key_to_emp:
            bad_emp.append(r)
        if qty is None:
            bad_qty.append(r)
            qty = 0.0
        parsed.append((plant, mat, desc, market, key_to_emp.get((plant, market), ""), qty,
                       mat_to_provg.get(mat, "")))

    issues: list[str] = []

    def _rows(nums: list[int]) -> str:
        shown = ", ".join(map(str, nums[:10]))
        return shown + ("…" if len(nums) > 10 else "")

    if bad_mat:
        issues.append(f"Material not found in mvke (rows: {_rows(bad_mat)})")
    if bad_emp:
        issues.append(f"Plant+Market not found in zemp (rows: {_rows(bad_emp)})")
    if bad_qty:
        issues.append(f"Target Quantity must be numeric (rows: {_rows(bad_qty)})")
    # Vice versa: mvke materials missing from the input are also invalid.
    missing_mats = sorted(mvke_mats - {m for m in input_mats if m})
    if missing_mats:
        shown = ", ".join(missing_mats[:10])
        issues.append(
            f"mvke materials missing from input: {shown}"
            + ("…" if len(missing_mats) > 10 else "")
        )
    if issues:
        raise ValueError(
            f"ZSD_MIO_PROD_TRG validation failed ({div_name}):\n"
            + "\n".join(f"- {i}" for i in issues)
        )
    if not parsed:
        raise ValueError("No data rows found (every row is blank).")

    # 3. Build the template — strictly 1 row per input row.
    # === EDIT HERE [Operation: ZSD_MIO_PROD_TRG] ===
    # TERR_CODE defaults to the input Market Code; HIERARCHY_LEVEL is fixed
    # to "1"; TARGET_UOM stays blank. Change the mapping below if needed.
    template = pd.DataFrame({
        "MANDT": "300",
        "KUNNR": [e for _, _, _, _, e, _, _ in parsed],
        "TERR_CODE": [mk for _, _, _, mk, _, _, _ in parsed],
        "WERKS": [p for p, _, _, _, _, _, _ in parsed],
        "DIVISION": div_code,
        "HIERARCHY_LEVEL": "1",
        "PROVG": [g for _, _, _, _, _, _, g in parsed],
        "MATNR": [m for _, m, _, _, _, _, _ in parsed],
        "BEGDA": start_date,
        "ENDDA": end_date,
        "MAKTX": [d for _, _, d, _, _, _, _ in parsed],
        "TARGET_QTY": [q for _, _, _, _, _, q, _ in parsed],
        "TARGET_UOM": "",
    })
    if len(template) != len(work):
        raise ValueError(
            f"Row mismatch: input has {len(work)} rows but template has "
            f"{len(template)}. Aborted."
        )
    summary = f"{len(template)} rows | mvke/zemp lookups OK"
    print(f"[ZSD_MIO_PROD_TRG] {div_name} ({div_code}) template built: {summary} "
          f"({start_date} - {end_date})")
    template.attrs["summary"] = summary  # shown in the status log
    return template


# ---------------- end of operations.
