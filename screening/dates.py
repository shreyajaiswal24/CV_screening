"""Date arithmetic - deliberately in code, not in the model.

Root cause of failure #1: the model was asked to produce a number it had to
calculate, with no anchor for 'today' and no rule for overlapping contracts.
The model now extracts literal date strings only; this module does the maths.
"""
from __future__ import annotations

import re
from datetime import date

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
PRESENT = {"present", "current", "now", "ongoing", "today", "date"}


def parse_point(s: str | None, *, today: date | None = None) -> tuple[int, int] | None:
    """Parse a date fragment into (year, month). Returns None if unparseable."""
    if not s:
        return None
    today = today or date.today()
    t = s.strip().lower().strip(".,")

    if any(p in t for p in PRESENT):
        return today.year, today.month

    month = None
    for name, num in MONTHS.items():
        if re.search(rf"\b{name}", t):
            month = num
            break

    m = re.search(r"(19|20)\d{2}", t)
    if not m:
        return None
    year = int(m.group(0))

    if month is None:
        m2 = re.search(r"\b(0?[1-9]|1[0-2])\s*[/\-]\s*(19|20)\d{2}", t)
        month = int(m2.group(1)) if m2 else 1
    return year, month


def _months(p: tuple[int, int]) -> int:
    return p[0] * 12 + p[1]


def total_years(date_ranges: list, *, today: date | None = None) -> float | None:
    """Total professional experience in years, merging overlapping periods.

    Overlapping contract roles are counted once - the fix for failure case E2.
    """
    today = today or date.today()
    intervals: list[tuple[int, int]] = []

    for dr in date_ranges:
        start = parse_point(getattr(dr, "start", None) or (dr.get("start") if isinstance(dr, dict) else None), today=today)
        end_raw = getattr(dr, "end", None) or (dr.get("end") if isinstance(dr, dict) else None)
        end = parse_point(end_raw, today=today)
        if start is None:
            continue
        if end is None:
            end = (today.year, today.month)
        a, b = _months(start), _months(end)
        if b < a:
            a, b = b, a
        intervals.append((a, b))

    if not intervals:
        return None

    intervals.sort()
    merged = [list(intervals[0])]
    for a, b in intervals[1:]:
        if a <= merged[-1][1]:            # overlap -> merge, do not double-count
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])

    months = sum(b - a for a, b in merged)
    return round(months / 12.0, 1)
