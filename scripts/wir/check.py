"""`check`: every number in the agent's answer must come from results.json.

Cheap models sometimes round creatively, mix up editions or invent a figure.
This command extracts the numbers from the answer text, guesses each one's
unit from the words after it (%/yr, %, per 1M, views) and matches it only
against values of that unit, with rounding tolerance."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .langs import UK_NAMES
from .runio import load_run

UK_BY_CODE = {v: k for k, v in UK_NAMES.items()}

SPACES = "   "
NUM = re.compile(r"(?<![\w.])([+\-−–]?)(\d{1,3}(?:[" + SPACES + r"]\d{3})+|\d+)([.,]\d+)?(?![\w])")
SKIP_CONTEXT = [
    re.compile(r"\b(19|20)\d{2}-\d{2}(-\d{2})?\b"),                 # 2025-04, 2025-04-14
    re.compile(r"\b\d{1,2}\.\d{1,2}\.(?:19|20)\d{2}\b"),            # 14.04.2025
    re.compile(r"\bQ\d+\b"),                                      # Wikidata ids
    re.compile(r"https?://\S+"),                                  # URLs
    re.compile(r"`[^`]*`"),                                       # inline code / commands
    re.compile(r"\b\d+[\s-]*(?:months?|mo\b|міс\w*|місяц\w*|years?|рок\w*|рік|річн\w*|днів|days?)", re.I),
    re.compile(r"\b95\s*%\s*(?:CI|ДІ|confidence|інтервал\w*|довір\w*)", re.I),
    re.compile(r"\b1\s*(?:M\b|млн|million|мільйон\w*)", re.I),
    re.compile(r"(?m)^\s*\d+[.)]\s"),                              # list numbering
    re.compile(r"\(\d{1,2}\)"),                                   # inline list markers "(2)"
    re.compile(r"\b\d{1,2}-(?:ше|ге|є|те|й|го|th|st|nd|rd)\b", re.I),  # ordinals "1-ше місце"
    re.compile(r"\b(?:19|20)\d{2}\b"),                             # years
]
TREND_AFTER = re.compile(
    r"^\s*%?\s*(?:/\s*(?:рік|р\.|yr|year)|на рік|за рік|per year|a year|щороку|annually)", re.I)
PM_AFTER = re.compile(
    r"^\s*(?:перегляд\w*\s+|views?\s+)?(?:на\s*(?:1\s*)?(?:млн|мільйон\w*|М\b)|per\s*(?:1\s*)?(?:M\b|million)|/\s*1\s*M\b)",
    re.I)
COUNT_AFTER = re.compile(r"^\s*(?:перегляд\w*|views?\b|visits?\b)", re.I)
SEMANTIC_MISSING = re.compile(r"no article|not exist|missing|content gap|немає|відсутн|не існує|прогалин", re.I)
CONFIDENCE_WORDS = re.compile(r"\b(high|medium|low|висок\w*|середн\w*|низьк\w*)\b", re.I)
# Small models occasionally switch script mid-sentence (seen in evals: Chinese inside a Ukrainian answer).
FOREIGN_SCRIPT = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]+")
# Direction of a percentage: "зросло на 14%" / "fell 14%" (word before) or "на 14% менше" / "14% lower"
# (word after). Matching by absolute value alone would accept "grew 14%" when the data say -14%.
# Comparatives count only after the number: "less than 10%" is a threshold, not a direction.
UP_W = (r"зрос\w*|зріс\w*|вирос\w*|виріс\w*|рост\w*|збільш\w*|підвищ\w*|приріст\w*|плюс|"
        r"grew|grow\w*|increas\w*|rose|rise[sn]?|rising|gain\w*|up")
DOWN_W = (r"пада\w*|падін\w*|впа\w*|знизи\w*|зниж\w*|зменш\w*|скорот\w*|скороч\w*|спад\w*|мінус|"
          r"declin\w*|decreas\w*|fell|fall\w*|drop\w*|down|lost|loss\w*|shr[iau]nk\w*")
DIR_BEFORE = re.compile(rf"(?<!\w)(?:(?P<up>{UP_W})|(?P<down>{DOWN_W}))(?!\w)", re.I)
DIR_AFTER = re.compile(rf"(?<!\w)(?:(?P<up>{UP_W}|більш\w*|вищ\w*|more|higher)|"
                       rf"(?P<down>{DOWN_W}|менш\w*|нижч\w*|less|lower|fewer))(?!\w)", re.I)
CLAUSE_END = re.compile(r"[,.;:!?\n|()\[\]]")
NEGATION = re.compile(r"(?<!\w)(?:не|ні|без|not|no|isn[’']t|doesn[’']t|hasn[’']t)\s*$", re.I)
LEVEL_PREP = re.compile(r"(?<!\w)(?:to|from|of|до|з|із|від)(?!\w)", re.I)

PARAM_UNITS = {"total": "count", "med": "count", "top": "count", "share": "pct", "c12": "pct",
               "a": "pct", "b": "pct", "y6": "pct", "rc": "pct", "pc": "pct", "pct": "pct",
               "wo": "pct", "tr": "trend", "lo": "trend", "hi": "trend", "t0": "trend", "t3": "trend",
               "ratio": "other"}


def _collect(obj, out: list[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, out)


def _to_float(sign: str, whole: str, frac: str | None) -> float:
    whole = re.sub("[" + SPACES + "]", "", whole)
    x = float(whole + ("." + frac[1:] if frac else ""))
    return -x if sign in ("-", "−", "–") else x


def _direction(text: str, start: int, end: int, sign: str) -> int:
    """Direction the answer states for a number: its explicit sign, else the words
    around it ("зросло на 14%", "на 14% менше"); +1 / -1, or 0 if none."""
    if sign:
        return -1 if sign in ("-", "−", "–") else 1
    after = text[end:end + 30]
    lead = re.match(r"\s*%?\s*(?:(?:/\s*(?:рік|р\.|yr|year)|на рік|за рік|per year|a year)\s*)?", after)
    m = DIR_AFTER.match(after, lead.end())
    if m and not CLAUSE_END.search(after[:m.start()]):
        return 1 if m.group("up") else -1
    before = text[max(0, start - 45):start]
    cut = list(CLAUSE_END.finditer(before))
    if cut:
        before = before[cut[-1].end():]
    words = list(DIR_BEFORE.finditer(before))
    if not words:
        return 0
    w = words[-1]
    between = before[w.end():]
    if NEGATION.search(before[:w.start()]) or LEVEL_PREP.search(between):
        return 0            # "не зростає", "fell to 5%", "з 10% до 14%": not a change figure
    if w.group(0).lower() in ("up", "down") and not re.fullmatch(r"\s*(?:by\s*)?", between):
        return 0            # "up to 14%" is a cap
    return 1 if w.group("up") else -1


def extract_numbers(text: str, with_direction: bool = False) -> list:
    """-> [(value, context, unit)] with unit in trend|pct|pm|count|any
    (+ direction -1/0/+1 stated by the wording when with_direction)."""
    masked = text
    for rx in SKIP_CONTEXT:
        masked = rx.sub(lambda m: " " * len(m.group(0)), masked)
    out = []
    for m in NUM.finditer(masked):
        sign, whole, frac = m.group(1), m.group(2), m.group(3)
        # "8,824" (English thousands) vs "3,08" (Ukrainian decimal comma)
        if frac and frac.startswith(",") and len(frac) == 4 and len(whole) <= 3 and not sign:
            whole, frac = whole + frac[1:], None
        x = _to_float(sign, whole, frac)
        after = text[m.end():m.end() + 30]
        if TREND_AFTER.search(after):
            unit = "trend"
        elif PM_AFTER.search(after):
            unit = "pm"
        elif after.lstrip().startswith("%"):
            unit = "pct"
        elif COUNT_AFTER.search(after):
            unit = "count"
        else:
            unit = "any"
        lo, hi = max(0, m.start() - 30), min(len(text), m.end() + 30)
        item = (x, text[lo:hi].replace("\n", " "), unit)
        if with_direction:
            item += (_direction(text, m.start(), m.end(), sign),)
        out.append(item)
    return out


def allowed_values(payload: dict) -> dict[str, list[float]]:
    """Quotable figures grouped by unit, so '30%/yr' is accepted only if some
    trend is ~30, not because an unrelated share happens to be 29.7%."""
    v: dict[str, list[float]] = {"trend": [], "pct": [], "pm": [], "count": [], "other": []}
    for r in payload["rows"]:
        if r.get("status") != "ok":
            continue
        tr = r["trend"]
        _collect([tr.get("pct_per_year"), tr.get("ci95"), tr.get("range_pct")], v["trend"])
        _collect(r["change"], v["pct"])
        _collect([r["spikes"].get("share_pct"), r["bots"].get("share_pct_last12"),
                  r["redirects"].get("share_pct_last12")], v["pct"])
        lv = r["level"]
        _collect([lv.get("views_per_million_last12"), lv.get("views_per_million_last3")], v["pm"])
        _collect([lv.get("views_per_month_last12"), lv.get("views_last12_total"),
                  lv.get("median_daily_views_last12")], v["count"])
        for d in r["spikes"].get("days", []):
            _collect([d.get("views"), d.get("baseline")], v["count"])
        _collect([r["seasonality"].get("peak_ratio")], v["other"])
        for m in r.get("articles", []):
            _collect([m.get("change_12m_pct"), m.get("share_pct")], v["pct"])
        for c in r.get("checks", []):  # numbers quoted inside the reasons
            for k, val in c.get("params", {}).items():
                if isinstance(val, str):
                    v[PARAM_UNITS.get(k, "other")] += [x for x, _, _ in extract_numbers(val)]
    rk = payload.get("ranking") or {}
    _collect([x.get("score") for x in rk.get("table", [])], v["other"])
    _collect(list((rk.get("weights") or {}).values()), v["other"])
    v["pct"] += v["trend"]
    return v


def matches(x: float, vals: list[float]) -> bool:
    for v in vals:
        tol = max(0.55, 0.015 * abs(v))
        if abs(x - v) <= tol or abs(abs(x) - abs(v)) <= tol:
            return True
    return False


def _signed_match(x: float, vals: list[float]) -> bool:
    return any(abs(x - v) <= max(0.55, 0.015 * abs(v)) for v in vals)


def run_check(payload: dict, text: str) -> dict:
    vals = allowed_values(payload)
    every = [x for group in vals.values() for x in group]
    found = extract_numbers(text, with_direction=True)
    unmatched = [{"number": x, "unit": unit, "context": ctx} for x, ctx, unit, _ in found
                 if abs(x) > 1 and not matches(x, every if unit == "any" else vals[unit])]
    # a supported magnitude with the wrong direction ("+14%" or "grew 14%" when the data say -14%)
    conflicts = []
    for x, ctx, unit, d in found:
        if unit not in ("pct", "trend") or abs(x) <= 1 or d == 0:
            continue
        stated = abs(x) * d
        if not _signed_match(stated, vals[unit]) and _signed_match(-stated, vals[unit]):
            conflicts.append({"number": stated, "context": ctx, "problem": "the data show the opposite direction"})
    warnings = []
    low = text.lower()
    for r in payload["rows"]:
        if r["status"] != "ok":
            uk = UK_BY_CODE.get(r["lang"], "")
            names = [r["lang_name"].lower()] + ([uk[:-2]] if len(uk) > 4 else [])
            if not (re.search(rf"\b{re.escape(r['lang'])}\b", text) or any(n in low for n in names if n)):
                warnings.append(f"the answer does not mention edition '{r['lang']}', which has no article")
            elif not SEMANTIC_MISSING.search(text):
                warnings.append(f"say explicitly that '{r['lang']}' has no article on the topic (content gap)")
    if any(r["status"] == "ok" for r in payload["rows"]) and not CONFIDENCE_WORDS.search(text):
        warnings.append("state the confidence level (high/medium/low) with its reason")
    for m in FOREIGN_SCRIPT.finditer(text):
        warnings.append(f"garbled text in another script: “{m.group(0)}” — rewrite that sentence in the user's language")
    return {"numbers_checked": len(found), "unsupported_numbers": unmatched, "direction_conflicts": conflicts,
            "warnings": warnings, "ok": not unmatched and not conflicts}


def cmd_check(a) -> int:
    payload, _ = load_run(a.run)
    if a.text:
        text = a.text
    elif a.answer == "-":
        text = sys.stdin.read()
    elif a.answer:
        text = Path(a.answer).read_text(encoding="utf-8")
    else:
        print("Error: give --answer FILE, --answer - (stdin) or --text '...'", file=sys.stderr)
        return 3
    res = run_check(payload, text)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if not res["ok"]:
        print(FIX_HINT, file=sys.stderr)
        return 5
    return 0


FIX_HINT = ("Fix: replace each unsupported number with the value from summary.md/results.json, or remove it; "
            "for a direction conflict fix the wording or sign (the data show the opposite). Then run check again.")
