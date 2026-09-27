"""End-to-end analysis on synthetic series with known answers."""
from __future__ import annotations

from datetime import date, timedelta

from conftest import Synthetic, make_topic, options
from wir import analysis

SEPT_PEAK = {9: 3.0, 10: 1.3, 6: 0.5, 7: 0.4, 8: 0.5}


def run(model, fake_api, present=True):
    fake_api(model)
    row = analysis.analyze_row(ctx=None, topic=make_topic(present=present), lang="cs", opt=options())
    return row.result


def test_declining_with_school_seasonality_is_declining_high(fake_api):
    r = run(Synthetic(base=300, growth=-0.30, season=SEPT_PEAK, noise=0.06), fake_api)
    assert r["verdict"] == "declining"
    assert r["confidence"] == "high"
    lo, hi = r["trend"]["ci95"]
    assert lo <= -30 <= hi + 5, r["trend"]          # true slope inside (or at the edge of) the CI
    assert r["seasonality"]["recurring"] is True
    assert r["seasonality"]["peak_month"] == "Sep"


def test_flat_seasonal_series_is_flat(fake_api):
    r = run(Synthetic(base=300, growth=0.0, season=SEPT_PEAK, noise=0.06, seed=3), fake_api)
    assert r["verdict"] == "flat", (r["change"], r["trend"])


def test_growth_is_growing(fake_api):
    r = run(Synthetic(base=150, growth=0.40, noise=0.08, seed=5), fake_api)
    assert r["verdict"] == "growing"
    assert r["trend"]["pct_per_year"] > 20


def test_one_month_event_is_not_trusted(fake_api):
    # flat interest + a three-week event in the last 12 months (ramps up, so no single-day spike)
    ev = {date(2026, 4, 1) + timedelta(days=i): 2500 * (1 - abs(i - 10) / 11) for i in range(21)}
    r = run(Synthetic(base=120, growth=0.0, noise=0.08, seed=7, events=ev), fake_api)
    ids = {c["id"]: c["status"] for c in r["checks"]}
    assert ids.get("concentration") in ("alert", "warn")
    assert not (r["verdict"] == "growing" and r["confidence"] == "high")


def test_single_day_spike_is_removed_from_trend(fake_api):
    ev = {date(2025, 11, 3): 20000}
    r = run(Synthetic(base=200, growth=0.0, noise=0.05, seed=9, events=ev), fake_api)
    assert r["spikes"]["days"] and r["spikes"]["days"][0]["date"] == "2025-11-03"
    assert r["verdict"] in ("flat", "mixed")
    assert abs(r["trend"]["pct_per_year"]) < 15


def test_new_article_inside_window_is_low_confidence(fake_api):
    r = run(Synthetic(base=200, growth=0.0, noise=0.05, created=date(2025, 3, 1)), fake_api)
    statuses = {c["id"]: c["status"] for c in r["checks"]}
    assert statuses.get("article_age") == "alert"
    assert r["confidence"] == "low"


def test_platform_decline_is_normalized_away(fake_api):
    # the article loses raw views only because the whole edition shrinks by 30%/yr
    m = Synthetic(base=300, growth=-0.30, noise=0.04, seed=11, project_growth=-0.30)
    r = run(m, fake_api)
    assert r["change"]["change_12m_raw_pct"] < -20
    assert abs(r["change"]["change_12m_pct"]) < 8
    assert r["verdict"] == "flat"


def test_missing_article_is_content_gap(fake_api):
    r = run(Synthetic(), fake_api, present=False)
    assert r["status"] == "no_article" and r["verdict"] == "no_article"


def test_low_volume_is_flagged(fake_api):
    r = run(Synthetic(base=3, growth=-0.3, noise=0.3, seed=13), fake_api)
    assert any(c["id"] == "volume" and c["status"] in ("warn", "alert") for c in r["checks"])
