"""Excel / CSV loading helpers.

Isolates all pandas file I/O so the UI never touches
openpyxl / xlrd directly.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

SUPPORTED_EXTS = {".xlsx", ".xls", ".csv"}
MAX_PREVIEW_ROWS = 5000


class DataLoadError(Exception):
    """User-friendly load failure (shown in the status log)."""


def is_supported(path: str | Path) -> bool:
    """Return True if the file extension is supported."""
    return Path(path).suffix.lower() in SUPPORTED_EXTS


def _cell_blank(value: object) -> bool:
    """True for NaN / None / blank strings."""
    return pd.isna(value) or str(value).strip() == ""  # type: ignore[arg-type]


def _first_nonblank_as_header(raw: pd.DataFrame) -> pd.DataFrame:
    """Use the first non-blank row as header (skips leading empty rows).

    Handles files whose data starts at row 2+ or below title rows.
    """
    first: int | None = None
    for i in range(len(raw)):
        if not all(_cell_blank(v) for v in raw.iloc[i]):
            first = i
            break
    if first is None:
        raise DataLoadError("Sheet is empty (no data rows).")
    header = ["" if pd.isna(v) else str(v).strip() for v in raw.iloc[first]]  # type: ignore[arg-type]
    seen: dict[str, int] = {}
    names: list[str] = []
    for i, h in enumerate(header):  # de-duplicate / name blank headers
        key = h or f"COL_{i}"
        if key in seen:
            seen[key] += 1
            key = f"{key}_{seen[key]}"
        else:
            seen[key] = 0
        names.append(key)
    body = raw.iloc[first + 1:].copy()
    body.columns = names
    keep = [
        c for c in body.columns
        if not (c.startswith("COL_") and body[c].apply(_cell_blank).all())
    ]
    return body[keep]
    """Return True if the file extension is supported."""
    return Path(path).suffix.lower() in SUPPORTED_EXTS


def get_sheet_names(path: str | Path) -> list[str]:
    """Return sheet names for an Excel file, or ["Data"] for CSVs.

    Raises:
        DataLoadError: on unsupported format / unreadable file / no sheets.
    """
    path = Path(path)
    if not path.exists():
        raise DataLoadError(f"File not found: {path}")
    if not is_supported(path):
        raise DataLoadError(
            f"Unsupported format '{path.suffix}'. Use .xlsx, .xls or .csv."
        )
    try:
        if path.suffix.lower() == ".csv":
            return ["Data"]
        xls = pd.ExcelFile(path, engine=None)
        names = xls.sheet_names
        if not names:
            raise DataLoadError("Workbook contains no sheets.")
        return names
    except DataLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 - friendly message, traceback logged by caller
        raise DataLoadError(f"Could not read workbook: {exc}") from exc


def load_sheet(path: str | Path, sheet: str | int | None = 0) -> pd.DataFrame:
    """Load one sheet (or CSV) into a DataFrame.

    Raises:
        DataLoadError: if the sheet is missing / empty / unreadable.
    """
    path = Path(path)
    try:
        if path.suffix.lower() == ".csv":
            raw = pd.read_csv(path, header=None)
        else:
            raw = pd.read_excel(
                path, sheet_name=sheet if sheet != "Data" else 0, header=None
            )
            if isinstance(raw, dict):  # defensive: sheet_name=None returns dict
                raise DataLoadError("Ambiguous sheet selection.")
    except DataLoadError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DataLoadError(f"Could not load sheet '{sheet}': {exc}") from exc

    try:
        df = _first_nonblank_as_header(raw)
    except DataLoadError:
        raise DataLoadError(f"Sheet '{sheet}' is empty (no data rows).") from None
    if df.empty:
        raise DataLoadError(f"Sheet '{sheet}' is empty (0 rows).")
    # Flatten MultiIndex columns from merged header rows.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" | ".join(map(str, c)).strip(" |") for c in df.columns]
    df.columns = [str(c) for c in df.columns]
    return df.reset_index(drop=True)


def frame_summary(df: pd.DataFrame) -> str:
    """Compact 'N rows x M cols' summary for info bars / log."""
    return f"{len(df):,} rows, {len(df.columns)} columns"


def dtypes_summary(df: pd.DataFrame) -> str:
    """One-line column: dtype summary for tooltips / info bar."""
    return "  |  ".join(f"{c} ({str(t)})" for c, t in df.dtypes.items())
