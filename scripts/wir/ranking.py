"""Rank audiences (topic x language rows) by user-chosen criteria, with a
sensitivity check across presets so a fragile ranking is visible."""
from __future__ import annotations

import math

PRESETS = {
    "balanced": {"size": 0.4, "momentum": 0.4, "trust": 0.2},
    "momentum": {"size": 0.2, "momentum": 0.6, "trust": 0.2},
    "size": {"size": 0.6, "momentum": 0.2, "trust": 0.2},
}
TRUST_SCORE = {"high": 1.0, "medium": 0.5, "low": 0.0}
CRITERIA_TEXT = {
    "size": "share of the edition's attention (views per million, last 12 months, log scale)",
    "momentum": "trend %/year (spike-cleaned, deseasonalized)",
    "trust": "confidence of the trend (high=1, medium=0.5, low=0)",
}


def parse_weights(spec: str | None, preset: str) -> dict[str, float]:
    if not spec:
        return dict(PRESETS[preset])
    w = {}
    for part in spec.split(","):
        k, _, v = part.partition("=")
        k = k.strip().lower()
        if k not in CRITERIA_TEXT:
            raise ValueError(f"Unknown criterion '{k}'. Use size, momentum, trust (e.g. size=0.5,momentum=0.3,trust=0.2).")
        w[k] = float(v)
    for k in CRITERIA_TEXT:
        w.setdefault(k, 0.0)
    s = sum(w.values())
    if s <= 0:
        raise ValueError("Weights must sum to a positive number.")
    return {k: v / s for k, v in w.items()}


def _minmax(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return [0.5 for _ in vals]
    return [(v - lo) / (hi - lo) for v in vals]


def _scores(rows: list[dict], w: dict[str, float]) -> list[float]:
    size = _minmax([math.log10(max(r["level"]["views_per_million_last12"], 1e-3)) for r in rows])
    mom = _minmax([r["trend"]["pct_per_year"] or 0.0 for r in rows])
    tru = [TRUST_SCORE.get(r["confidence"], 0.0) for r in rows]
    return [w["size"] * a + w["momentum"] * b + w["trust"] * c for a, b, c in zip(size, mom, tru)]


def rank(results: list[dict], preset: str = "balanced", weights: str | None = None) -> dict | None:
    rows = [r for r in results if r.get("status") == "ok" and r.get("verdict") != "insufficient_data"]
    if len(rows) < 2:
        return None
    w = parse_weights(weights, preset)
    sc = _scores(rows, w)
    order = sorted(range(len(rows)), key=lambda i: -sc[i])
    table = [{"rank": k + 1, "topic": rows[i]["topic"], "lang": rows[i]["lang"],
              "score": round(sc[i], 3), "verdict": rows[i]["verdict"],
              "confidence": rows[i]["confidence"]} for k, i in enumerate(order)]
    # sensitivity: does the leader / top-3 survive other presets?
    tops = {}
    for name, pw in PRESETS.items():
        s2 = _scores(rows, pw)
        o2 = sorted(range(len(rows)), key=lambda i: -s2[i])
        tops[name] = [f"{rows[i]['lang']}:{rows[i]['topic']}" for i in o2[:3]]
    leaders = {v[0] for v in tops.values()}
    top3_sets = {frozenset(v) for v in tops.values()}
    stable = "stable" if len(leaders) == 1 and len(top3_sets) == 1 else (
        "leader stable, order below varies" if len(leaders) == 1 else "unstable: depends on weights")
    return {"weights": {k: round(v, 2) for k, v in w.items()},
            "preset": None if weights else preset,
            "criteria": {k: CRITERIA_TEXT[k] for k in w if w[k] > 0},
            "table": table, "sensitivity": {"top3_by_preset": tops, "verdict": stable}}
