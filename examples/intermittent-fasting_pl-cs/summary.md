# wiki-interest-radar: intermittent fasting · pl, cs
Window 2024-09..2026-08 (24 full months, current month excluded) · agent=user · access=all-access · redirects included

## Resolved (from Wikidata; never guess other titles)
- intermittent fasting → Q1666254 “a diet that cycles between a period of fasting and non-…” | pl: NO ARTICLE (topic is only mentioned inside: Stres oksydacyjny, Głodówka lecznicza, Paleolityczny styl życia) | cs: Přerušovaný půst

## Results
| edition | topic | views/mo | per 1M | 12 mo vs prev 12 mo | last 6 mo YoY | trend %/yr [95% CI] | verdict | confidence |
|---|---|---|---|---|---|---|---|---|
| pl | intermittent fasting | — | — | — | — | — | NO ARTICLE (content gap) | — |
| cs | intermittent fasting | 183 | 3.08 | -47% | -45% | -40 [-48; -29] | declining | medium |
views/mo = raw monthly mean, last 12 months · per 1M = views per million views of that edition (use this to compare editions) · 12 mo vs prev 12 mo and last 6 mo YoY = change of the per-1M share · trend = deseasonalized, spike-cleaned Theil-Sen slope with 95% CI

## Why (quote these reasons; do not invent others)
- cs/intermittent fasting: declining, confidence medium. Problems: low volume: median 5 views/day in the last 12 months; 11% of window views fall on spike days (2024-10-17: 110 vs ~12, 2025-04-14: 508 vs ~12); the trend is computed without them.
- Missing articles are a content gap, not zero interest; they cannot be compared. Articles that merely mention the topic are NOT substitutes unless the user accepts a proxy (then: --title <lang>=<Title>).

## Limitations
- Wikipedia pageviews show attention, not willingness to pay; treat results as a direction to validate.
- A language edition is not a country; bot filtering is imperfect; Wikipedia-wide traffic shifts over time.

## Next
- Shareable one-page PDF: `uv run "scripts/radar.py" report --run "examples/intermittent-fasting_pl-cs" --lang uk` (or --lang en)
- Follow-up with changed assumptions: `uv run "scripts/radar.py" analyze --from "examples/intermittent-fasting_pl-cs" --add-langs <codes> | --months N | --agent all-agents | --access mobile-web`
- Files: examples/intermittent-fasting_pl-cs/results.json · examples/intermittent-fasting_pl-cs/chart.png · examples/intermittent-fasting_pl-cs/data.csv
