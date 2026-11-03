"""
Geometry for the "Monthly achievement %" line chart.

This module only does the maths (scales, smooth curve, tick positions) and
returns plain numbers/strings.  The drawing itself is in
templates/_chart.html and the colours are in static/report.css, so you can
restyle the chart without touching Python.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from .models import MONTHS, Person, Quarter

# SVG canvas (it scales to the page width; these are just internal units)
WIDTH, HEIGHT = 960, 410
PAD_L, PAD_R, PAD_T, PAD_B = 58, 24, 58, 44


def _nice_step(span: float) -> int:
    for step in (5, 10, 20, 25, 50, 100, 200, 500):
        if span / step <= 6:
            return step
    return 1000


def _monotone_path(pts: Sequence[Tuple[float, float]]) -> str:
    """Smooth curve through the points that never overshoots between them."""
    n = len(pts)
    if n == 1:
        return ""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [0 if d[i - 1] * d[i] <= 0 else (d[i - 1] + d[i]) / 2
                  for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0
        else:
            a, b = m[i] / d[i], m[i + 1] / d[i]
            s = a * a + b * b
            if s > 9:
                t = 3 / math.sqrt(s)
                m[i], m[i + 1] = t * a * d[i], t * b * d[i]
    path = f"M{xs[0]:.1f},{ys[0]:.1f}"
    for i in range(n - 1):
        h = xs[i + 1] - xs[i]
        path += (f" C{xs[i] + h / 3:.1f},{ys[i] + m[i] * h / 3:.1f}"
                 f" {xs[i + 1] - h / 3:.1f},{ys[i + 1] - m[i + 1] * h / 3:.1f}"
                 f" {xs[i + 1]:.1f},{ys[i + 1]:.1f}")
    return path


def _fmt(x: float) -> str:
    return f"{x:,.2f}"


def build_chart(person: Person, quarters: List[Quarter], last_month: int,
                target_line: float = 100) -> Dict:
    pw, ph = WIDTH - PAD_L - PAD_R, HEIGHT - PAD_T - PAD_B
    base_y = PAD_T + ph

    active = [i for i in range(last_month + 1) if person.months[i].ach is not None]
    achs = [person.months[i].ach for i in active]

    # ---- y scale --------------------------------------------------------
    values = achs + [target_line]
    lo, hi = min(values), max(values)
    step = _nice_step(max(hi - lo, 10) + 10)
    ymin = max(0, math.floor((lo - step * 0.4) / step) * step)
    ymax = math.ceil((hi + step * 0.4) / step) * step
    if ymax - ymin < step * 3:
        ymax = ymin + step * 3

    def X(i: float) -> float:
        return PAD_L + pw * (i + 0.5) / 12

    def Y(v: float) -> float:
        return PAD_T + ph * (1 - (v - ymin) / (ymax - ymin))

    ticks = [{"y": round(Y(v), 1), "label": f"{v:g}%", "is_target": v == target_line}
             for v in range(int(ymin), int(ymax) + 1, step)]

    # ---- quarter bands (shaded alternately) ------------------------------
    bands = []
    for q, qt in enumerate(quarters):
        x0 = PAD_L + pw * q * 3 / 12
        x1 = PAD_L + pw * (q + 1) * 3 / 12
        if qt.ach is None:
            label = f"{qt.name}  –"
        else:
            label = f"{qt.name}  {qt.ach:.1f}%"
            if qt.partial:
                label += f" ({qt.span} only)"
        bands.append({"x": round(x0, 1), "w": round(x1 - x0, 1), "cx": round((x0 + x1) / 2, 1),
                      "shaded": q % 2 == 0, "label": label})

    # ---- quarter-average markers -----------------------------------------
    qavg = []
    for q, qt in enumerate(quarters):
        if qt.ach is None:
            continue
        first, last = qt.month_idx[0], qt.month_idx[-1]
        qavg.append({
            "x1": round(PAD_L + pw * first / 12 + 10, 1),
            "x2": round(PAD_L + pw * (last + 1) / 12 - 10, 1),
            "y": round(Y(qt.ach), 1),
            "tip": f"{qt.name} achievement {qt.ach:.2f}%",
        })

    # ---- monthly line, split wherever a month has no data -----------------
    segments: List[List[int]] = []
    for i in active:
        if segments and segments[-1][-1] == i - 1:
            segments[-1].append(i)
        else:
            segments.append([i])
    lines, areas = [], []
    for seg in segments:
        pts = [(X(i), Y(person.months[i].ach)) for i in seg]
        if len(pts) > 1:
            d = _monotone_path(pts)
            lines.append(d)
            areas.append(f"{d} L{pts[-1][0]:.1f},{base_y} L{pts[0][0]:.1f},{base_y} Z")

    points = []
    for i in active:
        m = person.months[i]
        points.append({
            "x": round(X(i), 1), "y": round(Y(m.ach), 1), "label": f"{m.ach:.1f}",
            "tip": f"{MONTHS[i]}: {m.ach:.2f}%  (target {_fmt(m.target)}, sales {_fmt(m.sales)})",
        })

    # ---- months without data ---------------------------------------------
    nodata = None
    if last_month < 11:
        x0 = PAD_L + pw * (last_month + 1) / 12
        nodata = {"x": round(x0, 1), "w": round(PAD_L + pw - x0, 1),
                  "cx": round((x0 + PAD_L + pw) / 2, 1), "cy": round(PAD_T + ph / 2, 1)}

    return {
        "width": WIDTH, "height": HEIGHT,
        "left": PAD_L, "right": WIDTH - PAD_R, "top": PAD_T, "base": base_y,
        "ticks": ticks,
        "target_y": round(Y(target_line), 1), "target_value": target_line,
        "months": [{"x": round(X(i), 1), "name": MONTHS[i], "dim": i not in active}
                   for i in range(12)],
        "bands": bands, "qavg": qavg, "lines": lines, "areas": areas,
        "points": points, "nodata": nodata,
        "has_data": bool(active),
        "aria": f"Monthly achievement percentage, {MONTHS[active[0]]} to {MONTHS[active[-1]]}"
                if active else "No monthly data",
    }
