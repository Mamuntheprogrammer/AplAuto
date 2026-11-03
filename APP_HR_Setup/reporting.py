"""Reporting workspace core: locate Master-Data files + build Master_File."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from data_loader import DataLoadError, load_sheet

MASTER_DATA_DIR = "Master-Data"

MERGED_KEEP = ["EMPP_CODE", "NET_VALUE", "TARGET_AMOUNT", "TARGET_ACHV"]

MASTER_COLUMNS = [
    "EMPP_CODE", "Empp Name", "Depot", "D Final", "Terr. Code",
    "Division", "Hier lvl", "TARGET_AMOUNT", "NET_VALUE", "TARGET_ACHV", "Month",
]

VACANT_SHEETS = ["Pharma_vacant", "Dnr_Vacant"]

VACANT_COLUMNS = [
    "EMPP_CODE", "Empp Name", "Depot", "D Final", "Terr. Code", "AM_Terr",
    "Division", "Hier lvl", "TARGET_AMOUNT", "NET_VALUE", "TARGET_ACHV",
    "Month", "AM_Empp Name", "AM_Depot", "AM_Name",
]

_VACANT_DIV = {"Pharma_vacant": "01", "Dnr_Vacant": "11"}
_VACANT_SUFFIX = {"Pharma_vacant": "P", "Dnr_Vacant": "D"}


def _norm(name: str) -> str:
    """Normalize column/file text for case/space/punct-insensitive matching."""
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def find_master_data_dir(root: str | Path) -> Path:
    """Return <root>/Master-Data (exact, else case-insensitive fallback)."""
    root = Path(root)
    exact = root / MASTER_DATA_DIR
    if exact.is_dir():
        return exact
    for entry in root.iterdir():
        if entry.is_dir() and entry.name.lower() == MASTER_DATA_DIR.lower():
            return entry
    raise FileNotFoundError(
        f"Folder '{MASTER_DATA_DIR}' not found inside {root}."
    )


def find_reporting_files(master_dir: str | Path) -> dict[str, Path]:
    """Find the two workbooks: name contains 'Marketing Employee' / 'Merged'."""
    master_dir = Path(master_dir)
    files = [p for p in master_dir.iterdir() if p.is_file()]
    marketing = next(
        (p for p in files if "marketingemployee" in _norm(p.stem)), None
    )
    merged = next(
        (p for p in files if "merged" in _norm(p.stem)), None
    )
    missing: list[str] = []
    if marketing is None:
        missing.append('a file with "Marketing Employee" in the name')
    if merged is None:
        missing.append('a file with "Merged" in the name')
    if missing:
        seen = ", ".join(p.name for p in files) or "(empty folder)"
        raise FileNotFoundError(
            f"Master-Data is missing {' and '.join(missing)}. Found: {seen}"
        )
    return {"marketing": marketing, "merged": merged}  # type: ignore[return-value]


def load_reporting_files(root: str | Path) -> dict[str, object]:
    """Locate + load both workbooks (first sheet). Raises on any problem."""
    master_dir = find_master_data_dir(root)
    paths = find_reporting_files(master_dir)
    try:
        marketing_df = load_sheet(paths["marketing"], 0)
    except DataLoadError as exc:
        raise ValueError(f"Could not load Marketing Employee file: {exc}") from exc
    try:
        merged_df = load_sheet(paths["merged"], 0)
    except DataLoadError as exc:
        raise ValueError(f"Could not load Merged file: {exc}") from exc
    return {
        "marketing_path": paths["marketing"],
        "merged_path": paths["merged"],
        "marketing_df": marketing_df,
        "merged_df": merged_df,
    }


def _resolve_any(df: pd.DataFrame, candidates: list[str]) -> str:
    """Resolve the first candidate column name that exists (normalized match)."""
    for logical in candidates:
        try:
            return _resolve(df, logical)
        except ValueError:
            continue
    raise ValueError(
        f"Missing required column (tried: {', '.join(candidates)}). "
        f"Available: {', '.join(map(str, df.columns))}"
    )
def _resolve(df: pd.DataFrame, logical: str) -> str:
    """Map a logical column name to the actual column (normalized match)."""
    norms = {_norm(c): str(c) for c in df.columns}
    hit = norms.get(_norm(logical))
    if hit is not None:
        return hit
    raise ValueError(
        f"Missing required column '{logical}'. Available: {', '.join(map(str, df.columns))}"
    )


def _to_number(value: object) -> float:
    """Parse a numeric cell (handles commas/blanks); non-numeric → 0.0."""
    if pd.isna(value):  # type: ignore[arg-type]
        return 0.0
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _fmt2(value: object) -> str:
    """Format as two-decimal string (e.g. 123 → '123.00')."""
    return f"{_to_number(value):.2f}"


def _clean_str(value: object) -> str:
    if pd.isna(value):  # type: ignore[arg-type]
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def build_master_file(merged_df: pd.DataFrame, marketing_df: pd.DataFrame) -> pd.DataFrame:
    """VLOOKUP merged ↔ Marketing Employee on (EMPP_CODE, TERRITORY_CODE).

    Composite key: merged (EMPP_CODE + TERRITORY_CODE) matched against
    Marketing Employee (Empp Code + Terr. Code). Merged is the base (left
    join); descriptives fill in on match, blank otherwise.
    """
    if merged_df.empty:
        raise ValueError("Merged file is empty.")
    if marketing_df.empty:
        raise ValueError("Marketing Employee file is empty.")

    m_code = _resolve(merged_df, "EMPP_CODE")
    m_terr = _resolve_any(
        merged_df, ["TERRITORY_CODE", "Territory Code", "Territory", "Terr. Code"]
    )
    for col in ("NET_VALUE", "TARGET_AMOUNT", "TARGET_ACHV"):
        _resolve(merged_df, col)
    e_code = _resolve(marketing_df, "Empp Code")
    e_terr = _resolve(marketing_df, "Terr. Code")

    def _pair_key(emp: object, terr: object) -> str:
        return f"{_clean_str(emp).upper()}\x1f{_clean_str(terr).upper()}"

    keep = [_resolve(merged_df, c) for c in MERGED_KEEP]
    merged_small = merged_df[[m_code, m_terr] + [c for c in keep if c not in (m_code, m_terr)]].copy()
    merged_small["_key"] = [
        _pair_key(e, t)
        for e, t in zip(merged_small[m_code], merged_small[m_terr])
    ]
    marketing = marketing_df.copy()
    marketing["_key"] = [
        _pair_key(e, t) for e, t in zip(marketing[e_code], marketing[e_terr])
    ]
    # VLOOKUP semantics: first match per (Empp Code, Terr. Code) pair.
    marketing = marketing.drop_duplicates(subset="_key", keep="first")

    # Descriptive columns expected in Marketing Employee (flexible match).
    want = ["Empp Name", "Depot", "D Final", "Terr. Code", "Division", "Hier lvl", "Month"]
    resolved: dict[str, str | None] = {}
    for col in want:
        try:
            resolved[col] = _resolve(marketing_df, col)
        except ValueError:
            resolved[col] = None

    joined = merged_small.merge(
        marketing[["_key"] + [c for c in resolved.values() if c]],
        on="_key", how="left", indicator=True,
    )
    matched = int((joined["_merge"] == "both").sum())
    joined = joined.drop(columns=["_merge"])

    out = pd.DataFrame()
    out["EMPP_CODE"] = joined[m_code].apply(_clean_str)
    for col in want:
        src = resolved[col]
        out[col] = joined[src].apply(_clean_str) if src else ""
    # Terr. Code is part of the lookup key: fall back to the merged
    # TERRITORY_CODE when the pair has no Marketing Employee match.
    unmatched = out["Terr. Code"] == ""
    if bool(unmatched.any()):
        out.loc[unmatched, "Terr. Code"] = (
            joined.loc[unmatched, m_terr].apply(_clean_str).values
        )
    t_amt = _resolve(merged_df, "TARGET_AMOUNT")
    n_val = _resolve(merged_df, "NET_VALUE")
    t_ach = _resolve(merged_df, "TARGET_ACHV")
    out["TARGET_AMOUNT"] = joined[t_amt].apply(lambda v: f"{_to_number(v) / 100000:.2f}")
    out["NET_VALUE"] = joined[n_val].apply(lambda v: f"{_to_number(v) / 100000:.2f}")
    out["TARGET_ACHV"] = joined[t_ach].apply(_fmt2)
    # Exclusions: drop Depot 1397/1398, Terr. Code containing 999,
    # and EMPP_CODE containing VAC.
    drop_mask = (
        out["Depot"].apply(lambda v: str(v).strip() in ("1397", "1398"))
        | out["Terr. Code"].apply(lambda v: "999" in str(v))
        | out["EMPP_CODE"].apply(lambda v: "VAC" in str(v).upper())
        | out["Terr. Code"].apply(_terr_mid_over_500)
    )
    n_dropped = int(drop_mask.sum())
    out = out.loc[~drop_mask].copy()
    out["D Final"] = out["D Final"].apply(lambda v: str(v)[:35])
    out["_achv_num"] = joined[t_ach].apply(_to_number)
    out = out.sort_values(
        by="_achv_num", ascending=False, kind="mergesort"
    ).drop(columns=["_achv_num"])
    out = out[MASTER_COLUMNS]
    out.attrs["summary"] = (
        f"{len(out):,} rows (merged base) | {matched:,} matched in Marketing Employee"
        + (f" | {n_dropped:,} excluded rows" if n_dropped else "")
    )
    return out.reset_index(drop=True)


def _terr_mid_over_500(terr: object) -> bool:
    """True when the numeric middle of a Terr. Code (e.g. 710 in CH710-D) exceeds 500."""
    match = re.search(r"\d+", str(terr))
    if not match:
        return False
    try:
        return int(match.group(0)) > 500
    except ValueError:
        return False


def _div_code(value: object) -> str:
    """Normalize a Division cell to a 2-digit code ('01', '11')."""
    text = _clean_str(value).upper()
    if not text:
        return ""
    if "PHARMA" in text and "DNR" not in text:
        return "01"
    if "DNR" in text:
        return "11"
    match = re.search(r"\d+", text)
    if match:
        return match.group(0).zfill(2)
    return text


def _hier_int(value: object) -> int | None:
    """Parse Hier lvl to int; None when not numeric."""
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError, AttributeError):
        return None


def _am_terr(terr: str, hier: int | None, suffix: str) -> str:
    """AM_Terr: Hier 1 → first-4 of Terr.Code + '0-P'/'0-D', else Terr.Code."""
    terr = str(terr).strip()
    if hier == 1:
        return f"{terr[:4]}0-{suffix}"
    return terr


def build_vacant_files(
    master_df: pd.DataFrame, marketing_df: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """Filter vacant rows from master + VLOOKUP AM info from Marketing Employee.

    Pharma_vacant: EMPP_CODE = EM00000000, Division 01, Hier 1/2.
    Dnr_Vacant: EMPP_CODE = EM00000000, Division 11, Hier 1/2.
    AM_Terr built from Terr. Code, looked up in Marketing 'Terr. Code' to
    fetch Empp Name / Depot / Name. Returns {sheet_name: dataframe}.
    """
    if master_df.empty:
        raise ValueError("Master file is empty — build Master_File first.")
    if marketing_df.empty:
        raise ValueError("Marketing Employee file is empty — load files first.")

    c_emp = _resolve(master_df, "EMPP_CODE")
    c_div = _resolve(master_df, "Division")
    c_hier = _resolve(master_df, "Hier lvl")
    c_terr = _resolve(master_df, "Terr. Code")

    m_terr = _resolve(marketing_df, "Terr. Code")
    try:
        m_name = _resolve(marketing_df, "Empp Name")
    except ValueError:
        m_name = None
    try:
        m_depot = _resolve(marketing_df, "Depot")
    except ValueError:
        m_depot = None
    try:
        m_plain = _resolve(marketing_df, "Name")
        if m_plain == m_name:
            m_plain = None
    except ValueError:
        m_plain = None

    lookup: dict[str, dict[str, str]] = {}
    for _, row in marketing_df.iterrows():
        key = _clean_str(row[m_terr]).upper()
        if not key or key in lookup:
            continue
        lookup[key] = {
            "name": _clean_str(row[m_name]) if m_name else "",
            "depot": _clean_str(row[m_depot]) if m_depot else "",
            "plain": _clean_str(row[m_plain]) if m_plain else "",
        }

    sheets: dict[str, pd.DataFrame] = {}
    for sheet in VACANT_SHEETS:
        div = _VACANT_DIV[sheet]
        suffix = _VACANT_SUFFIX[sheet]
        rows: list[dict[str, object]] = []
        for _, row in master_df.iterrows():
            if _clean_str(row[c_emp]).upper() != "EM00000000":
                continue
            if _div_code(row[c_div]) != div:
                continue
            hier = _hier_int(row[c_hier])
            if hier not in (1, 2):
                continue
            terr = _clean_str(row[c_terr])
            am_terr = _am_terr(terr, hier, suffix)
            hit = lookup.get(am_terr.upper(), {"name": "", "depot": "", "plain": ""})
            rows.append({
                "EMPP_CODE": _clean_str(row[c_emp]),
                "Empp Name": _clean_str(row[_resolve(master_df, "Empp Name")]),
                "Depot": _clean_str(row[_resolve(master_df, "Depot")]),
                "D Final": row[_resolve(master_df, "D Final")],
                "Terr. Code": terr,
                "AM_Terr": am_terr,
                "Division": _clean_str(row[c_div]),
                "Hier lvl": hier,
                "TARGET_AMOUNT": row[_resolve(master_df, "TARGET_AMOUNT")],
                "NET_VALUE": row[_resolve(master_df, "NET_VALUE")],
                "TARGET_ACHV": row[_resolve(master_df, "TARGET_ACHV")],
                "Month": _clean_str(row[_resolve(master_df, "Month")]),
                "AM_Empp Name": hit["name"],
                "AM_Depot": hit["depot"],
                "AM_Name": hit["plain"],
            })
        sheets[sheet] = pd.DataFrame(rows, columns=VACANT_COLUMNS)
    if all(df.empty for df in sheets.values()):
        raise ValueError(
            "Vacant_File has 0 rows — no master rows with EMPP_CODE=EM00000000, "
            "Division 01/11 and Hier lvl 1/2."
        )
    return sheets


def export_vacant_workbook(sheets: dict[str, pd.DataFrame], path: str | Path) -> int:
    """Write vacant sheets (one per division) to a single Excel workbook."""
    from pathlib import Path as _Path

    path = _Path(path)
    if path.suffix.lower() == ".csv":
        first = next((df for df in sheets.values() if not df.empty), None)
        if first is None:
            raise ValueError("Nothing to export — all vacant sheets are empty.")
        first.to_csv(path, index=False)
    else:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
    return path.stat().st_size
