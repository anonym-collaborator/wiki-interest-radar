"""Date/month helpers and small series utilities (no pandas on purpose)."""
from __future__ import annotations

from datetime import date, timedelta

from . import config


def month_start(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def month_end(d: date) -> date:
    return add_months(month_start(d), 1) - timedelta(days=1)


def month_key(d: date) -> str:
    return f"{d.year:04d}{d.month:02d}"


def parse_month_key(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), 1)


def month_label(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def parse_month_label(s: str) -> date:
    y, m = s.strip().split("-")[:2]
    return date(int(y), int(m), 1)


def day_key(d: date) -> str:
    return d.strftime("%Y%m%d")


def parse_day_key(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def month_range(a: date, b: date) -> list[date]:
    out, cur = [], month_start(a)
    while cur <= b:
        out.append(cur)
        cur = add_months(cur, 1)
    return out


def day_range(a: date, b: date) -> list[date]:
    n = (b - a).days
    return [a + timedelta(days=i) for i in range(n + 1)]


def last_complete_month(today: date, lag_days: int = config.DATA_LAG_DAYS) -> date:
    """Latest month whose data should be fully loaded in the API."""
    m = add_months(month_start(today), -1)
    if today < add_months(m, 1) + timedelta(days=lag_days):
        m = add_months(m, -1)
    return m


def daily_to_monthly(daily: dict[date, int]) -> dict[date, int]:
    out: dict[date, int] = {}
    for d, v in daily.items():
        k = month_start(d)
        out[k] = out.get(k, 0) + v
    return out


def merge_intervals(iv: list[tuple[date, date]], step_days: int = 1) -> list[tuple[date, date]]:
    """Merge closed intervals that overlap or touch (gap < step)."""
    if not iv:
        return []
    iv = sorted(iv)
    out = [iv[0]]
    for s, e in iv[1:]:
        ps, pe = out[-1]
        if (s - pe).days <= step_days:
            out[-1] = (ps, max(pe, e))
        else:
            out.append((s, e))
    return out


def missing_intervals(start: date, end: date, covered: list[tuple[date, date]],
                      monthly: bool = False) -> list[tuple[date, date]]:
    """Sub-ranges of [start, end] not covered. Monthly intervals use month starts."""
    gaps = []
    cur = start
    step = (lambda d: add_months(d, 1)) if monthly else (lambda d: d + timedelta(days=1))
    back = (lambda d: add_months(d, -1)) if monthly else (lambda d: d - timedelta(days=1))
    for s, e in merge_intervals(covered, 31 if monthly else 1):
        if e < cur:
            continue
        if s > end:
            break
        if s > cur:
            gaps.append((cur, min(back(s), end)))
        cur = max(cur, step(e))
        if cur > end:
            break
    if cur <= end:
        gaps.append((cur, end))
    return gaps
