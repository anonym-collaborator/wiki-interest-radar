"""Unit tests: dates, statistics, fetching/zero-fill, languages, number checking."""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from wir import langs, stats
from wir.cache import Cache
from wir.check import extract_numbers, run_check
from wir.fetch import Ctx, article_series
from wir.series import add_months, last_complete_month, missing_intervals


# --- series ---------------------------------------------------------------
def test_last_complete_month_respects_loading_lag():
    assert last_complete_month(date(2026, 9, 27)) == date(2026, 8, 1)
    assert last_complete_month(date(2026, 9, 1)) == date(2026, 7, 1)   # August not loaded yet


def test_missing_intervals_daily_and_monthly():
    cov = [(date(2025, 1, 1), date(2025, 1, 10))]
    assert missing_intervals(date(2025, 1, 5), date(2025, 1, 15), cov) == [(date(2025, 1, 11), date(2025, 1, 15))]
    mcov = [(date(2025, 1, 1), date(2025, 3, 1))]
    assert missing_intervals(date(2024, 11, 1), date(2025, 5, 1), mcov, monthly=True) == [
        (date(2024, 11, 1), date(2024, 12, 1)), (date(2025, 4, 1), date(2025, 5, 1))]
    assert add_months(date(2025, 12, 1), 1) == date(2026, 1, 1)


# --- statistics -------------------------------------------------------------
def test_theil_sen_is_robust_to_outliers():
    y = np.arange(30, dtype=float) * 2.0
    y[5] = 500
    assert stats.theil_sen(y) == pytest.approx(2.0, abs=0.05)


def test_mann_kendall_separates_trend_from_noise():
    rng = np.random.default_rng(0)
    trend = np.arange(36) * 0.05 + rng.normal(0, 0.2, 36)
    noise = rng.normal(0, 0.2, 36)
    assert stats.seasonal_mann_kendall(trend)[1] < 0.01
    assert stats.seasonal_mann_kendall(noise)[1] > 0.05


def test_detect_spikes_finds_one_day_event():
    v = np.full(200, 100.0)
    v[120] = 2000
    spike, base = stats.detect_spikes(v)
    assert spike[120] and spike.sum() == 1 and base[120] == pytest.approx(100, rel=0.05)


# --- fetch: zero-fill + partial month --------------------------------------
class FakeClient:
    def __init__(self, items):
        self.items, self.urls, self.requests, self.throttled = items, [], 0, 0

    def get_json(self, url):
        self.urls.append(url)
        return 200, {"items": self.items}


def test_zero_days_are_filled_and_cached(tmp_path):
    items = [{"timestamp": "2025010100", "views": 5}, {"timestamp": "2025010300", "views": 7}]
    ctx = Ctx(FakeClient(items), Cache(tmp_path / "c.sqlite"))
    s = article_series(ctx, "cs.wikipedia.org", "A b", date(2025, 1, 1), date(2025, 1, 4))
    assert s == {date(2025, 1, 1): 5, date(2025, 1, 2): 0, date(2025, 1, 3): 7, date(2025, 1, 4): 0}
    article_series(ctx, "cs.wikipedia.org", "A b", date(2025, 1, 1), date(2025, 1, 4))
    assert len(ctx.client.urls) == 1               # second call served from cache
    assert "/A_b/daily/20250101/20250104" in ctx.client.urls[0]


def test_monthly_drops_partial_month_after_end(tmp_path):
    items = [{"timestamp": "2026070100", "views": 10}, {"timestamp": "2026080100", "views": 20},
             {"timestamp": "2026090100", "views": 3}]   # the API returns the running month too
    ctx = Ctx(FakeClient(items), Cache(tmp_path / "c.sqlite"))
    s = article_series(ctx, "en.wikipedia.org", "X", date(2026, 7, 1), date(2026, 8, 1), gran="monthly")
    assert s == {date(2026, 7, 1): 10, date(2026, 8, 1): 20}


