"""Calculations: quarters, headline figures, colour bands."""
from __future__ import annotations

from typing import List, Optional

from .models import MONTHS, Person, Quarter


def ach_class(ach: Optional[float], good: float, ok: float) -> str:
    """CSS class name for an achievement percentage."""
    if ach is None:
        return "none"
    if ach >= good:
        return "good"
    if ach >= ok:
        return "mid"
    return "low"


def quarters(person: Person, last_month: int) -> List[Quarter]:
    """
    Quarter figures for one person.

    Only months up to `last_month` (0-based) are counted, so the current
    quarter is "to date".  Quarter achievement = sales / target for those
    months, not the average of monthly percentages.
    """
    result: List[Quarter] = []
    prev: Optional[float] = None
    for q in range(4):
        idx = [i for i in range(q * 3, q * 3 + 3)
               if i <= last_month and person.months[i].has_data]
        target = sum(person.months[i].target for i in idx)
        sales = sum(person.months[i].sales for i in idx)
        ach = (sales / target * 100) if target > 0 else None
        span = (f"{MONTHS[idx[0]]}–{MONTHS[idx[-1]]}" if len(idx) > 1
                else (MONTHS[idx[0]] if idx else ""))
        quarter = Quarter(name=f"Q{q + 1}", month_idx=idx, target=target, sales=sales,
                          ach=ach, partial=0 < len(idx) < 3, span=span,
                          current=q * 3 <= last_month < q * 3 + 3,
                          delta=(ach - prev) if (ach is not None and prev is not None) else None)
        if ach is not None:
            prev = ach
        result.append(quarter)
    return result


def best_month(person: Person, last_month: int) -> Optional[int]:
    candidates = [i for i in range(last_month + 1) if person.months[i].ach is not None]
    return max(candidates, key=lambda i: person.months[i].ach) if candidates else None


def first_data_month(person: Person, last_month: int) -> Optional[int]:
    for i in range(last_month + 1):
        if person.months[i].ach is not None:
            return i
    return None
