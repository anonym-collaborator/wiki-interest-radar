"""summary.md (what the agent reads, <= ~40 lines), results.json, data.csv."""
from __future__ import annotations

import csv
import json
from textwrap import shorten
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .series import month_label

LIMITATIONS = [
    "Wikipedia pageviews show attention, not willingness to pay; treat results as a direction to validate.",
    "A language edition is not a country; bot filtering is imperfect; Wikipedia-wide traffic shifts over time.",
]


def _fmt(v, suffix="", nd=0, signed=False):
    if v is None:
        return "—"
    s = f"{v:+.{nd}f}" if signed else f"{v:,.{nd}f}".replace(",", " ")
    return s + suffix


def _pm(v):
    if v is None:
        return "—"
    return f"{v:.2f}" if v < 10 else f"{v:.1f}" if v < 100 else f"{v:.0f}"


def results_payload(rows, spec: dict, ranking: dict | None, command: str) -> dict:
    return {"tool": config.SKILL_NAME, "version": config.VERSION,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "command": command, "spec": spec, "rows": [r.result for r in rows], "ranking": ranking}


def write_outputs(out: Path, rows, spec: dict, ranking: dict | None, command: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    payload = results_payload(rows, spec, ranking, command)
    (out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    with (out / "data.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["topic", "lang", "month", "views", "edition_views", "views_per_million"])
        for r in rows:
            if r.raw is None:
                continue
            for m, v, p in zip(r.months, r.raw, r.proj):
                w.writerow([r.topic.name, r.lang, month_label(m), int(v), int(p),
                            f"{v / p * 1e6:.4f}" if p else ""])
    return payload


def render_summary(payload: dict, out: Path, skill_cmd: str) -> str:
    spec, rows = payload["spec"], payload["rows"]
    run = out.as_posix()
    w = rows[0]["window"]
    lines = [f"# {config.SKILL_NAME}: {', '.join(t['name'] for t in spec['topics'])} · "
             f"{', '.join(spec['langs'])}",
             f"Window {w['start']}..{w['end']} ({w['months']} full months, current month excluded) · "
             f"agent={spec['agent']} · access={spec['access']} · redirects {'included' if spec['redirects'] else 'excluded'}",
             ""]
    for t in spec["topics"]:
        for m in t["members"]:
            if m.get("ambiguous"):
                alts = "; ".join(a["description"][:40] for a in m.get("alternatives", [])[:3])
                lines.append(f"> **AMBIGUOUS — say this in the first sentence of the answer:** “{m['query']}” was measured "
                             f"as {m['qid']} ({shorten(m['description'], 60, placeholder='…')}). "
                             + (f"Other meanings: {alts}. " if alts else "")
                             + "Offer to re-run with `--qid` if the user meant another one.")
    if lines[-1].startswith("> "):
        lines.append("")
    lines.append("## Resolved (from Wikidata; never guess other titles)")
    for t in spec["topics"]:
        for m in t["members"]:
            arts = []
            for lang in spec["langs"]:
                a = m["articles"].get(lang)
                if a:
                    red = f" (+{len(a['redirects'])} redirects)" if a["redirects"] and spec["redirects"] else ""
                    arts.append(f"{lang}: {a['title']}{red}")
                else:
                    hint = m.get("gap_hints", {}).get(lang)
                    arts.append(f"{lang}: NO ARTICLE" + (f" (topic is only mentioned inside: {', '.join(hint)})" if hint else ""))
            flag = " AMBIGUOUS" if m.get("ambiguous") else ""
            lines.append(f"- {m['query']} → {m['qid']} “{shorten(m['description'], 60, placeholder='…')}”{flag} | "
                         + " | ".join(arts))
            if m.get("ambiguous") and m.get("alternatives"):
                alts = "; ".join(f"{a['qid']} {a['description'][:40]}" for a in m["alternatives"][:3])
                lines.append(f"  other meanings (use --qid): {alts}")
    lines += ["", "## Results",
              "| edition | topic | views/mo | per 1M | 12 mo vs prev 12 mo | last 6 mo YoY | "
              "trend %/yr [95% CI] | verdict | confidence |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["status"] != "ok":
            lines.append(f"| {r['lang']} | {r['topic']} | — | — | — | — | — | NO ARTICLE (content gap) | — |")
            continue
        lv, ch, tr = r["level"], r["change"], r["trend"]
        ci = tr["ci95"]
        lines.append(
            f"| {r['lang']} | {r['topic']} | {_fmt(lv['views_per_month_last12'])} | {_pm(lv['views_per_million_last12'])} | "
            f"{_fmt(ch['change_12m_pct'], '%', signed=True)} | {_fmt(ch['yoy_same_months_pct'], '%', signed=True)} | "
            f"{_fmt(tr['pct_per_year'], '', signed=True)} [{_fmt(ci[0], '', signed=True)}; {_fmt(ci[1], '', signed=True)}] | "
            f"{r['verdict']} | {r['confidence']} |")
    lines.append("views/mo = raw monthly mean, last 12 months · per 1M = views per million views of that "
                 "edition (use this to compare editions) · 12 mo vs prev 12 mo and last 6 mo YoY = change of the "
                 "per-1M share · trend = deseasonalized, spike-cleaned Theil-Sen slope with 95% CI")
    lines += ["", "## Why (quote these reasons; do not invent others)"]
    for r in rows:
        if r["status"] != "ok":
            continue
        bad = [c["message"].rstrip(".") for c in r["checks"] if c["status"] in ("alert", "warn")]
        info = [c["message"].rstrip(".") for c in r["checks"]
                if c["status"] == "info" and c["id"] != "data_break"]
        head = f"- {r['lang']}/{r['topic']}: {r['verdict']}, confidence {r['confidence']}."
        lines.append(head + (" Problems: " + "; ".join(bad) + "." if bad else " No warnings."))
        if info:
            lines.append("  Context: " + "; ".join(info[:3]) + ".")
    gaps = [r for r in rows if r["status"] != "ok"]
    if gaps:
        lines.append("- Missing articles are a content gap, not zero interest; they cannot be compared. "
                     "Articles that merely mention the topic are NOT substitutes unless the user accepts a proxy "
                     "(then: --title <lang>=<Title>).")
    rk = payload.get("ranking")
    if rk:
        items = ", ".join(f"{x['rank']}. {x['lang']}/{x['topic']} ({x['score']})" for x in rk["table"][:6])
        rule = " + ".join(f"{v:g}×{k}" for k, v in rk["weights"].items() if v)
        lines += ["", f"## Ranking ({rk['preset'] or 'custom'}: {rule})", items,
                  f"Sensitivity across presets: {rk['sensitivity']['verdict']}."]
    lines += ["", "## Limitations"] + [f"- {x}" for x in LIMITATIONS]
    lines += ["", "## Next",
              f"- Shareable one-page PDF: `{skill_cmd} report --run \"{run}\" --lang uk` (or --lang en)",
              f"- Follow-up with changed assumptions: `{skill_cmd} analyze --from \"{run}\" --add-langs <codes> "
              f"| --months N | --agent all-agents | --access mobile-web`",
              f"- Files: {run}/results.json · {run}/chart.png · {run}/data.csv"]
    return "\n".join(lines) + "\n"
