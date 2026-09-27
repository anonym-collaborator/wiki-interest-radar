"""Per (topic x language) metrics, trust checks, verdict and confidence.

Everything the agent will quote is computed here, so a cheap model never has
to do arithmetic or statistics itself.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from . import config, langs, stats
from .i18n import MONTHS_EN, MONTHS_UK_LOC, render_check
from .fetch import Ctx, article_series, project_series
from .resolve import Member
from .series import (add_months, daily_to_monthly, month_end, month_label, month_range,
                     parse_month_label)

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass
class Options:
    window_start: date
    window_end: date
    agent: str = "user"
    access: str = "all-access"
    redirects: bool = True

    @property
    def hist_start(self) -> date:
        return add_months(self.window_start, -12)

    @property
    def n_months(self) -> int:
        return len(month_range(self.window_start, self.window_end))


@dataclass
class Topic:
    name: str
    members: list[Member]
    kind: str = "topic"  # topic | basket

    @property
    def key(self) -> str:
        return "-".join("".join(ch if ch.isalnum() else " " for ch in self.name.lower()).split())[:40]


@dataclass
class Row:
    topic: Topic
    lang: str
    result: dict = field(default_factory=dict)
    months: list[date] = field(default_factory=list)
    raw: np.ndarray | None = None
    proj: np.ndarray | None = None
    long_months: list[date] = field(default_factory=list)
    long_pm: np.ndarray | None = None
    spike_months: list[date] = field(default_factory=list)


def _pct(a: float, b: float) -> float | None:
    if b is None or b <= 0 or a is None:
        return None
    return (a / b - 1.0) * 100.0


def _r(x, nd=1):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), nd)


def _sign(x: float | None, dead: float = 5.0) -> int:
    if x is None or abs(x) < dead:
        return 0
    return 1 if x > 0 else -1


def load_breaks() -> list[dict]:
    return json.loads((config.ASSETS / "known_breaks.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# data assembly
# ---------------------------------------------------------------------------

def _row_data(ctx: Ctx, topic: Topic, lang: str, opt: Options) -> dict:
    project = langs.host(lang)
    months = month_range(opt.hist_start, opt.window_end)
    day0, day1 = opt.hist_start, month_end(opt.window_end)
    long0 = date(config.DATA_START.year, config.DATA_START.month, 1)

    daily_total = None
    raw = np.zeros(len(months))
    user_long = np.zeros(len(month_range(long0, opt.window_end)))
    all_long = np.zeros_like(user_long)
    per_member = []
    articles = []
    missing = []
    redirect_views = 0.0
    for m in topic.members:
        art = m.articles.get(lang)
        if art is None:
            missing.append(m.label or m.query)
            continue
        d = article_series(ctx, project, art.title, day0, day1, gran="daily",
                           agent=opt.agent, access=opt.access)
        dv = np.array([d[x] for x in sorted(d)], dtype=float)
        daily_total = dv if daily_total is None else daily_total + dv
        mon = daily_to_monthly(d)
        member_raw = np.array([mon.get(x, 0) for x in months], dtype=float)
        red_list = art.redirects if opt.redirects else []
        red_total = np.zeros(len(months))
        for rt in red_list:
            rs = article_series(ctx, project, rt, opt.hist_start, opt.window_end, gran="monthly",
                                agent=opt.agent, access=opt.access)
            red_total += np.array([rs[x] for x in months], dtype=float)
        redirect_views += float(red_total[-12:].sum())
        member_raw = member_raw + red_total
        raw += member_raw
        ul = article_series(ctx, project, art.title, long0, opt.window_end, gran="monthly",
                            agent="user", access="all-access")
        al = article_series(ctx, project, art.title, long0, opt.window_end, gran="monthly",
                            agent="all-agents", access="all-access")
        user_long += np.array([ul[x] for x in sorted(ul)], dtype=float)
        all_long += np.array([al[x] for x in sorted(al)], dtype=float)
        first = next((x for x in sorted(al) if al[x] > 0), None)
        per_member.append({"label": m.label or m.query, "qid": m.qid, "title": art.title,
                           "raw": member_raw, "first_seen": first, "length": art.length,
                           "redirects": len(red_list), "source": art.source,
                           "ambiguous": m.ambiguous, "description": m.description})
        articles.append(art)
    pd_ = project_series(ctx, project, day0, day1, gran="daily", agent=opt.agent, access=opt.access)
    pmon = daily_to_monthly(pd_)
    proj = np.array([pmon.get(x, 0) for x in months], dtype=float)
    plong = project_series(ctx, project, long0, opt.window_end, gran="monthly",
                           agent="user", access="all-access")
    return {"project": project, "months": months, "raw": raw, "proj": proj,
            "daily": daily_total, "days": [day0 + timedelta(days=i) for i in range((day1 - day0).days + 1)],
            "members": per_member, "missing": missing, "redirect_views_last12": redirect_views,
            "user_long": user_long, "all_long": all_long,
            "long_months": month_range(long0, opt.window_end),
            "proj_long": np.array([plong[x] for x in sorted(plong)], dtype=float)}


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def analyze_row(ctx: Ctx, topic: Topic, lang: str, opt: Options) -> Row:
    row = Row(topic, lang)
    base = {"topic": topic.name, "topic_key": topic.key, "kind": topic.kind, "lang": lang,
            "lang_name": langs.english_name(lang), "project": langs.host(lang),
            "window": {"start": month_label(opt.window_start), "end": month_label(opt.window_end),
                       "months": opt.n_months}}
    if not any(m.articles.get(lang) for m in topic.members):
        hints = sorted({h for m in topic.members for h in m.gap_hints.get(lang, [])})
        base.update({"status": "no_article", "verdict": "no_article", "confidence": None,
                     "missing_members": [m.label or m.query for m in topic.members],
                     "mentioned_in": hints,
                     "reasons": ["No article on this topic exists in this edition (content gap, "
                                 "not zero interest). Nothing to measure."]})
        row.result = base
        return row

    d = _row_data(ctx, topic, lang, opt)
    months, raw, proj = d["months"], d["raw"], d["proj"]
    n_win = opt.n_months
    win = slice(len(months) - n_win, len(months))
    last12, prev12 = slice(len(months) - 12, len(months)), slice(len(months) - 24, len(months) - 12)
    proj_safe = np.where(proj > 0, proj, np.nan)
    pm = raw / proj_safe * 1e6

    level = {
        "views_per_month_last12": _r(raw[last12].mean(), 1),
        "views_per_million_last12": _r(raw[last12].sum() / proj[last12].sum() * 1e6, 3),
        "views_per_million_last3": _r(raw[-3:].sum() / proj[-3:].sum() * 1e6, 3),
        "views_last12_total": int(raw[last12].sum()),
    }
    daily, days = d["daily"], d["days"]
    last12_start = months[last12.start]
    dmask12 = np.array([x >= last12_start for x in days])
    level["median_daily_views_last12"] = _r(float(np.median(daily[dmask12])), 1)

    pm_last = raw[last12].sum() / proj[last12].sum()
    pm_prev = raw[prev12].sum() / proj[prev12].sum() if proj[prev12].sum() > 0 else None
    change = {
        "change_12m_pct": _r(_pct(pm_last, pm_prev) if pm_prev else None),
        "change_12m_raw_pct": _r(_pct(raw[last12].sum(), raw[prev12].sum())),
        "project_change_12m_pct": _r(_pct(proj[last12].sum(), proj[prev12].sum())),
    }
    yoy = []
    for k in range(len(months) - 6, len(months)):
        a, b = pm[k], pm[k - 12]
        if np.isfinite(a) and np.isfinite(b) and b > 0:
            yoy.append(a / b - 1.0)
    change["yoy_same_months_pct"] = _r(float(np.median(yoy)) * 100 if yoy else None)

    # spikes on the daily series (main articles), counted inside the window only
    spike, baseline = stats.detect_spikes(daily)
    win_start_day = opt.window_start
    in_win = np.array([x >= win_start_day for x in days])
    excess = np.where(spike & in_win, daily - baseline, 0.0)
    total_win = daily[in_win].sum()
    spike_share = float(excess.sum() / total_win * 100) if total_win > 0 else 0.0
    top_idx = [i for i in np.argsort(-excess) if excess[i] > 0][:3]
    spike_days = [{"date": days[i].isoformat(), "views": int(daily[i]),
                   "baseline": int(round(baseline[i]))} for i in sorted(top_idx)]
    clean_daily = np.where(spike, np.minimum(daily, baseline), daily)
    clean_mon = {}
    for x, v in zip(days, clean_daily):
        k = x.replace(day=1)
        clean_mon[k] = clean_mon.get(k, 0.0) + v
    dmon = {}
    for x, v in zip(days, daily):
        k = x.replace(day=1)
        dmon[k] = dmon.get(k, 0.0) + v
    raw_clean = raw - np.array([dmon.get(m, 0.0) - clean_mon.get(m, 0.0) for m in months])
    change["change_12m_ex_spikes_pct"] = _r(_pct(raw_clean[last12].sum() / proj[last12].sum(),
                                                 raw_clean[prev12].sum() / proj[prev12].sum())
                                            if proj[prev12].sum() > 0 and raw_clean[prev12].sum() > 0 else None)
    row.spike_months = sorted({days[i].replace(day=1) for i in np.nonzero(spike & in_win)[0]})

    # trend: Theil-Sen on deseasonalized log(per-million), spike-cleaned
    eps = 0.5 / np.where(proj > 0, proj, 1.0) * 1e6
    lpm = np.log(np.nan_to_num(raw_clean / proj_safe * 1e6, nan=0.0) + eps)
    cal = [m.month for m in months]
    des = stats.deseasonalize(lpm, cal)
    y = des[win]
    slope, lo, hi = stats.trend_with_ci(lpm, cal, win)
    to_pct = lambda s: (math.exp(12 * s) - 1) * 100 if s == s else None  # noqa: E731
    z_mk, p_mk = (stats.seasonal_mann_kendall(lpm[win]) if n_win >= 24
                  else stats.mann_kendall(y))
    trend = {"pct_per_year": _r(to_pct(slope)), "ci95": [_r(to_pct(lo)), _r(to_pct(hi))],
             "mann_kendall_p": _r(p_mk, 4),
             "test": "seasonal Mann-Kendall" if n_win >= 24 else "Mann-Kendall on deseasonalized"}
    estimates = [v for v in (change["change_12m_pct"], change["yoy_same_months_pct"],
                             trend["pct_per_year"]) if v is not None]
    trend["range_pct"] = [min(estimates), max(estimates)] if estimates else None
    # does the trend survive without the most recent 3 months?
    y_trim = des[win][:-3]
    trend["pct_per_year_without_last3"] = _r(to_pct(stats.theil_sen(y_trim))) if len(y_trim) >= 9 else None

    # seasonality only counts if the same calendar month peaks in >= 2 separate years;
    # a single event (an eclipse, an election) must not be mistaken for a season.
    pm0 = np.nan_to_num(pm, nan=0.0)
    prof = stats.seasonal_profile(pm0, cal)
    seasonality = {}
    if prof:
        pk = max(prof, key=prof.get)
        tops = []
        for b0 in range(len(months) % 12, len(months) - 11, 12):
            blk = pm0[b0:b0 + 12]
            order = np.argsort(-blk)[:2]
            tops.append({months[b0 + i].month for i in order})
        recurring = sum(1 for tset in tops if pk in tset) >= 2
        gi = int(np.argmax(pm0))
        seasonality = {"peak_month": MONTH_NAMES[pk - 1], "peak_ratio": _r(prof[pk], 2),
                       "recurring": recurring, "largest_month": month_label(months[gi])}

    # attention concentrated in one month of the last 12 (multi-week events that
    # daily spike detection cannot see because the baseline rises with them)
    l_raw, l_proj = raw[last12], proj[last12]
    p_raw, p_proj = raw[prev12], proj[prev12]
    concentration = None
    if l_raw.sum() > 0:
        ti = int(np.argmax(l_raw))
        share = float(l_raw[ti] / l_raw.sum() * 100)
        wo = None
        if p_raw.sum() - p_raw[ti] > 0:
            wo = _pct((l_raw.sum() - l_raw[ti]) / (l_proj.sum() - l_proj[ti]),
                      (p_raw.sum() - p_raw[ti]) / (p_proj.sum() - p_proj[ti]))
        concentration = {"top_month": month_label(months[last12.start + ti]), "top_month_share_pct": _r(share),
                         "change_12m_without_top_month_pct": _r(wo)}

    ul, al = d["user_long"], d["all_long"]
    bot_share = float(1 - ul[-12:].sum() / al[-12:].sum()) * 100 if al[-12:].sum() > 0 else None
    red_share = (d["redirect_views_last12"] / raw[last12].sum() * 100) if raw[last12].sum() > 0 else 0.0

    members_out = []
    for mm in d["members"]:
        mraw = mm["raw"]
        ch = _pct(mraw[last12].sum() / proj[last12].sum(), mraw[prev12].sum() / proj[prev12].sum()) \
            if mraw[prev12].sum() > 0 else None
        members_out.append({"label": mm["label"], "qid": mm["qid"], "title": mm["title"],
                            "source": mm["source"], "length_bytes": mm["length"],
                            "redirects": mm["redirects"],
                            "first_seen": month_label(mm["first_seen"]) if mm["first_seen"] else None,
                            "share_pct": _r(mraw[last12].sum() / raw[last12].sum() * 100
                                            if raw[last12].sum() > 0 else None),
                            "change_12m_pct": _r(ch)})

    res = {**base, "status": "ok",
           "articles": members_out, "missing_members": d["missing"],
           "level": level, "change": change, "trend": trend, "seasonality": seasonality,
           "spikes": {"share_pct": _r(spike_share), "days": spike_days,
                      "months": [month_label(m) for m in row.spike_months]},
           "bots": {"share_pct_last12": _r(bot_share)},
           "concentration": concentration,
           "redirects": {"share_pct_last12": _r(red_share), "count": sum(m["redirects"] for m in members_out)},
           "breaks": _breaks_for(lang, opt)}
    _judge(res, topic, d, opt)
    row.result = res
    row.months, row.raw, row.proj = months, raw, proj
    row.long_months = d["long_months"]
    pl = d["proj_long"]
    row.long_pm = np.where(pl > 0, d["user_long"] / np.where(pl > 0, pl, 1) * 1e6, np.nan)
    return row


def _breaks_for(lang: str, opt: Options) -> list[dict]:
    out = []
    for b in load_breaks():
        s, e = parse_month_label(b["start"]), parse_month_label(b["end"])
        if e < opt.hist_start or s > opt.window_end:
            continue
        scope = b["projects"]
        if scope == "*" or lang in scope:
            out.append({"id": b["id"], "start": b["start"], "end": b["end"],
                        "specific": scope != "*", "note": b["note"], "note_uk": b.get("note_uk"),
                        "source": b.get("source")})
    return out


# ---------------------------------------------------------------------------
# trust checks -> verdict + confidence
# ---------------------------------------------------------------------------

def _judge(res: dict, topic: Topic, d: dict, opt: Options) -> None:
    checks: list[dict] = []

    def add(cid: str, status: str, key: str, **params) -> None:
        c = {"id": cid, "status": status, "key": key, "params": params}
        c["message"] = render_check(c, "en")
        checks.append(c)

    def pct(x) -> str:
        return f"{x:+.0f}" if x is not None else "n/a"

    lv, ch, tr = res["level"], res["change"], res["trend"]
    total12 = lv["views_last12_total"]
    med = lv["median_daily_views_last12"] or 0
    if total12 < 365:
        add("volume", "alert", "volume_alert", total=total12)
    elif med < 10:
        add("volume", "warn", "volume_warn", med=f"{med:g}")
    else:
        add("volume", "ok", "volume_ok", med=f"{med:g}")

    sp = res["spikes"]["share_pct"] or 0
    ex = ch["change_12m_ex_spikes_pct"]
    top = res["spikes"]["days"]
    top_txt = ", ".join(f"{s['date']}: {s['views']} vs ~{s['baseline']}" for s in top[:2])
    if _sign(ex) != 0 and _sign(ch["change_12m_pct"]) != 0 and _sign(ex) != _sign(ch["change_12m_pct"]):
        add("spikes", "alert", "spikes_flip", top=top_txt)
    elif sp > 30:
        add("spikes", "alert", "spikes_alert", share=f"{sp:.0f}", top=top_txt)
    elif sp > 10:
        add("spikes", "warn", "spikes_warn", share=f"{sp:.0f}", top=top_txt)
    elif top:
        add("spikes", "ok", "spikes_small", share=f"{sp:.1f}", top=top_txt)
    else:
        add("spikes", "ok", "spikes_none")

    lo, hi = tr["ci95"]
    d_trend = 0
    if lo is not None and hi is not None:
        d_trend = 1 if lo > 0 else (-1 if hi < 0 else 0)
    s_change = _sign(ch["change_12m_pct"])
    insufficient = total12 < 100 or lo is None
    firsts = [m["first_seen"] for m in d["members"] if m["first_seen"]]
    newest = max(firsts) if firsts else None
    if newest and newest > add_months(opt.window_end, -11):
        insufficient = True

    c12_abs, tr_abs = abs(ch["change_12m_pct"] or 0), abs(tr["pct_per_year"] or 0)
    if insufficient:
        verdict = "insufficient_data"
    elif d_trend != 0 and s_change == d_trend:
        verdict = "growing" if d_trend > 0 else "declining"
    elif c12_abs < 10 and tr_abs < 10:
        verdict = "flat"
    else:
        verdict = "mixed"
    if verdict == "mixed":
        add("agreement", "alert", "agreement_alert", c12=pct(ch["change_12m_pct"]),
            tr=pct(tr["pct_per_year"]), lo=pct(lo), hi=pct(hi))
    elif verdict in ("growing", "declining"):
        add("agreement", "ok", "agreement_ok", a=pct(tr["range_pct"][0]), b=pct(tr["range_pct"][1]))
    if lo is not None and hi is not None and hi - lo > 60:
        add("precision", "warn", "precision_warn", lo=pct(lo), hi=pct(hi))

    y6, c12 = ch["yoy_same_months_pct"], ch["change_12m_pct"]
    if y6 is not None and c12 is not None and verdict != "insufficient_data":
        if _sign(y6) and _sign(c12) and _sign(y6) != _sign(c12):
            add("momentum", "warn", "momentum_turn", y6=pct(y6), c12=pct(c12))
        elif _sign(c12) and abs(y6) < abs(c12) / 2 and abs(c12) - abs(y6) >= 15:
            add("momentum", "info", "momentum_slowing", y6=pct(y6), c12=pct(c12))
        elif _sign(y6) and abs(y6) > 2 * abs(c12) and abs(y6) - abs(c12) >= 15:
            add("momentum", "info", "momentum_accel", y6=pct(y6), c12=pct(c12))

    rc, pc = ch["change_12m_raw_pct"], ch["project_change_12m_pct"]
    if _sign(rc) != 0 and _sign(ch["change_12m_pct"]) != 0 and _sign(rc) != _sign(ch["change_12m_pct"]):
        add("normalization", "warn", "norm_warn", rc=pct(rc), c12=pct(ch["change_12m_pct"]), pc=pct(pc))
    elif pc is not None and abs(pc) >= 15:
        add("normalization", "info", "norm_info", project=res["project"], pc=pct(pc))

    bs = res["bots"]["share_pct_last12"]
    if bs is not None and bs > 50:
        add("bots", "warn", "bots_warn", share=f"{bs:.0f}")
    elif bs is not None and bs > 35:
        add("bots", "info", "bots_info", share=f"{bs:.0f}")

    if newest:
        if newest >= opt.window_start:
            add("article_age", "alert", "age_alert", first=month_label(newest))
        elif newest >= opt.hist_start:
            add("article_age", "warn", "age_warn", first=month_label(newest))

    conc = res.get("concentration")
    if conc and (conc["top_month_share_pct"] or 0) > 30:
        wo, c12v = conc["change_12m_without_top_month_pct"], ch["change_12m_pct"]
        if wo is not None and c12v is not None and _sign(c12v) and (
                _sign(wo) != _sign(c12v) or abs(wo) < 0.4 * abs(c12v)):
            add("concentration", "alert", "conc_alert", month=conc["top_month"],
                share=f"{conc['top_month_share_pct']:.0f}", c12=pct(c12v), wo=pct(wo))
        else:
            add("concentration", "warn", "conc_warn", month=conc["top_month"],
                share=f"{conc['top_month_share_pct']:.0f}")
    t3, t0 = tr.get("pct_per_year_without_last3"), tr["pct_per_year"]
    if t3 is not None and t0 is not None and _sign(t0) and _sign(t3) != _sign(t0):
        add("recent_months", "warn", "trim_warn", t0=pct(t0), t3=pct(t3))

    seas = res["seasonality"]
    if seas and not seas.get("recurring") and (seas.get("peak_ratio") or 0) >= 1.5:
        add("seasonality", "info", "oneoff_info", month=seas["largest_month"])
    if seas and seas.get("recurring") and (seas.get("peak_ratio") or 0) >= 1.5:
        mi = MONTH_NAMES.index(seas["peak_month"])
        add("seasonality", "info", "season_info", peak_en=MONTHS_EN[mi], peak_uk=MONTHS_UK_LOC[mi],
            ratio=f"{seas['peak_ratio']:g}")

    for b in res["breaks"]:
        add("data_break", "warn" if b["specific"] else "info", "break", start=b["start"], end=b["end"],
            note=b["note"], note_uk=b.get("note_uk") or b["note"])

    if len(d["members"]) > 1:
        signs = [_sign(m["change_12m_pct"]) for m in res["articles"] if m["change_12m_pct"] is not None]
        agree = sum(1 for s in signs if s == s_change) / len(signs) if signs and s_change else None
        if agree is not None and agree < 2 / 3:
            add("basket", "warn", "basket_warn", pct=f"{agree * 100:.0f}")
        loo_flip = []
        for m in d["members"]:
            rest = d["raw"] - m["raw"]
            p_last = rest[-12:].sum() / d["proj"][-12:].sum()
            p_prev = rest[-24:-12].sum() / d["proj"][-24:-12].sum() if rest[-24:-12].sum() > 0 else None
            if p_prev and s_change and _sign(_pct(p_last, p_prev)) not in (0, s_change):
                loo_flip.append(m["label"])
        if loo_flip:
            add("basket", "alert", "basket_alert", label=loo_flip[0])
    if res["missing_members"]:
        add("coverage", "info", "coverage_info", items=", ".join(res["missing_members"]))
    rs = res["redirects"]["share_pct_last12"]
    if rs and rs > 25:
        add("redirects", "info", "redirects_info", share=f"{rs:.0f}")
    for m in d["members"]:
        if m["ambiguous"]:
            add("ambiguity", "warn", "ambiguity_warn", label=m["label"], qid=m["qid"], desc=m["description"])
        if m["source"] == "user":
            add("proxy", "info", "proxy_info", title=m["title"])

    alerts = [c for c in checks if c["status"] == "alert"]
    warns = [c for c in checks if c["status"] == "warn"]
    confidence = "low" if alerts else ("medium" if len(warns) >= 2 else "high")
    if verdict == "insufficient_data":
        confidence = "low"
    res.update({"verdict": verdict, "confidence": confidence, "checks": checks,
                "reasons": [c["message"] for c in alerts + warns]})


def analyze(ctx: Ctx, topics: list[Topic], codes: list[str], opt: Options) -> list[Row]:
    rows = []
    for t in topics:
        for c in codes:
            rows.append(analyze_row(ctx, t, c, opt))
    return rows
