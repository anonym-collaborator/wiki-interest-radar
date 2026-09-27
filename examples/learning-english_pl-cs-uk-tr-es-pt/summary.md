# wiki-interest-radar: Learning English · pl, cs, uk, tr, es, pt
Window 2024-09..2026-08 (24 full months, current month excluded) · agent=user · access=all-access · redirects included

## Resolved (from Wikidata; never guess other titles)
- English language → Q1860 “West Germanic language” | pl: Język angielski (+6 redirects) | cs: Angličtina (+4 redirects) | uk: Англійська мова (+8 redirects) | tr: İngilizce (+7 redirects) | es: Idioma inglés (+25 redirects) | pt: Língua inglesa (+16 redirects)
- English grammar → Q560583 “body of rules that describe the structure of expressions in…” | pl: Gramatyka języka angielskiego | cs: Anglická gramatika | uk: Граматика англійської мови | tr: NO ARTICLE (topic is only mentioned inside: Future simple, Alexander Bain (filozof), Çizgi) | es: Gramática del inglés | pt: Gramática da língua inglesa
- IELTS → Q490396 “Test for learners of English as a second language” | pl: IELTS | cs: IELTS | uk: IELTS | tr: IELTS | es: IELTS (+1 redirects) | pt: Sistema de avaliação na língua inglesa internacional (+2 redirects)
- TOEFL → Q487425 “examination to certify skill in English for non-native…” | pl: TOEFL | cs: NO ARTICLE (topic is only mentioned inside: Test of English for International Communication, TrackTest, Společný evropský referenční rámec) | uk: TOEFL | tr: TOEFL | es: TOEFL (+1 redirects) | pt: Teste de Inglês como uma Língua Estrangeira (+3 redirects)

## Results
| edition | topic | views/mo | per 1M | 12 mo vs prev 12 mo | last 6 mo YoY | trend %/yr [95% CI] | verdict | confidence |
|---|---|---|---|---|---|---|---|---|
| pl | Learning English | 8 824 | 46.9 | -11% | -6% | -11 [-13; -8] | declining | high |
| cs | Learning English | 3 059 | 51.5 | -18% | -11% | -15 [-20; -10] | declining | high |
| uk | Learning English | 7 210 | 127 | -18% | -11% | -16 [-18; -13] | declining | high |
| tr | Learning English | 8 870 | 81.5 | +1% | +2% | -2 [-5; +1] | flat | high |
| es | Learning English | 28 795 | 52.9 | -14% | -6% | -14 [-17; -11] | declining | high |
| pt | Learning English | 9 658 | 53.8 | -13% | +1% | -14 [-18; -9] | declining | high |
views/mo = raw monthly mean, last 12 months · per 1M = views per million views of that edition (use this to compare editions) · 12 mo vs prev 12 mo and last 6 mo YoY = change of the per-1M share · trend = deseasonalized, spike-cleaned Theil-Sen slope with 95% CI

## Why (quote these reasons; do not invent others)
- pl/Learning English: declining, confidence high. No warnings.
- cs/Learning English: declining, confidence high. No warnings.
  Context: articles missing in this edition: TOEFL.
- uk/Learning English: declining, confidence high. No warnings.
  Context: the whole uk.wikipedia.org changed -25% over the same 12 months; figures are per 1M edition views to remove that.
- tr/Learning English: flat, confidence high. No warnings.
  Context: the whole tr.wikipedia.org changed -16% over the same 12 months; figures are per 1M edition views to remove that; articles missing in this edition: English grammar.
- es/Learning English: declining, confidence high. No warnings.
  Context: the whole es.wikipedia.org changed -21% over the same 12 months; figures are per 1M edition views to remove that.
- pt/Learning English: declining, confidence high. No warnings.
  Context: the whole pt.wikipedia.org changed -17% over the same 12 months; figures are per 1M edition views to remove that.

## Ranking (balanced: 0.4×size + 0.4×momentum + 0.2×trust)
1. tr/Learning English (0.821), 2. uk/Learning English (0.6), 3. pl/Learning English (0.357), 4. pt/Learning English (0.307), 5. es/Learning English (0.305), 6. cs/Learning English (0.257)
Sensitivity across presets: unstable: depends on weights.

## Limitations
- Wikipedia pageviews show attention, not willingness to pay; treat results as a direction to validate.
- A language edition is not a country; bot filtering is imperfect; Wikipedia-wide traffic shifts over time.

## Next
- Shareable one-page PDF: `uv run "scripts/radar.py" report --run "examples/learning-english_pl-cs-uk-tr-es-pt" --lang uk` (or --lang en)
- Follow-up with changed assumptions: `uv run "scripts/radar.py" analyze --from "examples/learning-english_pl-cs-uk-tr-es-pt" --add-langs <codes> | --months N | --agent all-agents | --access mobile-web`
- Files: examples/learning-english_pl-cs-uk-tr-es-pt/results.json · examples/learning-english_pl-cs-uk-tr-es-pt/chart.png · examples/learning-english_pl-cs-uk-tr-es-pt/data.csv
