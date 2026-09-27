"""One-page A4 PDF (+ PNG preview).

Text is measured first and the chart takes the space that is left, with every
text block on a line budget, so the page can never spill onto a second one.
All numbers come from results.json; the agent only adds optional notes."""
from __future__ import annotations

import json
import sys
import textwrap
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config  # noqa: E402
from .charts import INK, MUTED, draw_trend  # noqa: E402
from .i18n import render_check, t  # noqa: E402
from .langs import UK_NAMES, english_name  # noqa: E402
from .runio import load_run  # noqa: E402

UK_BY_CODE = {v: k for k, v in UK_NAMES.items()}
W_IN, H_IN = 8.27, 11.69
LH_ANS = 9.2 * 1.38 / 72 / H_IN
LH_SMALL = 7.8 * 1.38 / 72 / H_IN
ROW_H = 0.0165
FOOTER_TOP = 0.062
MAX_TABLE_ROWS = 9


def lang_label(code: str, ui: str) -> str:
    name = UK_BY_CODE.get(code) if ui == "uk" else english_name(code)
    return f"{name or english_name(code)} ({code})"


def _num(v, nd=0, signed=False, pct=False):
    if v is None:
        return "—"
    s = f"{v:+.{nd}f}" if signed else f"{v:,.{nd}f}".replace(",", " ")
    return (s + "%") if pct else s


def _pm(v):
    if v is None:
        return "—"
    return f"{v:.2f}" if v < 10 else (f"{v:.1f}" if v < 100 else f"{v:.0f}")


def _wrap(text: str, width: int, max_lines: int) -> list[str]:
    lines = textwrap.wrap(text, width=width, break_long_words=True)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(0, width - 1)].rstrip() + "…"
    return lines


def _lines(items: list[str], width: int, per_item: int) -> list[str]:
    out: list[str] = []
    for it in items:
        out += _wrap(it, width, per_item)
    return out


def _fit(lines: list[str], room: int) -> list[str]:
    if len(lines) <= room:
        return lines
    return lines[:max(room - 1, 0)] + ["…"]


def _block(fig, x, y, lines, size=8.0, color=INK, lh=1.38, weight="normal") -> float:
    """Draw lines top-down from y (figure fraction); return the y below the block."""
    step = size * lh / 72.0 / H_IN
    for ln in lines:
        fig.text(x, y, ln, fontsize=size, color=color, va="top", weight=weight)
        y -= step
    return y


STAB_UK = {"stable": "стабільний за будь-яких пресетів ваг",
           "leader stable, order below varies": "лідер стабільний, решта порядку залежить від ваг",
           "unstable: depends on weights": "нестабільний: залежить від ваг критеріїв"}


def _answer_sentences(payload: dict, ui: str, compact: bool) -> list[str]:
    out = []
    v, vs, c = t(ui, "verdicts"), t(ui, "verdicts_short"), t(ui, "conf")
    multi_topic = len({x["topic"] for x in payload["rows"]}) > 1
    for r in payload["rows"]:
        lab = lang_label(r["lang"], ui) + (f" / {r['topic']}" if multi_topic else "")
        if r["status"] != "ok":
            sent = t(ui, "sent_missing").format(lang=lab)
            if r.get("mentioned_in"):
                sent += (" Тема лише згадується в статтях: " if ui == "uk" else " The topic is only mentioned in: ")                     + ", ".join(r["mentioned_in"][:3]) + "."
            out.append(sent)
            continue
        if r["verdict"] == "insufficient_data":
            out.append(t(ui, "sent_insufficient").format(lang=lab))
            continue
        ch, tr = r["change"], r["trend"]
        if compact:
            if ui == "uk":
                out.append(f"{lab}: {vs[r['verdict']]}, {_num(ch['change_12m_pct'], signed=True, pct=True)} за 12 міс., "
                           f"тренд {_num(tr['pct_per_year'], signed=True, pct=True)}/рік; довіра {c[r['confidence']]}")
            else:
                out.append(f"{lab}: {vs[r['verdict']]}, {_num(ch['change_12m_pct'], signed=True, pct=True)} over 12 mo, "
                           f"trend {_num(tr['pct_per_year'], signed=True, pct=True)}/yr; confidence {c[r['confidence']]}")
        else:
            out.append(t(ui, "sent_ok").format(
                lang=lab, verdict=v[r["verdict"]], change=_num(ch["change_12m_pct"], signed=True, pct=True),
                trend=_num(tr["pct_per_year"], signed=True, pct=True),
                lo=_num(tr["ci95"][0], signed=True), hi=_num(tr["ci95"][1], signed=True),
                conf=c[r["confidence"]]))
    rk = payload.get("ranking")
    if rk:
        items = ", ".join(f"{x['rank']}. {x['lang']}" + (f"/{x['topic']}" if multi_topic else "")
                          for x in rk["table"][:5])
        rule = " + ".join(f"{w:g}·{k}" for k, w in rk["weights"].items() if w)
        stab = rk["sensitivity"]["verdict"]
        if ui == "uk":
            rule = rule.replace("size", "розмір").replace("momentum", "динаміка").replace("trust", "довіра")
            stab = STAB_UK.get(stab, stab)
        out.append(t(ui, "ranking").format(rule=rule, items=items, stab=stab))
    return out


