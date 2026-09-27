# Metrics reference

All figures are computed by `scripts/wir/analysis.py` from the Wikimedia Analytics API
(`per-article` and `aggregate` endpoints), agent `user` and access `all-access` unless the run says otherwise.

## Series

- Article views: daily views of the article, zero-filled (the API omits zero days) + monthly views of its
  main-namespace redirects (disable with `--no-redirects`). A basket sums its member articles per edition.
- Edition views: the `aggregate` total of the same language edition, same agent/access.
- Per 1M: `article views / edition views × 1,000,000`. This is the share of the edition's attention and the
  only fair way to compare editions of different size or an edition whose total traffic changed.
- Months: only complete months (the current month and data younger than 2 days are excluded). The analysis
  fetches 12 extra months before the window for year-over-year comparisons and seasonality.

## Summary columns / results.json fields

| Column | Field | Meaning |
|---|---|---|
| views/mo | `level.views_per_month_last12` | mean monthly raw views over the last 12 months |
| per 1M | `level.views_per_million_last12` | views per million edition views over the last 12 months |
| — | `level.views_per_million_last3` | same for the last 3 months |
| — | `level.median_daily_views_last12` | median daily views (volume check) |
| 12 mo vs prev 12 mo | `change.change_12m_pct` | per-1M share of the last 12 months vs the 12 before (seasonality cancels out) |
| — | `change.change_12m_raw_pct` | same on raw views (not comparable across editions) |
| — | `change.project_change_12m_pct` | change of the whole edition over the same period |
| last 6 mo YoY | `change.yoy_same_months_pct` | median of (month / same month a year earlier − 1) over the last 6 months: recent momentum |
| — | `change.change_12m_ex_spikes_pct` | the 12-month change with spike days replaced by their baseline |
| trend %/yr [95% CI] | `trend.pct_per_year`, `trend.ci95` | Theil–Sen slope of log(per 1M) after removing calendar-month effects and spike days, annualized; CI from a block bootstrap of the whole pipeline |
| — | `trend.mann_kendall_p` | seasonal Mann–Kendall p-value (direction consistency across calendar months) |
| — | `trend.range_pct` | min..max of the three estimates above — quote it when they differ |
| — | `spikes.share_pct`, `spikes.days` | share of window views above baseline on spike days; top spike days with views and baseline |
| — | `bots.share_pct_last12` | share of spider+automated views among all views (not included in `user` data) |
| — | `seasonality.peak_month`, `peak_ratio` | calendar month with the highest average share and its ratio to an average month |
| — | `redirects.share_pct_last12` | share of views that arrived through redirects |
| verdict | `verdict` | growing / declining / flat / mixed / insufficient_data / no_article |
| confidence | `confidence` | high / medium / low — how far the verdict can be trusted (see methodology.md) |
| — | `checks[]` | every trust check with status ok/info/warn/alert and a message; `reasons` = warn+alert messages |

## Ranking

`score = w_size·size + w_momentum·momentum + w_trust·trust`, each criterion min–max scaled across the rows:
size = log10(per 1M), momentum = trend %/yr, trust = 1 / 0.5 / 0 for high / medium / low.
Presets: balanced 0.4/0.4/0.2 (default), momentum 0.2/0.6/0.2, size 0.6/0.2/0.2; custom via `--weights`.
`sensitivity.verdict` says whether the leader and the top 3 are the same under all presets.
