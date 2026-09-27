# Methodology: when can a pageview trend be trusted?

Wikipedia pageviews are a noisy proxy for public attention. Research that uses them (McIver & Brownstein 2014,
Generous et al. 2014, Mittermeier et al. 2019) normalizes by overall traffic, handles seasonality, removes bot
and news spikes, and requires minimum volumes; Sharpe et al. 2016 found Wikipedia weaker than Google search data
for detecting change points. The skill therefore reports a **verdict with a confidence level and reasons**, never a
bare growth number.

## Pipeline

1. Topic → Wikidata item → article per edition (sitelinks). Missing sitelink = no article (content gap).
   Search hits that merely mention the topic are listed as hints and never used automatically.
2. Daily `user` views (zero-filled) + monthly views of main-namespace redirects; edition totals for normalization.
3. Spike detection on daily views: robust z-score of log1p(views) against a centered 61-day rolling median
   (MAD scale), spike if z > 5, views ≥ 20 and ≥ 4× baseline. Spike days are replaced by the baseline for trends.
4. Per 1M series; calendar-month effects estimated on the detrended log series (Theil–Sen detrending, ≥ 24 months)
   and removed.
5. Three estimates of change: 12 months vs the previous 12 (seasonality-neutral), median same-month YoY over the
   last 6 months (momentum), Theil–Sen trend with a 95% CI from a block bootstrap (blocks of 6 months) that
   re-estimates the seasonal effects in every replicate. Seasonal Mann–Kendall gives a direction-consistency p-value.

## Verdict

- `growing` / `declining`: the trend CI excludes 0 and the 12-month change (|x| ≥ 5%) has the same sign.
- `flat`: |12-month change| < 10% and |trend| < 10%/yr.
- `mixed`: anything else (methods disagree). `insufficient_data`: < 100 views in the last 12 months or the
  article is younger than 12 months. `no_article`: no article in the edition.

## Trust checks

| Check | Warn | Alert | Why |
|---|---|---|---|
| volume | median < 10 views/day | < 365 views in 12 months | single readers/events dominate small series |
| spikes | 10–30% of views on spike days | > 30%, or the 12-month change flips sign without spikes | news-driven attention is not a trend |
| agreement | — | verdict `mixed` | estimates disagree |
| precision | CI wider than 60 points | — | direction may hold, size is uncertain |
| momentum | last-6-months YoY opposite to the 12-month change | — | possible turning point |
| normalization | raw and per-1M changes have opposite signs | — | the direction depends on edition-wide traffic |
| bots | > 50% of all views are bots | — | undetected bots may remain in `user` |
| article_age | first seen < 12 months before the window | first seen inside the window | new pages grow while being indexed |
| data_break | edition-specific break in the period | — | e.g. war-driven reader shifts between ru/uk (2022) |
| basket | < 2/3 of articles move with the topic | removing one article reverses the direction | the topic trend rests on one article |
| ambiguity | topic name matched several meanings | — | wrong item = wrong article |

Info-level context (no effect on confidence): edition changed ≥ 15%, seasonality peak ≥ 1.5× an average month,
bots 35–50%, known global data breaks, slowing/accelerating momentum, redirect share > 25%, missing basket members.

Confidence: any alert → **low**; ≥ 2 warnings → **medium**; otherwise **high**. It is confidence in the
*direction* of the verdict; the CI and `range_pct` describe the size.

## Known data breaks (assets/known_breaks.json)

- 2020-04-29: `automated` agent class introduced (~5% of former `user` views reclassified).
- 2021-06..2022-01: known pageview data loss (~2.8% and ~4.3%).
- 2022: war-driven shift of readers between Russian and Ukrainian Wikipedia (uk, ru, be).
- 2025-03..08: evasive bots (mostly from Brazil) reclassified; human pageviews ~8% below 2024.

## `verify`

Re-measures each row on desktop vs mobile web (each normalized by the edition's device total), with bots
included (all-agents), with the window trimmed by 3 months at either end, and re-fetches one month from the API
bypassing the cache (must equal the zero-filled daily sum). Verdict: any alert → fragile, warnings → mixed, else robust.

## Sources

- Analytics API: https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/ (troubleshooting: zero values
  omitted, 404 = zero or not loaded; concepts: redirects counted separately; changelog: automated agent 2020-04-29)
- Rate limits 2026: https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
- Bot reclassification 2025: https://diff.wikimedia.org/2025/10/17/new-user-trends-on-wikipedia/
- McIver & Brownstein 2014, https://doi.org/10.1371/journal.pcbi.1003581 · Generous et al. 2014,
  https://doi.org/10.1371/journal.pcbi.1003892 · Mittermeier et al. 2019, https://doi.org/10.1371/journal.pbio.3000146 ·
  Sharpe et al. 2016, https://publichealth.jmir.org/2016/2/e161