def _trust_bullets(payload: dict, ui: str) -> list[str]:
    """Alerts/warnings per edition first, then shared context folded into one
    line each, then a single 'no problems' line for clean editions."""
    mark = {"alert": "✖", "warn": "▲", "info": "•", "ok": "✓"}
    bad, clean, norm, other = [], [], [], []
    for r in payload["rows"]:
        if r["status"] != "ok":
            continue
        issues = sorted((c for c in r["checks"] if c["status"] in ("alert", "warn")),
                        key=lambda c: c["status"] != "alert")
        for c in issues[:2]:
            bad.append(f"{mark[c['status']]} {r['lang']}: {render_check(c, ui)}")
        if not issues:
            clean.append(r["lang"])
        for c in r["checks"]:
            if c["status"] != "info":
                continue
            if c["id"] == "normalization":
                norm.append(f"{r['lang']} {c['params']['pc']}%")
            elif c["id"] in ("momentum", "seasonality", "bots"):
                other.append(f"• {r['lang']}: {render_check(c, ui)}")
    out = list(bad)
    if clean:
        out.append(("✓ без попереджень (методи узгоджені, сплески й боти в межах норми): " if ui == "uk"
                    else "✓ no warnings (methods agree, spikes and bots within limits): ") + ", ".join(clean))
    if norm:
        out.append(("• увесь розділ змінився за 12 міс.: " if ui == "uk" else "• whole editions changed over 12 months: ")
                   + ", ".join(norm)
                   + ("; тому показники — на 1 млн переглядів розділу" if ui == "uk"
                      else "; hence figures are per 1M edition views"))
    return out + other


def _limit_bullets(payload: dict, ui: str) -> list[str]:
    out = list(t(ui, "limits"))
    rows = [r for r in payload["rows"] if r["status"] == "ok"]
    if rows:
        n = max(len(r.get("articles", [])) for r in rows)
        if n <= 2:
            out.append(t(ui, "limit_single").format(n=n))
    seen = set()
    for r in rows:
        for b in r.get("breaks", []):
            if b["id"] not in seen and not b["specific"]:
                seen.add(b["id"])
                note = (b.get("note_uk") or b["note"]) if ui == "uk" else b["note"]
                out.append(f"{b['start']}..{b['end']}: {note}")
    return out


def _table(fig, payload: dict, ui: str, x0: float, y: float) -> float:
    heads = [t(ui, k) for k in ("table_lang", "table_article", "table_views", "table_pm",
                                "table_change", "table_trend", "table_verdict", "table_conf")]
    xs = [x0, x0 + 0.068, x0 + 0.285, x0 + 0.37, x0 + 0.45, x0 + 0.55, x0 + 0.70, x0 + 0.82]
    for xx, h in zip(xs, heads):
        fig.text(xx, y, h, fontsize=7.2, color=MUTED, va="top", weight="bold")
    y -= 0.016
    v, c = t(ui, "verdicts_short"), t(ui, "conf")
    for r in payload["rows"][:MAX_TABLE_ROWS]:
        if r["status"] == "ok":
            art = r["articles"][0]["title"] if len(r["articles"]) == 1 else f"{r['topic']} ({len(r['articles'])})"
            tr = r["trend"]
            cells = [r["lang"], textwrap.shorten(art, 34, placeholder="…"),
                     _num(r["level"]["views_per_month_last12"]), _pm(r["level"]["views_per_million_last12"]),
                     _num(r["change"]["change_12m_pct"], signed=True, pct=True),
                     f"{_num(tr['pct_per_year'], signed=True)} [{_num(tr['ci95'][0], signed=True)}; "
                     f"{_num(tr['ci95'][1], signed=True)}]",
                     v[r["verdict"]], c[r["confidence"]]]
        else:
            cells = [r["lang"], t(ui, "no_article"), "—", "—", "—", "—", v["no_article"], "—"]
        for xx, cell in zip(xs, cells):
            fig.text(xx, y, cell, fontsize=7.8, color=INK, va="top")
        y -= ROW_H
    if len(payload["rows"]) > MAX_TABLE_ROWS:
        fig.text(x0, y, f"… +{len(payload['rows']) - MAX_TABLE_ROWS}", fontsize=7, color=MUTED, va="top")
        y -= ROW_H
    return y


