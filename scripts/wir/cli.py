"""Command-line interface. Structured files go to --out; stdout gets a short
Markdown summary; progress and warnings go to stderr."""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import date
from pathlib import Path

from . import config, langs
from .analysis import Options, Topic, analyze
from .cache import Cache
from .fetch import Ctx
from .net import ApiError, Client, OfflineMiss, log
from .ranking import PRESETS, rank
from .resolve import Member, ResolveError, resolve_member
from .series import add_months, last_complete_month, month_label, parse_month_label

EXIT_OK, EXIT_NO_DATA, EXIT_ARGS, EXIT_AMBIGUOUS, EXIT_CHECK, EXIT_API = 0, 2, 3, 4, 5, 6

EPILOG = """exit codes: 0 ok · 2 nothing measurable (no articles) · 3 bad arguments ·
4 topic not found on Wikidata · 5 `check` found unsupported numbers · 6 Wikimedia API failure

examples:
  radar.py analyze --topic "intermittent fasting" --langs pl,cs
  radar.py analyze --topic astronomy --langs uk --months 36
  radar.py analyze --basket "Learning English: English language; English grammar; IELTS; TOEFL" --langs pl,cs,uk,de,tr
  radar.py analyze --from wir-runs/astronomy_uk_24m --add-langs pl --agent all-agents
  radar.py report --run wir-runs/astronomy_uk_24m --lang uk
  radar.py check --run wir-runs/astronomy_uk_24m --answer answer.md
"""


def skill_cmd() -> str:
    return f"uv run \"{(config.SKILL_ROOT / 'scripts' / 'radar.py').as_posix()}\""


def _slug(text: str) -> str:
    s = "".join(ch if ch.isalnum() else "-" for ch in text.lower())
    return "-".join(p for p in s.split("-") if p)[:48] or "run"


def _parse_basket(spec: str) -> dict:
    name, sep, rest = spec.partition(":")
    if not sep:
        raise ValueError('--basket needs "Name: term1; term2; ..." (a colon after the name).')
    terms = [x.strip() for x in rest.split(";") if x.strip()]
    if len(terms) < 2:
        raise ValueError("--basket needs at least two terms separated by ';'.")
    return {"name": name.strip(), "kind": "basket", "members": [{"query": q} for q in terms]}


