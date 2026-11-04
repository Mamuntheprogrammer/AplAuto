#!/usr/bin/env python3
"""
Target vs Achievement - PDF report generator (single file, A4 landscape by default).

One PDF per manager, same design as the HTML report: headline figures, monthly
achievement line chart shaded by quarter, quarter cards, then one table per level
below the manager (highest Ach % first).

Setup (one time):
    pip install reportlab

Usage (put this file next to data/data.db, or pass --db):
    python generate_pdf.py                       every employee allowed by the settings below
    python generate_pdf.py -e EM00013923         one or more specific employees
    python generate_pdf.py --levels 9 8          only these hierarchy levels
    python generate_pdf.py --divisions 1 2       only these divisions  (--all-divisions = no filter)
    python generate_pdf.py --upto 9              last month to show, 1-12 (default: detect from data)
    python generate_pdf.py --portrait            A4 portrait instead of landscape
    python generate_pdf.py --db my.db --out pdfs/
    python generate_pdf.py --list                show who would get a PDF, write nothing

Reads the same SQLite database as the HTML project (tables `sales` and `zemp`).
"""
from __future__ import annotations

import argparse
import math
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.graphics.shapes import Path as SPath
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

# =============================================================================
# SETTINGS - edit here
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent
DB_CANDIDATES = [BASE_DIR / "data" / "data.db", BASE_DIR / "data.db"]
OUTPUT_DIR = BASE_DIR / "output_pdf"

PAGE_SIZE = A4                      # any reportlab page size, e.g. reportlab.lib.pagesizes.LETTER
LANDSCAPE = True                    # --portrait on the command line switches this off

REPORT_LEVELS = (9,)  # hierarchy levels that get a PDF
REPORT_DIVISIONS = (1, 2, 4)        # None = all divisions
SKIP_IF_NO_TEAM = True              # skip managers with nobody under them in zemp
REPORT_UPTO_MONTH = None            # None = latest month with sales; or 1-12

COMPANY_NAME = "Aristopharma ltd."
UNIT_NOTE = "(Figures in Lac tk)"
TITLE_TEMPLATE = "Target vs Achievement upto {month}, {year} (highest achv% wise)"
SHOW_OWN_TABLE = True               # monthly Target/Sales/Ach % of the manager himself, on page 1
SORT_TEAM_BY = "ach"                # "ach", "target", "sales" or "name" (highest first)
ACH_GOOD, ACH_OK = 90, 75           # >= GOOD green, >= OK amber, else red
TARGET_LINE = 100                   # dashed reference line in the chart

# sales.hieararchy number -> (label, zemp column(s) holding the person at that level)
LEVELS = {
    1: ("MIO/SMIO", ("MIO/ SMIO",)),
    2: ("AM/SAM",   ("AM/ SAM", "SAM")),
    4: ("RSM/ASM",  ("RSM", "ASM")),
    6: ("DSM",      ("DSM",)),
    7: ("SM",       ("SM",)),
    8: ("SSM",      ("SSM",)),
    9: ("AGM",      ("AGM",)),
}
VACANT_ID = "EM00000000"

# Colours
NAVY = colors.HexColor("#0E2A47")
NAVY2 = colors.HexColor("#17375B")
BRAND = colors.HexColor("#0B67C2")
AMBER = colors.HexColor("#D9822B")
INK = colors.HexColor("#14263B")
MUTE = colors.HexColor("#5B6B7F")
LINE = colors.HexColor("#E2E8F0")
BAND = colors.HexColor("#F3F6FA")
STRIPE = colors.HexColor("#F8FAFC")
TOTAL_BG = colors.HexColor("#EEF5FD")
PALETTE = {  # class -> (text colour, tint)
    "good": (colors.HexColor("#1E8E5A"), colors.HexColor("#E6F5EE")),
    "mid":  (colors.HexColor("#B7791F"), colors.HexColor("#FBF1DC")),
    "low":  (colors.HexColor("#C2412D"), colors.HexColor("#FBE9E6")),
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]

# =============================================================================
# FONTS
# =============================================================================
FONT, FONT_B = "Helvetica", "Helvetica-Bold"          # fallbacks (always available)


def setup_fonts() -> None:
    """Use Segoe UI (Windows) or a similar TrueType font if one is installed."""
    global FONT, FONT_B
    pairs = [
        ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ]
    for reg, bold in pairs:
        if Path(reg).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("Report", reg))
            pdfmetrics.registerFont(TTFont("Report-Bold", bold))
            pdfmetrics.registerFontFamily("Report", normal="Report", bold="Report-Bold",
                                          italic="Report", boldItalic="Report-Bold")
            FONT, FONT_B = "Report", "Report-Bold"
            return


# =============================================================================
# DATA  (same logic as the HTML project)
# =============================================================================
@dataclass
class Month:
    target: float
    sales: float
    ach: Optional[float]

    @property
    def has_data(self) -> bool:
        return self.target > 0 or self.sales > 0


