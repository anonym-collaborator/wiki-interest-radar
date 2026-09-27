"""Shared fixtures: a synthetic pageview generator patched in place of the API."""
from __future__ import annotations

import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from wir import analysis  # noqa: E402
from wir.resolve import Article, Member  # noqa: E402
from wir.series import day_range, month_end, month_range  # noqa: E402

T0 = date(2023, 9, 1)


class Synthetic:
    """views(d) = base * (1+growth)^years * season[month] * noise + events."""

    def __init__(self, base=200.0, growth=0.0, season=None, noise=0.08, seed=1, events=None,
                 created=None, project_growth=0.0, bot_share=0.2):
        self.base, self.growth, self.noise = base, growth, noise
        self.season = season or {}
        self.events = events or {}          # {date: extra views}
        self.created = created              # date the article appears
        self.project_growth = project_growth
        self.bot_share = bot_share
        self.rng = np.random.default_rng(seed)
        self._cache: dict[date, float] = {}

    def article(self, d: date) -> float:
        if d not in self._cache:
            if self.created and d < self.created:
                v = 0.0
            else:
                yrs = (d - T0).days / 365.25
                v = self.base * (1 + self.growth) ** yrs * self.season.get(d.month, 1.0)
                v *= math.exp(self.rng.normal(0, self.noise))
                v += self.events.get(d, 0.0)
            self._cache[d] = round(v)
        return self._cache[d]

    def project(self, d: date) -> float:
        yrs = (d - T0).days / 365.25
        return 5e6 * (1 + self.project_growth) ** yrs


def _series(fn, start, end, gran, factor=1.0):
    if gran == "daily":
        return {d: int(fn(d) * factor) for d in day_range(start, end)}
    return {m: int(sum(fn(d) for d in day_range(m, month_end(m))) * factor) for m in month_range(start, end)}


@pytest.fixture
def fake_api(monkeypatch):
    """Patch analysis.* fetchers with a Synthetic model; returns a setter."""
    state = {"model": Synthetic()}

    def article_series(ctx, project, title, start, end, *, gran="daily", agent="user", access="all-access"):
        m = state["model"]
        if title.startswith("Redirect"):
            return _series(lambda d: 0, start, end, gran)
        factor = 1.0 / (1 - m.bot_share) if agent == "all-agents" else 1.0
        return _series(m.article, start, end, gran, factor)

    def project_series(ctx, project, start, end, *, gran="daily", agent="user", access="all-access"):
        return _series(state["model"].project, start, end, gran)

    monkeypatch.setattr(analysis, "article_series", article_series)
    monkeypatch.setattr(analysis, "project_series", project_series)

    def use(model: Synthetic):
        state["model"] = model

    return use


def make_topic(lang="cs", title="Test article", present=True):
    art = Article(lang, title, True, 5000, []) if present else None
    m = Member(query="test topic", qid="Q1", label="test topic", description="synthetic", articles={lang: art})
    return analysis.Topic("test topic", [m])


def options(months=24):
    end = date(2026, 8, 1)
    start = date(2024, 9, 1) if months == 24 else None
    return analysis.Options(start, end)