def build_spec(a) -> dict:
    spec: dict = {}
    if a.from_run:
        p = Path(a.from_run) / "spec.json"
        if not p.exists():
            raise ValueError(f"--from: {p} not found. Pass a run directory printed by a previous analyze.")
        spec = json.loads(p.read_text(encoding="utf-8"))
        for t in spec["topics"]:  # keep resolved QIDs, re-resolve titles for (new) languages
            t["members"] = [{"query": m["query"], "qid": m.get("qid"),
                             "titles": {k: v["title"] for k, v in (m.get("articles") or {}).items()
                                        if v and v.get("source") == "user"}} for m in t["members"]]
    topics = [{"name": x, "kind": "topic", "members": [{"query": x}]} for x in (a.topic or [])]
    topics += [_parse_basket(b) for b in (a.basket or [])]
    if a.add_topic:
        spec.setdefault("topics", []).extend(
            {"name": x, "kind": "topic", "members": [{"query": x}]} for x in a.add_topic)
    if topics:
        spec["topics"] = topics
    if not spec.get("topics"):
        raise ValueError("Give --topic TEXT (repeatable), --basket 'Name: a; b' or --from RUN_DIR.")
    if a.qid:
        if len(spec["topics"]) != 1 or len(spec["topics"][0]["members"]) != 1:
            raise ValueError("--qid works with exactly one --topic.")
        spec["topics"][0]["members"][0]["qid"] = a.qid
    if a.title:
        if len(spec["topics"]) != 1 or len(spec["topics"][0]["members"]) != 1:
            raise ValueError("--title works with exactly one --topic.")
        titles = spec["topics"][0]["members"][0].setdefault("titles", {})
        for item in a.title:
            k, sep, v = item.partition("=")
            if not sep or not v.strip():
                raise ValueError(f"--title must look like cs=Přerušovaný půst (got {item!r}).")
            titles[langs.normalize(k)] = v.strip().replace("_", " ")
    if a.langs:
        spec["langs"] = langs.parse_list(a.langs)
    for extra in langs.parse_list(a.add_langs) if a.add_langs else []:
        spec.setdefault("langs", [])
        if extra not in spec["langs"]:
            spec["langs"].append(extra)
    if a.drop_langs:
        drop = set(langs.parse_list(a.drop_langs))
        spec["langs"] = [x for x in spec.get("langs", []) if x not in drop]
    if not spec.get("langs"):
        raise ValueError("Give --langs, e.g. --langs pl,cs (Wikipedia edition codes).")
    if len(spec["langs"]) * sum(len(t["members"]) for t in spec["topics"]) > 60:
        raise ValueError("Too many topic x language combinations (>60) for one run; split the request.")

    today = date.today()
    if a.end:
        end = parse_month_label(a.end)
    elif a.months or a.start or not spec.get("window"):
        end = last_complete_month(today)
    else:
        end = parse_month_label(spec["window"]["end"])
    latest = last_complete_month(today)
    if end > latest:
        log(f"end month {month_label(end)} is not complete yet; using {month_label(latest)}")
        end = latest
    if a.start:
        start = parse_month_label(a.start)
    elif a.months:
        start = add_months(end, -(a.months - 1))
    elif spec.get("window") and not a.end:
        start = parse_month_label(spec["window"]["start"])
    else:
        start = add_months(end, -23)
    earliest = add_months(date(2015, 7, 1), 12)
    if start < earliest:
        raise ValueError(f"The window must start at {month_label(earliest)} or later "
                         "(data begins 2015-07 and 12 earlier months are needed for comparison).")
    n = (end.year - start.year) * 12 + end.month - start.month + 1
    if not 12 <= n <= 120:
        raise ValueError(f"Window must be 12..120 months (got {n}).")
    spec["window"] = {"start": month_label(start), "end": month_label(end), "months": n}
    spec["agent"] = a.agent or spec.get("agent", "user")
    spec["access"] = a.access or spec.get("access", "all-access")
    if a.no_redirects:
        spec["redirects"] = False
    spec.setdefault("redirects", True)
    spec["preset"] = a.preset or spec.get("preset", "balanced")
    spec["weights"] = a.weights if a.weights is not None else spec.get("weights")
    return spec


def canonical_command(spec: dict, out: Path) -> str:
    parts = ["radar.py", "analyze"]
    for t in spec["topics"]:
        if t["kind"] == "basket":
            parts += ["--basket", f"{t['name']}: " + "; ".join(m["query"] for m in t["members"])]
        else:
            parts += ["--topic", t["members"][0]["query"]]
    parts += ["--langs", ",".join(spec["langs"]), "--start", spec["window"]["start"],
              "--end", spec["window"]["end"]]
    if spec["agent"] != "user":
        parts += ["--agent", spec["agent"]]
    if spec["access"] != "all-access":
        parts += ["--access", spec["access"]]
    if not spec["redirects"]:
        parts.append("--no-redirects")
    return " ".join(shlex.quote(p) for p in parts)


def _ctx(a) -> Ctx:
    return Ctx(Client(offline=getattr(a, "offline", False)), Cache())


