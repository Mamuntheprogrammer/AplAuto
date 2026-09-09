"""Popup calendar date picker (CustomTkinter, no extra dependency).

Used by the dynamic params panel for ``date`` params (DD.MM.YYYY).
Monday-first grid to match the German date format.
"""

from __future__ import annotations

import calendar as calmod
from datetime import date, datetime
from typing import Callable

import customtkinter as ctk

from ui.helpers import center_over

WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
DATE_FMT = "%d.%m.%Y"


def parse_de_date_str(value: str) -> date | None:
    """Parse ``DD.MM.YYYY``; return None when invalid."""
    try:
        return datetime.strptime((value or "").strip(), DATE_FMT).date()
    except (ValueError, TypeError):
        return None


def format_de(day: date) -> str:
    """Format a date as ``DD.MM.YYYY``."""
    return day.strftime(DATE_FMT)


def month_last_day(day: date) -> date:
    """Return the last day of ``day``'s month (e.g. 05.04.2026 → 30.04.2026)."""
    last = calmod.monthrange(day.year, day.month)[1]
    return date(day.year, day.month, last)


class CalendarDialog(ctk.CTkToplevel):
    """Modal month-grid calendar; result is a ``DD.MM.YYYY`` string or None."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        initial: str = "",
        on_select: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("Select date")
        center_over(self, parent, 310, 360)
        self.resizable(False, False)
        self.result: str | None = None
        self._on_select = on_select

        base = parse_de_date_str((initial or "").strip()) or date.today()
        self._year, self._month = base.year, base.month
        self._selected = parse_de_date_str((initial or "").strip())

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=(12, 4))
        ctk.CTkButton(nav, text="◀", width=36, fg_color="#3a3a3a",
                      command=self._prev).pack(side="left")
        self._title = ctk.CTkLabel(nav, text="", font=("Segoe UI", 13, "bold"))
        self._title.pack(side="left", expand=True)
        ctk.CTkButton(nav, text="▶", width=36, fg_color="#3a3a3a",
                      command=self._next).pack(side="right")

        week = ctk.CTkFrame(self, fg_color="transparent")
        week.pack(padx=10)
        for i, wd in enumerate(WEEKDAYS):
            ctk.CTkLabel(week, text=wd, width=36, font=("Segoe UI", 10, "bold"),
                         text_color="gray70").grid(row=0, column=i, padx=1)

        self._grid = ctk.CTkFrame(self, fg_color="transparent")
        self._grid.pack(padx=10, pady=4)

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(pady=8)
        ctk.CTkButton(foot, text="Today", width=100, fg_color="#3a3a3a",
                      command=self._today).pack(side="left", padx=6)
        ctk.CTkButton(foot, text="Cancel", width=100, fg_color="#3a3a3a",
                      command=self._cancel).pack(side="left", padx=6)

        self._render()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    # ------------------------------------------------------------------ public
    @classmethod
    def pick(cls, parent: ctk.CTkBaseClass, initial: str = "") -> str | None:
        """Open modally; return the picked ``DD.MM.YYYY`` string or None."""
        dialog = cls(parent, initial)
        parent.wait_window(dialog)
        return dialog.result

    # ------------------------------------------------------------------ internals
    def _render(self) -> None:
        self._title.configure(text=f"{calmod.month_name[self._month]} {self._year}")
        for child in self._grid.winfo_children():
            child.destroy()
        today = date.today()
        for r, week in enumerate(calmod.monthcalendar(self._year, self._month)):
            for c, day in enumerate(week):
                if day == 0:
                    ctk.CTkLabel(self._grid, text="", width=36).grid(
                        row=r, column=c, padx=1, pady=1
                    )
                    continue
                is_selected = (
                    self._selected is not None
                    and (self._selected.year, self._selected.month, self._selected.day)
                    == (self._year, self._month, day)
                )
                is_today = (today.year, today.month, today.day) == (
                    self._year, self._month, day,
                )
                btn = ctk.CTkButton(
                    self._grid, text=str(day), width=36, height=30,
                    fg_color="#1f6aa5" if is_selected else "transparent",
                    text_color="white" if is_selected else ("#4cc38a" if is_today else None),
                    hover_color="#185a8d" if is_selected else "#3a3a3a",
                    command=lambda d=day: self._choose(d),
                )
                btn.grid(row=r, column=c, padx=1, pady=1)

    def _choose(self, day: int) -> None:
        picked = date(self._year, self._month, day)
        self.result = format_de(picked)
        if self._on_select is not None:
            self._on_select(self.result)
        self.destroy()

    def _prev(self) -> None:
        self._month -= 1
        if self._month < 1:
            self._month, self._year = 12, self._year - 1
        self._render()

    def _next(self) -> None:
        self._month += 1
        if self._month > 12:
            self._month, self._year = 1, self._year + 1
        self._render()

    def _today(self) -> None:
        today = date.today()
        self._year, self._month = today.year, today.month
        self._selected = today
        self._render()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
