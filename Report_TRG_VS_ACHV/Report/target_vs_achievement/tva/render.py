"""Turns one employee's data into a finished, self-contained HTML file."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import charts, metrics, team
from .models import MONTH_NAMES, MONTHS, Person

PKG_DIR = Path(__file__).resolve().parent


def _money(x) -> str:
    return "–" if x in (None, 0) else f"{x:,.2f}"


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(PKG_DIR / "templates")),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True, lstrip_blocks=True,
    )
    env.filters["money"] = _money
    env.filters["pct"] = lambda x: "–" if x is None else f"{x:.1f}%"
    return env


class ReportRenderer:
    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.env = make_env()
        # CSS / JS are inlined so each report is ONE file you can mail or open anywhere.
        self.css = Markup((PKG_DIR / "static" / "report.css").read_text(encoding="utf-8"))
        self.js = Markup((PKG_DIR / "static" / "report.js").read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    def _row(self, p: Person, last_month: int) -> Dict:
        """One table row: which cells to show and which colour band each falls in."""
        cfg = self.cfg
        cells = []
        for i in range(12):
            m = p.months[i]
            shown = i <= last_month and m.has_data
            cells.append({
                "target": m.target if shown else None,
                "sales": m.sales if shown else None,
                "ach": m.ach if shown else None,
                "cls": metrics.ach_class(m.ach, cfg.ACH_GOOD, cfg.ACH_OK) if shown else "none",
            })
        return {
            "person": p, "cells": cells,
            "total_cls": metrics.ach_class(p.total_ach, cfg.ACH_GOOD, cfg.ACH_OK),
        }

    # ------------------------------------------------------------------
    def render(self, employee: Person, tables: List[team.TeamTable], last_month: int,
               year: Optional[int]) -> str:
        cfg = self.cfg
        quarters = metrics.quarters(employee, last_month)
        for q in quarters:
            q.cls = metrics.ach_class(q.ach, cfg.ACH_GOOD, cfg.ACH_OK)
        chart = charts.build_chart(employee, quarters, last_month, cfg.TARGET_LINE)

        best = metrics.best_month(employee, last_month)
        first = metrics.first_data_month(employee, last_month)
        kpi_trend = None
        if best is not None and first is not None and best != first:
            kpi_trend = employee.months[best].ach - employee.months[first].ach

        view_tables = [{
            "level": t.level, "label": t.label, "own": t.own, "count": len(t.people),
            "rows": [self._row(p, last_month) for p in t.people],
            "anchor": f"t-{t.level}",
        } for t in tables]

        month_name = MONTH_NAMES[last_month] if last_month >= 0 else ""
        title = cfg.TITLE_TEMPLATE.format(month=month_name, year=year or "")

        return self.env.get_template("report.html").render(
            cfg=cfg, css=self.css, js=self.js, months=MONTHS,
            title=title, e=employee,
            level_label=cfg.LEVELS.get(employee.level, (str(employee.level),))[0],
            gap=employee.total_target - employee.total_sales,
            last_month_name=MONTHS[last_month] if last_month >= 0 else "",
            first_month_name=MONTHS[first] if first is not None else "",
            best=best, best_ach=employee.months[best].ach if best is not None else None,
            best_name=MONTHS[best] if best is not None else "",
            kpi_trend=kpi_trend,
            quarters=quarters, chart=chart, tables=view_tables,
            team_total=team.team_size(tables),
            generated=datetime.now().strftime("%d/%m/%Y %I:%M %p"),
        )

    def render_index(self, entries: List[Dict], title: str) -> str:
        return self.env.get_template("index.html").render(
            cfg=self.cfg, css=self.css, js=self.js, entries=entries, title=title,
            generated=datetime.now().strftime("%d/%m/%Y %I:%M %p"))
