"""Zero-filled, cached pageview series from the Wikimedia Analytics API."""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from datetime import date

from . import config
from .cache import Cache, series_key
from .net import Client
from .series import (day_key, day_range, month_end, month_key, month_range,
                     missing_intervals, parse_day_key, parse_month_key)

PV = config.PAGEVIEWS_API


@dataclass
class Ctx:
    client: Client
    cache: Cache


def cached_json(ctx: Ctx, url: str, max_age_s: float = 14 * 86400):
    hit = ctx.cache.get_json(url, max_age_s)
    if hit is not None:
        return hit
    status, body = ctx.client.get_json(url)
    if status == 200:
        ctx.cache.put_json(url, status, body)
    return status, body


def quote_title(title: str) -> str:
    return urllib.parse.quote(title.replace(" ", "_"), safe="")


def _article_url(project, title, access, agent, gran, s: date, e: date) -> str:
    end = month_end(e) if gran == "monthly" else e
    return (f"{PV}/per-article/{project}/{access}/{agent}/{quote_title(title)}/{gran}/"
            f"{s:%Y%m%d}/{end:%Y%m%d}")


def _project_url(project, access, agent, gran, s: date, e: date) -> str:
    end = month_end(e) if gran == "monthly" else e
    return f"{PV}/aggregate/{project}/{access}/{agent}/{gran}/{s:%Y%m%d}00/{end:%Y%m%d}00"


def _ensure(ctx: Ctx, skey: str, start: date, end: date, monthly: bool, make_url) -> None:
    for s, e in missing_intervals(start, end, ctx.cache.coverage(skey), monthly):
        status, body = ctx.client.get_json(make_url(s, e))
        if status == 200:
            lo, hi = (month_key(s), month_key(e)) if monthly else (day_key(s), day_key(e))
            pts = {}
            for it in body.get("items", []):
                ts = it["timestamp"][:6] if monthly else it["timestamp"][:8]
                if lo <= ts <= hi:  # the API may return a partial month past `end`
                    pts[ts] = int(it.get("views") or 0)
            ctx.cache.put_points(skey, pts)
        # 404 = "zero or not loaded": we only ask for loaded periods, so zeros.
        ctx.cache.add_coverage(skey, s, e, monthly)
        ctx.cache.misses += 1


def _read(ctx: Ctx, skey: str, start: date, end: date, monthly: bool) -> dict[date, int]:
    if monthly:
        pts = ctx.cache.get_points(skey, month_key(start), month_key(end))
        return {m: pts.get(month_key(m), 0) for m in month_range(start, end)}
    pts = ctx.cache.get_points(skey, day_key(start), day_key(end))
    return {d: pts.get(day_key(d), 0) for d in day_range(start, end)}


def article_series(ctx: Ctx, project: str, title: str, start: date, end: date, *,
                   gran: str = "daily", agent: str = "user",
                   access: str = "all-access") -> dict[date, int]:
    monthly = gran == "monthly"
    skey = series_key("article", project, title.replace(" ", "_"), access, agent, gran)
    _ensure(ctx, skey, start, end, monthly,
            lambda s, e: _article_url(project, title, access, agent, gran, s, e))
    return _read(ctx, skey, start, end, monthly)


def project_series(ctx: Ctx, project: str, start: date, end: date, *,
                   gran: str = "daily", agent: str = "user",
                   access: str = "all-access") -> dict[date, int]:
    monthly = gran == "monthly"
    skey = series_key("project", project, "", access, agent, gran)
    _ensure(ctx, skey, start, end, monthly,
            lambda s, e: _project_url(project, access, agent, gran, s, e))
    return _read(ctx, skey, start, end, monthly)


__all__ = ["Ctx", "cached_json", "article_series", "project_series", "quote_title",
           "parse_day_key", "parse_month_key"]
