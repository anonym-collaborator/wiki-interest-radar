---
name: wiki-interest-radar
description: Measure and compare audience interest in topics across Wikipedia language editions using Wikimedia pageview data — is interest growing, how far can the growth be trusted (spikes, bots, seasonality, platform-wide traffic shifts), which languages or markets look most promising — and produce charts and a one-page PDF report. Use when a user asks which course or topic to add, which language to localize into, whether interest in something is rising in some language, how trustworthy a trend is, or wants Wikipedia pageview statistics, even if they do not mention Wikipedia.
license: MIT
compatibility: Requires Python 3.11+ and uv, plus outbound HTTPS to wikimedia.org, wikidata.org and *.wikipedia.org. Will not work in sandboxes without network access (e.g. Claude API code execution).
metadata:
  version: "0.1.0"
---

# Wiki interest radar

One script does all the data work: topic → articles, fetching, cleaning, normalization,
statistics, trust checks, charts, PDF. Do not write your own fetching or statistics code and
do not calculate numbers yourself — copy them from the script output.

Command prefix (absolute path of this skill's directory): `uv run <skill_dir>/scripts/radar.py`
The first run installs dependencies (~15 s). Every command prints the exact next commands.
Run commands from the user's working directory (not from the skill directory): results go to `./wir-runs/<name>`
(or `--out <dir>`), and the summary prints absolute paths — reuse them in follow-ups.

## Workflow (usually 1–3 commands)

1. **Analyze** — resolves the topic via Wikidata, fetches, normalizes, tests the trend, rates trust, draws a chart:
   ```bash
   uv run <skill_dir>/scripts/radar.py analyze --topic "intermittent fasting" --langs pl,cs
   ```
   - `--topic`: the user's words or the English name; repeat `--topic` for several topics.
   - Broad theme (e.g. "learning English", "space science") → basket of 2–5 concrete articles:
     `--basket "Learning English: English language; English grammar; IELTS; TOEFL"`
   - `--langs`: Wikipedia edition codes (uk, pl, cs, sk, de, fr, es, pt, it, tr, ro, en…).
   - Window: last 24 full months by default; `--months 36` (12–120) or `--start 2023-01 --end 2025-12`.
2. **Answer from the printed summary** (also saved as `summary.md` in the run directory), using the template below.
3. **Shareable report** — whenever the user wants a PDF, report, звіт, one-pager or something to send:
   ```bash
   uv run <skill_dir>/scripts/radar.py report --run <run dir> --lang uk --notes "2-4 sentences of recommendation"
   ```
   `--lang uk` for Ukrainian users, `en` otherwise. Give the user the PDF path it prints.
4. **Check numbers** before sending an answer or notes you wrote:
   ```bash
   uv run <skill_dir>/scripts/radar.py check --run <run dir> --text "<your answer>"
   ```
   Exit code 5 lists unsupported numbers or a direction the data contradict ("grew 14%" when it is −14%):
   fix them from the summary, re-check. `report --notes` runs the same check and builds no PDF until it passes.

## Follow-ups — reuse the run, don't start over

- Other editions / window / filters (cached, takes seconds):
  `analyze --from <run dir> --add-langs sk` · `--drop-langs pl` · `--months 36` · `--agent all-agents` · `--access mobile-web`
- The user's own criteria of promise: `analyze --from <run dir> --weights size=0.2,momentum=0.6,trust=0.2`
  (size = share of attention, momentum = trend, trust = confidence). The summary says whether the ranking is stable.
- "What changed?" → `diff --runs <old run dir> <new run dir>`
- "How much can we trust this?" in depth → `verify --run <run dir>` → robust / mixed / fragile with reasons.
- In a follow-up answer, first say what changed at the user's request (e.g. "Polish dropped, window now 36 months").

## Rules (and why)

- Compare editions only by the **per 1M** column: editions differ >10× in size and whole editions gain or lose traffic over time.
- **NO ARTICLE = content gap, not zero interest.** Say so explicitly. Never guess a title or substitute another article;
  the summary lists articles that merely mention the topic. Use `--title pl=<exact title>` only if the user accepts that proxy.
- Every growth figure goes with its **verdict and confidence**, plus the reasons printed under "Why". Don't invent reasons.
- When the 12-month change, the last-6-months YoY and the trend differ, give the range, not one number.
- `declining` with high confidence is a solid finding — don't soften it. `mixed` or low confidence → don't recommend; propose how to validate.
- Pageviews measure attention on Wikipedia, not willingness to pay: always end with what to validate next.
- Countries: an edition is a language, not a country. Use the edition(s) people there read and say that this is an approximation.
- New topic ideas: propose 3–5 concrete articles yourself and measure them (separate `--topic`s or one `--basket`).
- Don't ask for confirmation before analyzing. If the summary marks a topic **AMBIGUOUS**, the first sentence of your
  answer names the meaning that was measured (e.g. "Mercury — the planet"), then list the other meanings and offer
  `--qid`. A wrong meaning silently answers a different question.

## Answer template

**Answer:** 1–2 sentences, the verdict per edition (or "no article"); for an AMBIGUOUS topic start with the meaning measured.
**Data:** per 1M, 12-month change, trend %/yr [95% CI] for each edition, copied from the table.
**How far to trust it:** confidence + the listed reasons (spikes, bots, low volume, seasonality, platform shifts).
**Limitations:** the ones that matter here (one article vs the whole topic, language ≠ country, attention ≠ demand).
**Next step:** one concrete validation or follow-up (another data source, an experiment, a follow-up command).

## Exit codes

0 ok · 2 nothing measurable (no articles) · 3 bad arguments — the message says what to fix · 4 topic not found on
Wikidata — retry with the English name or `--qid Q…` · 5 `check` (or `report --notes`) found unsupported numbers or a
wrong direction · 6 Wikimedia API problem — wait a minute and rerun the same command (cached data is reused).

## Read more only when needed

- [references/metrics.md](references/metrics.md) — what each summary column and results.json field means. Read when asked how a number is computed.
- [references/methodology.md](references/methodology.md) — trust checks, thresholds, verdict rules and their sources. Read for deep "can we trust it?" questions.
- [references/troubleshooting.md](references/troubleshooting.md) — errors, rate limits, Windows encoding. Read when a command fails.