def build_pdf(run: Path, ui: str, title: str | None, notes: str | None, out: Path) -> Path:
    payload, rows = load_run(run)
    spec = payload["spec"]
    w = payload["rows"][0]["window"]
    if not title:
        names = []
        for tp in spec["topics"]:
            lab_uk = tp["members"][0].get("label_uk") if tp["kind"] == "topic" else ""
            names.append(lab_uk if ui == "uk" and lab_uk else tp["name"])
        title = t(ui, "report_title").format(topic=", ".join(names))
    today = date.today().isoformat()

    # Measure text first; the chart gets what is left (within bounds).
    compact = len(payload["rows"]) > 3
    ans = _wrap(notes.strip(), 98, 5) if notes else []
    sents = _answer_sentences(payload, ui, compact)
    has_rank = bool(payload.get("ranking"))
    body, rank_s = (sents[:-1], sents[-1:]) if has_rank else (sents, [])
    ans += _lines(["– " + x for x in body], 98, 1 if compact else 2)
    ans += _lines(["– " + x for x in rank_s], 98, 2)
    ans = ans[:14]
    trust = _lines(_trust_bullets(payload, ui), 60, 3)
    limits = _lines(["• " + x for x in _limit_bullets(payload, ui)], 60, 3)
    n_table = min(len(payload["rows"]), MAX_TABLE_ROWS) + (1 if len(payload["rows"]) > MAX_TABLE_ROWS else 0)
    header_h = 0.075
    answer_h = 0.028 + len(ans) * LH_ANS
    table_h = 0.016 + n_table * ROW_H
    bullets_min_h = 0.03 + min(max(len(trust), len(limits)), 8) * LH_SMALL
    free = 0.965 - header_h - answer_h - 0.035 - 0.045 - table_h - 0.012 - bullets_min_h - FOOTER_TOP
    chart_h = max(0.18, min(0.33, free))

    fig = plt.figure(figsize=(W_IN, H_IN))
    x0 = 0.065
    y = _block(fig, x0, 0.965, _wrap(title, 62, 2), size=15, weight="bold")
    sub = t(ui, "report_sub").format(langs=", ".join(lang_label(c, ui) for c in spec["langs"]),
                                     start=w["start"], end=w["end"], months=w["months"],
                                     agent=spec["agent"], today=today)
    y = _block(fig, x0, y - 0.004, _wrap(sub, 128, 2), size=7.2, color=MUTED)
    y = _block(fig, x0, y - 0.010, [t(ui, "answer")], size=10.5, weight="bold")
    y = _block(fig, x0, y - 0.002, ans, size=9.2)

    chart_top = y - 0.035  # room for the legend above the plot
    ax = fig.add_axes([x0 + 0.035, chart_top - chart_h, 0.835, chart_h])
    draw_trend(ax, rows, ui, legend="top")
    y = _table(fig, payload, ui, x0, chart_top - chart_h - 0.045)

    y -= 0.012
    room = max(int((y - 0.022 - FOOTER_TOP) / LH_SMALL), 1)
    col2 = x0 + 0.46
    yl = _block(fig, x0, y, [t(ui, "trust_title")], size=9.5, weight="bold")
    _block(fig, x0, yl - 0.002, _fit(trust, room), size=7.8)
    yr = _block(fig, col2, y, [t(ui, "limits_title")], size=9.5, weight="bold")
    _block(fig, col2, yr - 0.002, _fit(limits, room), size=7.8)

    foot = t(ui, "footer").format(today=today, cmd=payload.get("command", "")) + \
        f" · {config.SKILL_NAME} {config.VERSION}"
    _block(fig, x0, 0.040, _wrap(foot, 150, 2), size=6.2, color=MUTED)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, format="pdf")
    fig.savefig(out.with_suffix(".png"), dpi=110)
    plt.close(fig)
    return out


def cmd_report(a) -> int:
    run = Path(a.run)
    notes = a.notes
    if a.notes_file:
        notes = Path(a.notes_file).read_text(encoding="utf-8")
    if notes and len(notes) > 700:
        print("Error: --notes must be at most 700 characters (2-4 sentences).", file=sys.stderr)
        return 3
    if notes:
        # the PDF is the artifact that gets forwarded: refuse to print a figure the data do not support
        from .check import FIX_HINT, run_check
        res = run_check(load_run(a.run)[0], notes)
        if not res["ok"]:
            print(json.dumps({k: res[k] for k in ("unsupported_numbers", "direction_conflicts")},
                             ensure_ascii=False, indent=1))
            print("PDF not built: the notes do not match results.json. " + FIX_HINT, file=sys.stderr)
            return 5
    out = Path(a.out) if a.out else run / "report.pdf"
    try:
        pdf = build_pdf(run, a.lang, a.title, notes, out)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 3
    print(f"PDF: {pdf.resolve().as_posix()}\nPreview: {pdf.with_suffix('.png').resolve().as_posix()}\n"
          f"Before sending numbers you wrote yourself: check --run \"{run.resolve().as_posix()}\" --text \"<your answer>\"")
    return 0
