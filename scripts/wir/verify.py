"""`verify`: independent robustness re-check of an analyze run.

Answers "how much can we trust this?" beyond the built-in checks:
  devices  - does the change hold on desktop and on mobile web separately?
  bots     - does it hold when bots are counted too (all-agents)?
  window   - does the trend keep its sign without the first / last 3 months?
  spot     - one month re-fetched from the API, bypassing the cache, must match.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

from . import config, langs, stats
from .cache import Cache
from .fetch import Ctx, _article_url, article_series, project_series
from .net import ApiError, Client
from .runio import load_run
from .series import add_months, month_end, month_key, month_range, parse_month_label


def _chg(last: float, prev: float) -> float | None:
    return (last / prev - 1) * 100 if prev > 0 else None


def _sign(x, dead=5.0):
    return 0 if x is None or abs(x) < dead else (1 if x > 0 else -1)


def _trend(raw: np.ndarray, proj: np.ndarray, months: list, win: slice) -> float | None:
    eps = 0.5 / np.where(proj > 0, proj, 1.0) * 1e6
    lpm = np.log(raw / np.where(proj > 0, proj, np.nan) * 1e6 + eps)
    des = stats.deseasonalize(np.nan_to_num(lpm), [m.month for m in months])
    s = stats.theil_sen(des[win])
    return (math.exp(12 * s) - 1) * 100 if s == s else None


def verify_row(ctx: Ctx, row, spec: dict) -> dict:
    r = row.result
    lang, project = r["lang"], langs.host(r["lang"])
    w = r["window"]
    ws, we = parse_month_label(w["start"]), parse_month_label(w["end"])
    hist = add_months(ws, -12)
    months = month_range(hist, we)
    out = {"lang": lang, "topic": r["topic"], "tests": []}

    def test(name, status, msg):
        out["tests"].append({"test": name, "status": status, "message": msg})

    # devices (normalized by the same device's edition total)
    dev = {}
    for access in ("desktop", "mobile-web"):
        tot = np.zeros(len(months))
        for a in r["articles"]:
            s = article_series(ctx, project, a["title"], hist, we, gran="monthly", agent="user", access=access)
            tot += np.array([s[m] for m in months], dtype=float)
        ps = project_series(ctx, project, hist, we, gran="monthly", agent="user", access=access)
        pv = np.array([ps[m] for m in months], dtype=float)
        dev[access] = _chg(tot[-12:].sum() / pv[-12:].sum(), tot[-24:-12].sum() / pv[-24:-12].sum()) \
            if pv[-24:-12].sum() > 0 and tot[-24:-12].sum() > 0 else None
        dev[access + "_views_last12"] = float(tot[-12:].sum())
    d, m = dev["desktop"], dev["mobile-web"]
    mob_share = dev["mobile-web_views_last12"] / max(dev["desktop_views_last12"] + dev["mobile-web_views_last12"], 1) * 100
    if d is None or m is None:
        test("devices", "warn", "not enough device data to compare")
    elif _sign(d) and _sign(m) and _sign(d) != _sign(m) and abs(d - m) > 20:
        test("devices", "alert", f"desktop {d:+.0f}% vs mobile web {m:+.0f}%: the devices disagree "
                                 "(bots often inflate desktop)")
    elif abs(d - m) > 25:
        test("devices", "warn", f"desktop {d:+.0f}% vs mobile web {m:+.0f}%: same direction, different size")
    else:
        test("devices", "ok", f"desktop {d:+.0f}% and mobile web {m:+.0f}% agree")
    if mob_share < 15 or mob_share > 95:
        test("mobile_share", "warn", f"mobile web is {mob_share:.0f}% of views; unusual shares often mean bot traffic")

    # bots counted in
    allv = np.zeros(len(months))
    for a in r["articles"]:
        s = article_series(ctx, project, a["title"], hist, we, gran="monthly", agent="all-agents")
        allv += np.array([s[x] for x in months], dtype=float)
    pa = project_series(ctx, project, hist, we, gran="monthly", agent="all-agents")
    pav = np.array([pa[x] for x in months], dtype=float)
    ch_all = _chg(allv[-12:].sum() / pav[-12:].sum(), allv[-24:-12].sum() / pav[-24:-12].sum()) \
        if allv[-24:-12].sum() > 0 else None
    base = r["change"]["change_12m_pct"]
    if ch_all is not None and base is not None and _sign(ch_all) and _sign(base) and _sign(ch_all) != _sign(base):
        test("bots", "alert", f"with bots counted the change is {ch_all:+.0f}% vs {base:+.0f}% humans only")
    elif ch_all is not None:
        test("bots", "ok", f"with bots counted: {ch_all:+.0f}% (humans only {base:+.0f}%)")

    # window trims (from the stored series; no API calls)
    if row.raw is not None:
        n_win = w["months"]
        full = len(row.months)
        t_first = _trend(row.raw, row.proj, row.months, slice(full - n_win + 3, full))
        t_last = _trend(row.raw, row.proj, row.months, slice(full - n_win, full - 3))
        t0 = r["trend"]["pct_per_year"]
        flips = [x for x in (t_first, t_last) if x is not None and _sign(x) and _sign(t0) and _sign(x) != _sign(t0)]
        if flips:
            test("window", "alert", f"trend changes sign when 3 months are trimmed ({t_first:+.0f} / {t_last:+.0f} %/yr "
                                    f"vs {t0:+.0f})")
        else:
            test("window", "ok", f"trend without first 3 months {t_first:+.0f}%/yr, without last 3 {t_last:+.0f}%/yr "
                                  f"(full window {t0:+.0f})")

    # spot check: one month straight from the API vs. our zero-filled daily sums
    a0 = r["articles"][0]
    probe = add_months(ws, 5)
    url = _article_url(project, a0["title"], "all-access", spec["agent"], "monthly", probe, probe)
    try:
        status, body = Client().get_json(url)
        api_v = sum(int(i["views"]) for i in body.get("items", []) if i["timestamp"][:6] == month_key(probe)) \
            if status == 200 else 0
        daily = article_series(ctx, project, a0["title"], probe, month_end(probe), gran="daily",
                               agent=spec["agent"])
        ours = sum(daily.values())
        if abs(api_v - ours) > max(2, 0.01 * api_v):
            test("spot_check", "alert", f"{a0['title']} {month_key(probe)}: API monthly {api_v} vs cached daily sum {ours}")
        else:
            test("spot_check", "ok", f"{a0['title']} {month_key(probe)[:4]}-{month_key(probe)[4:]}: API {api_v} = cached {ours}")
    except ApiError as e:
        test("spot_check", "warn", f"could not re-fetch from the API ({e.status})")

    st = [x["status"] for x in out["tests"]]
    out["verdict"] = "fragile" if "alert" in st else ("mixed" if "warn" in st else "robust")
    return out


def cmd_verify(a) -> int:
    payload, rows = load_run(a.run)
    ctx = Ctx(Client(offline=a.offline), Cache())
    res = [verify_row(ctx, row, payload["spec"]) for row in rows if row.result.get("status") == "ok"]
    ctx.cache.close()
    Path(a.run, "verify.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# verify: {Path(a.run).name}"]
    for v in res:
        lines.append(f"- {v['lang']}/{v['topic']}: **{v['verdict']}**")
        for tst in v["tests"]:
            lines.append(f"  - {tst['status']}: {tst['test']}: {tst['message']}")
    lines.append("robust = all tests pass · mixed = warnings · fragile = the conclusion depends on a device, "
                 "bots or the exact window; say so to the user.")
    print("\n".join(lines))
    return 0


_ = (config, sys)
