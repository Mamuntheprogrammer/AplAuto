"""Plain data containers shared by the rest of the package."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


@dataclass(frozen=True)
class Month:
    """One month of one employee.  Values are in Lac tk."""
    target: float
    sales: float
    ach: Optional[float]          # percent; None when there was no target

    @property
    def has_data(self) -> bool:
        return self.target > 0 or self.sales > 0


@dataclass
class Person:
    """One row of the `sales` table."""
    emp_id: str
    name: str
    depot_code: Optional[int]
    depot_name: str
    territory: str
    division: Optional[int]
    level: int                     # sales.hieararchy
    year: Optional[int]
    months: List[Month] = field(default_factory=list)   # always 12 items
    total_target: float = 0.0
    total_sales: float = 0.0
    total_ach: Optional[float] = None


@dataclass
class Quarter:
    name: str                      # "Q1"
    month_idx: List[int]           # months (0-based) that have data
    target: float
    sales: float
    ach: Optional[float]
    partial: bool                  # fewer than 3 months of data
    span: str                      # "Jan–Mar"
    delta: Optional[float] = None  # percentage points vs previous quarter
    current: bool = False          # the quarter that contains the latest month with data
    cls: str = "none"              # colour band, filled in by the renderer