def cmd_analyze(a) -> int:
    from .charts import save_chart
    from .summary import render_summary, write_outputs

    spec = build_spec(a)
    ctx = _ctx(a)
    topics = []
    for t in spec["topics"]:
        members = []
        for m in t["members"]:
            members.append(resolve_member(ctx, m["query"], spec["langs"], qid=m.get("qid"),
                                          user_titles=m.get("titles")))
        topics.append(Topic(t["name"], members, t["kind"]))
    spec["topics"] = [{"name": tp.name, "kind": tp.kind, "members": [m.to_dict() for m in tp.members]}
                      for tp in topics]
    w = spec["window"]
    opt = Options(parse_month_label(w["start"]), parse_month_label(w["end"]), spec["agent"],
                  spec["access"], spec["redirects"])
    rows = analyze(ctx, topics, spec["langs"], opt)
    ranking = rank([r.result for r in rows], spec["preset"], spec["weights"])
    if a.out:
        out = Path(a.out)
    else:
        name = "_".join([_slug("+".join(t["name"] for t in spec["topics"])), "-".join(spec["langs"]),
                         f"{w['months']}m"] + ([spec["agent"]] if spec["agent"] != "user" else [])
                        + ([spec["access"]] if spec["access"] != "all-access" else []))
        out = Path("wir-runs") / name
    out = out.resolve()
    payload = write_outputs(out, rows, spec, ranking, canonical_command(spec, out))
    title = ", ".join(t.name for t in topics) + " · " + ", ".join(spec["langs"])
    save_chart(rows, out / "chart.png", title)
    text = render_summary(payload, Path(out.as_posix()), skill_cmd())
    (out / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    log(f"done: {ctx.client.requests} API requests, {ctx.client.throttled} throttled, cache {ctx.cache.path}")
    ctx.cache.close()
    return EXIT_OK if any(r.result["status"] == "ok" for r in rows) else EXIT_NO_DATA


def cmd_resolve(a) -> int:
    codes = langs.parse_list(a.langs)
    ctx = _ctx(a)
    m: Member = resolve_member(ctx, a.topic, codes, qid=a.qid)
    out = {"query": m.query, "qid": m.qid, "label": m.label, "description": m.description,
           "ambiguous": m.ambiguous, "alternatives": m.alternatives,
           "articles": {k: (v.title if v else None) for k, v in m.articles.items()},
           "redirects": {k: len(v.redirects) for k, v in m.articles.items() if v}}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    ctx.cache.close()
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="radar.py", description=(
        "Wikipedia interest radar: compare how interest in topics changes across Wikipedia "
        "language editions, rate how trustworthy the change is, chart it, and build a one-page PDF."),
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=config.VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)

    an = sub.add_parser("analyze", help="resolve topics, fetch, normalize, test trends, rate trust, chart",
                        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    an.add_argument("--topic", action="append", help="topic in any language, e.g. 'intermittent fasting' (repeatable)")
    an.add_argument("--basket", action="append",
                    help="one topic measured by several articles: 'Name: term1; term2; term3' (repeatable)")
    an.add_argument("--add-topic", action="append", help="with --from: add a topic to the previous run")
    an.add_argument("--langs", help="Wikipedia edition codes, comma-separated: pl,cs,uk")
    an.add_argument("--add-langs", help="with --from: add editions")
    an.add_argument("--drop-langs", help="with --from: remove editions")
    an.add_argument("--months", type=int, help="window length in full months (default 24; 12..120)")
    an.add_argument("--start", help="first month YYYY-MM (instead of --months)")
    an.add_argument("--end", help="last month YYYY-MM (default: last complete month)")
    an.add_argument("--agent", choices=["user", "all-agents"], help="user = humans only (default)")
    an.add_argument("--access", choices=["all-access", "desktop", "mobile-web", "mobile-app"])
    an.add_argument("--no-redirects", action="store_true", help="do not add views of redirects")
    an.add_argument("--qid", help="force the Wikidata item for a single --topic, e.g. Q333")
    an.add_argument("--title", action="append", help="force an article title: cs=Přerušovaný půst (proxy)")
    an.add_argument("--preset", choices=sorted(PRESETS), help="ranking preset (default balanced)")
    an.add_argument("--weights", help="custom ranking weights: size=0.5,momentum=0.3,trust=0.2")
    an.add_argument("--from", dest="from_run", help="reuse a previous run directory (follow-up questions)")
    an.add_argument("--out", help="output directory (default ./wir-runs/<slug>)")
    an.add_argument("--offline", action="store_true", help="use only cached data")
    an.set_defaults(func=cmd_analyze)

    rs = sub.add_parser("resolve", help="show which article represents a topic in each edition (cheap)")
    rs.add_argument("topic")
    rs.add_argument("--langs", required=True)
    rs.add_argument("--qid")
    rs.add_argument("--offline", action="store_true")
    rs.set_defaults(func=cmd_resolve)

    from .commands import register
    register(sub)

    a = p.parse_args(argv)
    try:
        return a.func(a)
    except (ValueError, langs.UnknownLanguage) as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ARGS
    except ResolveError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_AMBIGUOUS
    except OfflineMiss as e:
        print(f"Error: {e}. Run without --offline.", file=sys.stderr)
        return EXIT_API
    except ApiError as e:
        print(f"Error: Wikimedia API problem: {e}. Wait a minute and retry the same command "
              "(cached data is reused).", file=sys.stderr)
        return EXIT_API