# --- languages -------------------------------------------------------------
def test_language_codes_names_and_aliases():
    assert langs.parse_list("ua, Czech, польська, pl") == ["uk", "cs", "pl"]
    with pytest.raises(langs.UnknownLanguage) as e:
        langs.normalize("xx")
    assert "edition codes" in str(e.value)
    assert langs.host("nan") == "zh-min-nan.wikipedia.org"


# --- check -------------------------------------------------------------------
def _payload():
    row = {"status": "ok", "lang": "cs", "lang_name": "Czech", "topic": "t",
           "level": {"views_per_month_last12": 183.2, "views_per_million_last12": 3.08,
                     "views_per_million_last3": 2.1, "views_last12_total": 2198, "median_daily_views_last12": 5},
           "change": {"change_12m_pct": -47.0, "change_12m_raw_pct": -53.6, "project_change_12m_pct": -12.6,
                      "yoy_same_months_pct": -44.8, "change_12m_ex_spikes_pct": -47.7},
           "trend": {"pct_per_year": -40.0, "ci95": [-48.0, -29.0], "range_pct": [-47.0, -40.0]},
           "spikes": {"share_pct": 10.8, "days": [{"date": "2025-04-14", "views": 508, "baseline": 12}]},
           "bots": {"share_pct_last12": 29.7}, "seasonality": {"peak_ratio": 1.4}, "redirects": {},
           "articles": [], "checks": []}
    gap = {"status": "no_article", "lang": "pl", "lang_name": "Polish", "topic": "t"}
    return {"rows": [gap, row], "ranking": None}


def test_extract_numbers_handles_uk_decimals_and_units():
    nums = extract_numbers("частка 3,08 на 1 млн, тренд −40%/рік, 8 824 переглядів, 14.04.2025, 24 міс.")
    got = [(x, u) for x, _, u in nums]
    assert (3.08, "pm") in got and (-40.0, "trend") in got and (8824.0, "count") in got
    assert all(x != 14.04 and x != 24 for x, _ in got)


def test_extract_numbers_formats_seen_in_haiku_answers():
    # eval iteration 2 (astro-uk): "на 1 мільйон" was read as a raw count, "12-місячне" as a number
    got = [(x, u) for x, _, u in extract_numbers("9,89 переглядів на 1 мільйон переглядів; 12-місячне "
                                                "зниження -46%; 6-month YoY; 17.5 views per million")]
    assert (9.89, "pm") in got and (17.5, "pm") in got and (-46.0, "pct") in got
    assert all(x not in (12, 6) for x, _ in got)


def test_check_warns_about_text_in_another_script():
    res = run_check(_payload(), "У чеській частка впала на 47%, довіра середня. Весь談站維基百科 змінився. "
                                "У польській статті немає.")
    assert any("another script" in w for w in res["warnings"])


def test_check_accepts_supported_and_rejects_invented_numbers():
    good = "У чеській частка впала на 47% (тренд −40%/рік, 95% ДІ −48…−29), довіра середня. У польській статті немає."
    assert run_check(_payload(), good)["ok"]
    bad = run_check(_payload(), "У чеській падає на 30% на рік, у польській теж знижується (-12%).")
    assert not bad["ok"] and {u["number"] for u in bad["unsupported_numbers"]} == {30.0, -12.0}
    assert any("pl" in w for w in bad["warnings"])


def test_check_catches_wrong_direction():
    # matching by absolute value alone accepted "grew 47%" when the data say -47%
    res = run_check(_payload(), "У чеській частка зросла на 47%, довіра середня. У польській статті немає.")
    assert not res["ok"] and [c["number"] for c in res["direction_conflicts"]] == [47.0]
    assert not run_check(_payload(), "Czech: +47% over 12 months, medium confidence. Polish: no article.")["ok"]
    ok = ("Czech fell 47% and is down 53.6% in raw views; bots 29.7%, up to 10.8% in spike days; "
          "не зростає: −40%/рік; за пів року на 44.8% менше. Medium confidence. Polish: no article.")
    res = run_check(_payload(), ok)
    assert res["ok"], res