@dataclass
class Person:
    emp_id: str
    name: str
    depot_name: str
    territory: str
    division: Optional[int]
    level: int
    year: Optional[int]
    months: List[Month] = field(default_factory=list)
    total_target: float = 0.0
    total_sales: float = 0.0
    total_ach: Optional[float] = None


@dataclass
class Quarter:
    name: str
    idx: List[int]
    target: float
    sales: float
    ach: Optional[float]
    partial: bool
    current: bool
    span: str
    delta: Optional[float] = None


def _num(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def load_sales(conn: sqlite3.Connection) -> Dict[str, Person]:
    people: Dict[str, Person] = {}
    for r in conn.execute("SELECT * FROM sales"):
        months = []
        for m in MONTHS:
            t, s = _num(r[f"{m}_Tar"]), _num(r[f"{m}_Sol"])
            months.append(Month(t, s, _num(r[f"{m}_Ach"]) if t > 0 else None))
        tt = _num(r["Total_Tar"])
        people[r["emp_id"]] = Person(
            emp_id=r["emp_id"], name=(r["emp_name"] or "").strip(),
            depot_name=r["depot_name"] or "", territory=r["emp_terri"] or "",
            division=r["division"], level=int(r["hieararchy"]), year=r["year"], months=months,
            total_target=tt, total_sales=_num(r["Total_Sol"]),
            total_ach=_num(r["Total_Ach"]) if tt > 0 else None)
    return people


def load_team_index(conn: sqlite3.Connection) -> Dict[Tuple[int, str], Set[str]]:
    """{(level, manager_id): {employee ids in rows where that manager column = manager_id}}"""
    have = {r["name"] for r in conn.execute('PRAGMA table_info("zemp")')}
    usable = {lvl: tuple(c for c in cols if c in have) for lvl, (_l, cols) in LEVELS.items()}
    usable = {k: v for k, v in usable.items() if v}
    wanted = sorted({c for v in usable.values() for c in v} | {"Employee ID"})
    index: Dict[Tuple[int, str], Set[str]] = defaultdict(set)
    for row in conn.execute("SELECT " + ", ".join(f'"{c}"' for c in wanted) + " FROM zemp"):
        emp = row["Employee ID"]
        if not emp or emp == VACANT_ID:
            continue
        for lvl, cols in usable.items():
            for c in cols:
                mgr = row[c]
                if mgr and mgr != VACANT_ID:
                    index[(lvl, mgr)].add(emp)
    return index


def detect_last_month(people) -> int:
    last = -1
    for p in people:
        for i, m in enumerate(p.months):
            if m.sales > 0 and i > last:
                last = i
    return last


def ach_class(a: Optional[float]) -> str:
    if a is None:
        return "none"
    return "good" if a >= ACH_GOOD else "mid" if a >= ACH_OK else "low"


def quarters_for(p: Person, last: int) -> List[Quarter]:
    out, prev = [], None
    for q in range(4):
        idx = [i for i in range(q * 3, q * 3 + 3) if i <= last and p.months[i].has_data]
        t = sum(p.months[i].target for i in idx)
        s = sum(p.months[i].sales for i in idx)
        a = s / t * 100 if t > 0 else None
        span = (f"{MONTHS[idx[0]]}-{MONTHS[idx[-1]]}" if len(idx) > 1 else MONTHS[idx[0]] if idx else "")
        out.append(Quarter(f"Q{q + 1}", idx, t, s, a, 0 < len(idx) < 3,
                           q * 3 <= last < q * 3 + 3, span,
                           (a - prev) if (a is not None and prev is not None) else None))
        if a is not None:
            prev = a
    return out


SORTS = {"ach": lambda p: -(p.total_ach if p.total_ach is not None else -1),
         "target": lambda p: -p.total_target, "sales": lambda p: -p.total_sales,
         "name": lambda p: p.name.lower()}


def build_tables(emp: Person, people, index):
    """[(label, [Person...], is_own)] - own row first, then each lower level present."""
    tables = []
    if SHOW_OWN_TABLE:
        tables.append((LEVELS.get(emp.level, (str(emp.level),))[0], [emp], True))
    under = index.get((emp.level, emp.emp_id), set())
    for lvl in sorted(LEVELS, reverse=True):
        if lvl >= emp.level:
            continue
        members = [people[i] for i in under if i in people and people[i].level == lvl and i != emp.emp_id]
        if members:
            members.sort(key=SORTS.get(SORT_TEAM_BY, SORTS["ach"]))
            tables.append((LEVELS[lvl][0], members, False))
    return tables


# =============================================================================
# SMALL HELPERS
# =============================================================================
def money(x) -> str:
    return "-" if not x else f"{x:,.2f}"


def pct(x) -> str:
    return "-" if x is None else f"{x:.1f}%"


def num1(x) -> str:
    """Percentage without the % sign, for narrow table cells (the header says %)."""
    return "-" if x is None else f"{x:.1f}"


def fit_text(s: str, width: float, font: str, size: float) -> str:
    """Shorten with an ellipsis so the text fits in `width` points."""
    if pdfmetrics.stringWidth(s, font, size) <= width:
        return s
    while s and pdfmetrics.stringWidth(s + "...", font, size) > width:
        s = s[:-1]
    return s.rstrip() + "..."


def style(name, size, color=INK, bold=False, leading=None, align=0, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, fontName=FONT_B if bold else FONT, fontSize=size, textColor=color,
                          leading=leading or size * 1.25, alignment=align, **kw)


def nice_step(span: float) -> int:
    for step in (5, 10, 20, 25, 50, 100, 200, 500):
        if span / step <= 6:
            return step
    return 1000


def bezier_segments(pts):
    """Monotone cubic through points -> [(c1x, c1y, c2x, c2y, x, y), ...] (never overshoots)."""
    n = len(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [0 if d[i - 1] * d[i] <= 0 else (d[i - 1] + d[i]) / 2 for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0
        else:
            a, b = m[i] / d[i], m[i + 1] / d[i]
            s = a * a + b * b
            if s > 9:
                t = 3 / s ** 0.5
                m[i], m[i + 1] = t * a * d[i], t * b * d[i]
    segs = []
    for i in range(n - 1):
        h = xs[i + 1] - xs[i]
        segs.append((xs[i] + h / 3, ys[i] + m[i] * h / 3, xs[i + 1] - h / 3, ys[i + 1] - m[i + 1] * h / 3,
                     xs[i + 1], ys[i + 1]))
    return segs


# =============================================================================
# CHART  (reportlab vector drawing)
# =============================================================================
def build_chart(emp: Person, quarters: List[Quarter], last: int, width: float, height: float) -> Drawing:
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, rx=6, ry=6, fillColor=colors.white, strokeColor=LINE, strokeWidth=0.8))
    d.add(String(14, height - 20, "Monthly achievement %", fontName=FONT_B, fontSize=11, fillColor=INK))
    d.add(String(14, height - 32, "Achievement against target, by month and quarter",
                 fontName=FONT, fontSize=7.5, fillColor=MUTE))

    # legend (top right)
    lx = width - 14
    for text, kind in reversed([("Monthly", "m"), ("Quarter average", "q"), ("Target", "t")]):
        tw = pdfmetrics.stringWidth(text, FONT, 7.5)
        d.add(String(lx - tw, height - 21, text, fontName=FONT, fontSize=7.5, fillColor=MUTE))
        ln = Line(lx - tw - 20, height - 19, lx - tw - 6, height - 19,
                  strokeColor=BRAND if kind == "m" else AMBER if kind == "q" else colors.HexColor("#7C8CA1"),
                  strokeWidth=2.2 if kind == "m" else 1.6)
        if kind == "t":
            ln.strokeDashArray = [3, 2]
        d.add(ln)
        lx -= tw + 34

    active = [i for i in range(last + 1) if emp.months[i].ach is not None]
    if not active:
        d.add(String(width / 2, height / 2, "No monthly data yet", fontName=FONT, fontSize=9,
                     fillColor=MUTE, textAnchor="middle"))
        return d

    L, R, B, T = 40, 16, 22, height - 62            # plot box in drawing coordinates
    pw, ph = width - L - R, T - B
    vals = [emp.months[i].ach for i in active] + [TARGET_LINE]
    lo, hi = min(vals), max(vals)
    step = nice_step(max(hi - lo, 10) + 10)
    ymin = max(0, math.floor((lo - step * 0.4) / step) * step)
    ymax = math.ceil((hi + step * 0.4) / step) * step
    if ymax - ymin < step * 3:
        ymax = ymin + step * 3
    X = lambda i: L + pw * (i + 0.5) / 12
    Y = lambda v: B + ph * (v - ymin) / (ymax - ymin)

    # quarter bands + labels
    for q, qt in enumerate(quarters):
        x0, x1 = L + pw * q * 3 / 12, L + pw * (q + 1) * 3 / 12
        if q % 2 == 0:
            d.add(Rect(x0, B, x1 - x0, ph + 18, fillColor=BAND, strokeColor=None))
        label = f"{qt.name}  -" if qt.ach is None else f"{qt.name}  {qt.ach:.1f}%"
        if qt.ach is not None and qt.partial:
            label += f" ({qt.span} only)"
        d.add(String((x0 + x1) / 2, T + 6, label, fontName=FONT_B, fontSize=8, fillColor=INK, textAnchor="middle"))

    # months without data: light hatch
    if last < 11:
        x0, x1 = L + pw * (last + 1) / 12, L + pw
        d.add(Rect(x0, B, x1 - x0, ph, fillColor=colors.HexColor("#F6F8FB"), strokeColor=None))
        h = ph
        s = -h
        while s < x1 - x0:
            xa, xb, ya, yb = x0 + s, x0 + s + h, B, B + h
            if xa < x0:
                ya += x0 - xa
                xa = x0
            if xb > x1:
                yb -= xb - x1
                xb = x1
            if xb > xa and yb > ya:
                d.add(Line(xa, ya, xb, yb, strokeColor=colors.HexColor("#D5DDE7"), strokeWidth=0.5))
            s += 7
        d.add(String((x0 + x1) / 2, B + ph / 2, "Awaiting data", fontName=FONT, fontSize=8,
                     fillColor=colors.HexColor("#8696AA"), textAnchor="middle"))

    # grid, y labels
    v = int(ymin)
    while v <= ymax:
        y = Y(v)
        if v != TARGET_LINE:
            d.add(Line(L, y, L + pw, y, strokeColor=colors.HexColor("#E4EAF1"), strokeWidth=0.5))
        d.add(String(L - 6, y - 2.5, f"{v:g}%", fontName=FONT, fontSize=7, fillColor=MUTE, textAnchor="end"))
        v += step
    ty = Y(TARGET_LINE)
    t = Line(L, ty, L + pw, ty, strokeColor=colors.HexColor("#7C8CA1"), strokeWidth=0.9)
    t.strokeDashArray = [4, 3]
    d.add(t)
    d.add(String(L + pw - 3, ty + 3, f"Target {TARGET_LINE:g}%", fontName=FONT_B, fontSize=6.5,
                 fillColor=MUTE, textAnchor="end"))

    # x labels + axis
    for i, mn in enumerate(MONTHS):
        d.add(String(X(i), B - 12, mn, fontName=FONT, fontSize=7.5, textAnchor="middle",
                     fillColor=MUTE if i in active else colors.HexColor("#A9B5C4")))
    d.add(Line(L, B, L + pw, B, strokeColor=colors.HexColor("#B6C2D1"), strokeWidth=0.7))

    # quarter averages
    for qt in quarters:
        if qt.ach is None:
            continue
        d.add(Line(L + pw * qt.idx[0] / 12 + 6, Y(qt.ach), L + pw * (qt.idx[-1] + 1) / 12 - 6, Y(qt.ach),
                   strokeColor=AMBER, strokeWidth=1.8, strokeLineCap=1))

    # monthly line (split where a month has no data)
    segments: List[List[int]] = []
    for i in active:
        if segments and segments[-1][-1] == i - 1:
            segments[-1].append(i)
        else:
            segments.append([i])
    for seg in segments:
        pts = [(X(i), Y(emp.months[i].ach)) for i in seg]
        if len(pts) < 2:
            continue
        curves = bezier_segments(pts)
        area = SPath(fillColor=BRAND, fillOpacity=0.13, strokeColor=None)
        area.moveTo(*pts[0])
        for c in curves:
            area.curveTo(*c)
        area.lineTo(pts[-1][0], B)
        area.lineTo(pts[0][0], B)
        area.closePath()
        d.add(area)
        line = SPath(fillColor=None, strokeColor=BRAND, strokeWidth=2.2, strokeLineCap=1, strokeLineJoin=1)
        line.moveTo(*pts[0])
        for c in curves:
            line.curveTo(*c)
        d.add(line)
    for i in active:
        x, y = X(i), Y(emp.months[i].ach)
        label = f"{emp.months[i].ach:.1f}"
        tw = pdfmetrics.stringWidth(label, FONT_B, 7.5)
        d.add(Rect(x - tw / 2 - 1.5, y + 5, tw + 3, 9.5, fillColor=colors.white, fillOpacity=0.85, strokeColor=None))
        d.add(String(x, y + 7, label, fontName=FONT_B, fontSize=7.5, fillColor=INK, textAnchor="middle"))
        d.add(Circle(x, y, 3.2, fillColor=colors.white, strokeColor=BRAND, strokeWidth=1.6))
    return d


def build_bar(width: float, frac: float, color) -> Drawing:
    d = Drawing(width, 5)
    d.add(Rect(0, 0, width, 5, rx=2.5, ry=2.5, fillColor=colors.HexColor("#E8EDF3"), strokeColor=None))
    w = max(0, min(frac, 1)) * width
    if w > 0:
        d.add(Rect(0, 0, w, 5, rx=2.5, ry=2.5, fillColor=color, strokeColor=None))
    return d


# =============================================================================
# PAGE FURNITURE
# =============================================================================
class NumberedCanvas(canvas.Canvas):
    """Adds 'Page x of y' once the total page count is known."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self.setFont(FONT, 7.5)
            self.setFillColor(MUTE)
            self.drawRightString(self._pagesize[0] - MARGIN, 14, f"Page {self._pageNumber} of {total}")
            super().showPage()
        super().save()


MARGIN = 28


def draw_footer(c, doc, generated):
    w = c._pagesize[0]
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(MARGIN, 24, w - MARGIN, 24)
    c.setFont(FONT, 7.5)
    c.setFillColor(MUTE)
    c.drawString(MARGIN, 14, f"{COMPANY_NAME}   |   Generated {generated}")


def make_page_callbacks(emp: Person, level_label: str, title: str, generated: str):
    def first(c, doc):
        w, h = c._pagesize
        band = 62 if w > 700 else 82
        c.setFillColor(NAVY)
        c.rect(0, h - band, w, band, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#9CC4EE"))
        c.setFont(FONT_B, 8.5)
        c.drawString(MARGIN, h - 19, COMPANY_NAME)
        c.setFillColor(colors.white)
        c.setFont(FONT_B, 15 if w > 700 else 12.5)
        c.drawString(MARGIN, h - 37, title)
        c.setFillColor(colors.HexColor("#B8C7D9"))
        c.setFont(FONT, 8.5)
        c.drawString(MARGIN, h - 51, UNIT_NOTE)
        meta = f"{emp.emp_id}  |  {level_label}  |  Territory {emp.territory}" + \
               (f"  |  Division {emp.division}" if emp.division is not None else "")
        if w > 700:
            c.setFillColor(colors.white)
            c.setFont(FONT_B, 12)
            c.drawRightString(w - MARGIN, h - 30, emp.name)
            c.setFillColor(colors.HexColor("#B8C7D9"))
            c.setFont(FONT, 8.5)
            c.drawRightString(w - MARGIN, h - 44, meta)
        else:
            c.setFillColor(colors.white)
            c.setFont(FONT_B, 11)
            c.drawString(MARGIN, h - 65, emp.name)
            c.setFillColor(colors.HexColor("#B8C7D9"))
            c.setFont(FONT, 8)
            c.drawString(MARGIN, h - 77, meta)
        draw_footer(c, doc, generated)

    def later(c, doc):
        w, h = c._pagesize
        c.setFillColor(NAVY)
        c.rect(0, h - 24, w, 24, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(FONT_B, 8.5)
        c.drawString(MARGIN, h - 15.5, f"{COMPANY_NAME}  -  Target vs Achievement")
        c.setFont(FONT, 8.5)
        c.drawRightString(w - MARGIN, h - 15.5, f"{emp.name}  |  {emp.emp_id}")
        draw_footer(c, doc, generated)

    return first, later


# =============================================================================
# FLOWABLES
# =============================================================================
def kpi_strip(emp: Person, last: int, width: float):
    best = max((i for i in range(last + 1) if emp.months[i].ach is not None),
               key=lambda i: emp.months[i].ach, default=None)
    first = next((i for i in range(last + 1) if emp.months[i].ach is not None), None)
    gap = emp.total_target - emp.total_sales
    lbl, val, sub = style("kl", 8, MUTE), style("kv", 17, INK, True, 20), style("ks", 7.5, MUTE)
    brand = style("kb", 17, BRAND, True, 20)
    best_sub = "No monthly data"
    if best is not None:
        best_sub = MONTHS[best]
        if first is not None and best != first:
            diff = emp.months[best].ach - emp.months[first].ach
            best_sub += f" - {'up' if diff >= 0 else 'down'} {abs(diff):.1f} pts since {MONTHS[first]}"
    gap_txt = (f"{money(gap)} below target" if gap > 0 else f"{money(-gap)} above target" if gap < 0 else "On target")
    cells = [
        [Paragraph("Total target", lbl), Paragraph(money(emp.total_target), val),
         Paragraph(f"Jan-{MONTHS[last]} - Lac Tk", sub)],
        [Paragraph("Total achievement", lbl), Paragraph(money(emp.total_sales), val), Paragraph(gap_txt, sub)],
        [Paragraph("Overall achievement", lbl),
         Paragraph(f"{emp.total_ach:.2f}%" if emp.total_ach is not None else "-", brand),
         Paragraph("Year to date", sub)],
        [Paragraph("Best month", lbl), Paragraph(pct(emp.months[best].ach) if best is not None else "-", val),
         Paragraph(best_sub, sub)],
    ]
    t = Table([cells], colWidths=[width / 4] * 4)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, LINE), ("LINEAFTER", (0, 0), (-2, -1), 0.8, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def quarter_cards(quarters: List[Quarter], width: float):
    colw = width / 4
    cells = []
    for q in quarters:
        if q.ach is None:
            cells.append([Paragraph(f"<b>{q.name}</b>", style("qn", 9)),
                          Paragraph("-", style("qe", 20, colors.HexColor("#B5C0CE"), True, 26)),
                          Paragraph("No data yet", style("qs", 8, MUTE))])
            continue
        cls = ach_class(q.ach)
        col = PALETTE[cls][0]
        tag = " to date" if (q.current and q.partial) else " partial" if q.partial else ""
        head = Table([[Paragraph(f"<b>{q.name}</b>", style("qn", 9)),
                       Paragraph(f"{q.span}<font color='#D9822B'><b>{tag}</b></font>", style("qm", 7.5, MUTE, align=2))]],
                     colWidths=[colw * 0.3, colw - 28 - colw * 0.3])
        head.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                  ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        body = [head,
                Paragraph(f"{q.ach:.1f}<font size=11>%</font>", style("qv", 21, col, True, 27)),
                build_bar(colw - 28, q.ach / 100, col),
                Spacer(1, 4),
                Paragraph(f"<font color='#5B6B7F'>Target</font>&nbsp;&nbsp;<b>{money(q.target)}</b>"
                          f"&nbsp;&nbsp;&nbsp;&nbsp;<font color='#5B6B7F'>Sales</font>&nbsp;&nbsp;<b>{money(q.sales)}</b>",
                          style("qd", 7.5))]
        if q.delta is not None:
            up = q.delta >= 0
            body.append(Paragraph(f"{'+' if up else '-'}{abs(q.delta):.1f} pts vs prev. quarter",
                                  style("qx", 7.5, PALETTE['good'][0] if up else PALETTE['low'][0], True)))
        cells.append(body)
    t = Table([cells], colWidths=[colw] * 4)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, LINE), ("LINEAFTER", (0, 0), (-2, -1), 0.8, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def heading(text: str, count: int, width: float, own: bool = False):
    right = "own figures" if own else f"{count:,} record{'s' if count != 1 else ''}"
    t = Table([[Paragraph(f"<b>{escape(text)}</b>", style("h2", 11)),
                Paragraph(right, style("hc", 8, MUTE, align=2))]], colWidths=[width * 0.6, width * 0.4])
    t.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, 0), 3, BRAND), ("LEFTPADDING", (0, 0), (0, 0), 7),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    t.keepWithNext = 1          # never leave a heading alone at the bottom of a page
    return t


def own_table(emp: Person, last: int, width: float):
    """Three-row monthly breakdown of the manager's own figures."""
    head = [""] + MONTHS + ["Total"]
    rows = [head, ["Target"], ["Sales"], ["Ach %"]]
    for i in range(12):
        m = emp.months[i]
        shown = i <= last and m.has_data
        rows[1].append(money(m.target) if shown else "-")
        rows[2].append(money(m.sales) if shown else "-")
        rows[3].append(pct(m.ach) if shown and m.ach is not None else "-")
    rows[1].append(money(emp.total_target))
    rows[2].append(money(emp.total_sales))
    rows[3].append(pct(emp.total_ach))
    first = 38
    t = Table(rows, colWidths=[first] + [(width - first) / 13] * 13, rowHeights=[15, 15, 15, 15])
    cmds = [("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), 6.8),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FONT_B), ("FONTNAME", (0, 1), (0, -1), FONT_B),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (-1, 1), (-1, -1), TOTAL_BG), ("FONTNAME", (-1, 1), (-1, -1), FONT_B),
            ("BACKGROUND", (-1, 0), (-1, 0), BRAND),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("TEXTCOLOR", (1, 1), (-1, -1), INK)]
    for c in range(1, 14):
        a = emp.total_ach if c == 13 else (emp.months[c - 1].ach if c - 1 <= last else None)
        cls = ach_class(a)
        if cls in PALETTE:
            cmds += [("TEXTCOLOR", (c, 3), (c, 3), PALETTE[cls][0]), ("BACKGROUND", (c, 3), (c, 3), PALETTE[cls][1]),
                     ("FONTNAME", (c, 3), (c, 3), FONT_B)]
    for c in range(1, 14):
        if rows[1][c] == "-":
            cmds.append(("TEXTCOLOR", (c, 1), (c, 3), colors.HexColor("#B5C0CE")))
    t.setStyle(TableStyle(cmds))
    return t


def team_table(people: List[Person], quarters_by_id, last: int, width: float):
    """
    Compact table for page width: totals + monthly Ach % (+ quarter Ach % and depot when they fit).
    The full month-by-month Target/Sales detail stays in the HTML report.
    """
    n_m = last + 1
    f_id, f_name, f_depot, f_terr, f_num, f_ach = 54, 112, 66, 50, 50, 38
    min_cell = 21.5

    def need(depot, quarters):
        base = f_id + f_name + f_terr + 2 * f_num + f_ach + (f_depot if depot else 0)
        return base + min_cell * (n_m + (4 if quarters else 0))

    use_depot, use_q = True, True
    if need(True, True) > width:
        use_q = False
    if need(True, use_q) > width:
        use_depot = False
    fixed = [f_id, f_name] + ([f_depot] if use_depot else []) + [f_terr, f_num, f_num, f_ach]
    n_cells = n_m + (4 if use_q else 0)
    cell_w = (width - sum(fixed)) / n_cells
    widths = fixed + [cell_w] * n_cells
    c_target = len(fixed) - 3
    c_ach = len(fixed) - 1
    first_month = len(fixed)
    first_q = first_month + n_m

    h1 = ["Employee ID", "Name"] + (["Depot"] if use_depot else []) + ["Territory", "Target", "Sales", "Ach %"]
    h1 += ["Monthly achievement %"] + [""] * (n_m - 1)
    if use_q:
        h1 += ["Quarter %"] + [""] * 3
    h2 = [""] * len(fixed) + MONTHS[:n_m] + (["Q1", "Q2", "Q3", "Q4"] if use_q else [])
    rows = [h1, h2]
    cmds = []
    for p in people:
        qs = quarters_by_id[p.emp_id]
        r = [p.emp_id, fit_text(p.name, f_name - 6, FONT, 6.8)]
        if use_depot:
            r.append(fit_text(p.depot_name, f_depot - 6, FONT, 6.8))
        r += [fit_text(p.territory, f_terr - 5, FONT, 6.8), money(p.total_target), money(p.total_sales), pct(p.total_ach)]
        r += [num1(p.months[i].ach) for i in range(n_m)]
        if use_q:
            r += [num1(q.ach) for q in qs]
        rows.append(r)
        ri = len(rows) - 1
        values = [(c_ach, p.total_ach)] + [(first_month + i, p.months[i].ach) for i in range(n_m)]
        if use_q:
            values += [(first_q + k, qs[k].ach) for k in range(4)]
        for c, a in values:
            cls = ach_class(a)
            if cls in PALETTE:
                cmds.append(("TEXTCOLOR", (c, ri), (c, ri), PALETTE[cls][0]))
                cmds.append(("BACKGROUND", (c, ri), (c, ri), PALETTE[cls][1]))
            else:
                cmds.append(("TEXTCOLOR", (c, ri), (c, ri), colors.HexColor("#B5C0CE")))

    t = Table(rows, colWidths=widths, repeatRows=2)
    base = [
        ("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), 6.8),
        ("LEADING", (0, 0), (-1, -1), 8.4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (c_target, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("BACKGROUND", (0, 1), (-1, 1), NAVY2),
        ("TEXTCOLOR", (0, 0), (-1, 1), colors.white), ("FONTNAME", (0, 0), (-1, 1), FONT_B),
        ("SPAN", (first_month, 0), (first_month + n_m - 1, 0)), ("ALIGN", (first_month, 0), (-1, 1), "CENTER"),
        ("LINEBEFORE", (first_month, 0), (first_month, 1), 0.5, colors.HexColor("#27507F")),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1), [colors.white, STRIPE]),
        ("LINEBELOW", (0, 2), (-1, -1), 0.3, colors.HexColor("#EEF2F6")),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
    ]
    for c in range(0, len(fixed)):                                  # header text of fixed columns spans both rows
        base.append(("SPAN", (c, 0), (c, 1)))
        base.append(("VALIGN", (c, 0), (c, 1), "BOTTOM"))
    base.append(("ALIGN", (0, 0), (c_target - 1, 1), "LEFT"))
    base.append(("ALIGN", (c_target, 0), (c_ach, 1), "RIGHT"))
    if use_q:
        base += [("SPAN", (first_q, 0), (first_q + 3, 0)),
                 ("LINEBEFORE", (first_q, 0), (first_q, -1), 0.5, colors.HexColor("#27507F")),
                 ("BACKGROUND", (first_q, 0), (first_q + 3, 0), BRAND)]
    base += [("BACKGROUND", (c_target, 2), (c_ach - 1, -1), TOTAL_BG),
             ("FONTNAME", (c_target, 2), (c_ach - 1, -1), FONT_B)]
    t.setStyle(TableStyle(base + cmds))
    return t


# =============================================================================
# BUILD ONE PDF
# =============================================================================
def build_pdf(emp: Person, tables, last: int, out_path: Path, pagesize) -> None:
    W, H = pagesize
    cw = W - 2 * MARGIN
    band1 = 62 if W > 700 else 82
    generated = datetime.now().strftime("%d/%m/%Y %I:%M %p")
    level_label = LEVELS.get(emp.level, (str(emp.level),))[0]
    title = TITLE_TEMPLATE.format(month=MONTH_NAMES[last] if last >= 0 else "", year=emp.year or "")
    first_cb, later_cb = make_page_callbacks(emp, level_label, title, generated)

    doc = BaseDocTemplate(str(out_path), pagesize=pagesize, title=f"{COMPANY_NAME} - {emp.name}",
                          author=COMPANY_NAME, leftMargin=MARGIN, rightMargin=MARGIN)
    doc.addPageTemplates([
        PageTemplate("first", [Frame(MARGIN, 34, cw, H - band1 - 12 - 34, 0, 0, 0, 0, id="f1")],
                     onPage=first_cb, autoNextPageTemplate="later"),
        PageTemplate("later", [Frame(MARGIN, 34, cw, H - 24 - 10 - 34, 0, 0, 0, 0, id="f2")], onPage=later_cb),
    ])

    quarters = quarters_for(emp, last)
    story = [kpi_strip(emp, last, cw), Spacer(1, 4)]
    team_rows = [(l, p, own) for l, p, own in tables if not own]
    if team_rows:
        total = sum(len(p) for _l, p, _o in team_rows)
        parts = ", ".join(f"{len(p):,} {escape(l)}" for l, p, _o in team_rows)
        story.append(Paragraph(f"<b>Team of {total:,}</b>  -  {parts}", style("tn", 8, MUTE)))
    story += [Spacer(1, 6), build_chart(emp, quarters, last, cw, 205 if W > 700 else 190), Spacer(1, 6),
              quarter_cards(quarters, cw)]
    story.append(Spacer(1, 4))
    story.append(Paragraph("Quarter achievement = quarter sales / quarter target, for months with data. "
                           "pts = percentage points.", style("nt", 7, MUTE)))

    for label, people, own in tables:
        story.append(Spacer(1, 10))
        story.append(heading(label, len(people), cw, own))
        story.append(Spacer(1, 3))
        if own:
            story.append(own_table(people[0], last, cw))
        else:
            qmap = {p.emp_id: quarters_for(p, last) for p in people}
            story.append(team_table(people, qmap, last, cw))
    doc.build(story, canvasmaker=NumberedCanvas)


# =============================================================================
# COMMAND LINE
# =============================================================================
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-e", "--employee", action="append", metavar="ID")
    ap.add_argument("--levels", type=int, nargs="+")
    ap.add_argument("--divisions", type=int, nargs="+")
    ap.add_argument("--all-divisions", action="store_true")
    ap.add_argument("--upto", type=int, choices=range(1, 13), metavar="MONTH")
    ap.add_argument("--portrait", action="store_true", help="A4 portrait instead of landscape")
    ap.add_argument("--include-no-team", action="store_true")
    ap.add_argument("--db", metavar="FILE")
    ap.add_argument("--out", metavar="DIR")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)

    levels = tuple(a.levels) if a.levels else REPORT_LEVELS
    divisions = None if a.all_divisions else (tuple(a.divisions) if a.divisions else REPORT_DIVISIONS)
    skip_no_team = False if a.include_no_team else SKIP_IF_NO_TEAM
    upto = a.upto or REPORT_UPTO_MONTH
    out_dir = Path(a.out) if a.out else OUTPUT_DIR
    pagesize = portrait(PAGE_SIZE) if (a.portrait or not LANDSCAPE) else landscape(PAGE_SIZE)

    db = Path(a.db) if a.db else next((p for p in DB_CANDIDATES if p.exists()), None)
    if db is None or not Path(db).exists():
        print("Error: database not found. Put data.db in ./data/ or next to this file, or use --db FILE.",
              file=sys.stderr)
        return 1
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        people = load_sales(conn)
        index = load_team_index(conn)
    except (sqlite3.Error, KeyError) as exc:
        print(f"Error reading database: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    last = (upto - 1) if upto else detect_last_month(people.values())
    if a.employee:
        chosen = []
        for eid in a.employee:
            if eid in people:
                chosen.append(people[eid])
            else:
                print(f"  ! {eid} was not found in the sales table", file=sys.stderr)
    else:
        chosen = [p for p in people.values()
                  if p.level in levels and (divisions is None or p.division in divisions)
                  and (not skip_no_team or (index.get((p.level, p.emp_id), set()) - {p.emp_id}))]
        chosen.sort(key=lambda p: (-p.level, p.emp_id))

    if a.list:
        for p in chosen:
            print(f"{p.emp_id}  {LEVELS.get(p.level, (p.level,))[0]:<9} {p.territory:<9} {p.name}")
        print(f"{len(chosen)} employees")
        return 0

    setup_fonts()
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"Database : {db}\nOutput   : {out_dir}   ({'landscape' if pagesize[0] > pagesize[1] else 'portrait'})")
    for n, emp in enumerate(chosen, 1):
        build_pdf(emp, build_tables(emp, people, index), last, out_dir / f"{emp.emp_id}.pdf", pagesize)
        if n % 25 == 0 or n == len(chosen):
            print(f"  {n}/{len(chosen)} PDFs written")
    print(f"Done: {len(chosen)} PDFs in {time.time() - t0:.1f}s")
    return 0 if chosen else 2


if __name__ == "__main__":
    sys.exit(main())
