"""`diff`: what changed between two runs (follow-ups, changed assumptions)."""
from __future__ import annotations

from .runio import load_run

SPEC_KEYS = ("langs", "window", "agent", "access", "redirects", "preset", "weights")


def _get(r: dict, path: str):
    cur = r
    for p in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


METRICS = [("per 1M", "level.views_per_million_last12"), ("12 mo change %", "change.change_12m_pct"),
           ("trend %/yr", "trend.pct_per_year")]


def cmd_diff(a) -> int:
    (p_old, _), (p_new, _) = load_run(a.runs[0]), load_run(a.runs[1])
    lines = ["# diff", "## Assumptions"]
    changed = False
    for k in SPEC_KEYS:
        o, n = p_old["spec"].get(k), p_new["spec"].get(k)
        if o != n:
            changed = True
            lines.append(f"- {k}: {o} → {n}")
    ot = [t["name"] for t in p_old["spec"]["topics"]]
    nt = [t["name"] for t in p_new["spec"]["topics"]]
    if ot != nt:
        changed = True
        lines.append(f"- topics: {ot} → {nt}")
    if not changed:
        lines.append("- none (same settings; differences come from newer data only)")
    lines.append("## Rows")
    old_rows = {(r["topic"], r["lang"]): r for r in p_old["rows"]}
    verdict_changed = False
    for r in p_new["rows"]:
        key = (r["topic"], r["lang"])
        o = old_rows.pop(key, None)
        if o is None:
            lines.append(f"- NEW {r['lang']}/{r['topic']}: {r['verdict']} ({r.get('confidence')})")
            continue
        parts = []
        for label, path in METRICS:
            ov, nv = _get(o, path), _get(r, path)
            if ov is not None and nv is not None and abs(nv - ov) >= 0.05:
                parts.append(f"{label} {ov:g} → {nv:g}")
        vo, vn = f"{o['verdict']}/{o.get('confidence')}", f"{r['verdict']}/{r.get('confidence')}"
        verdict_changed |= o["verdict"] != r["verdict"]
        verdict = f"verdict {vo} → {vn}" if vo != vn else f"verdict unchanged ({vn})"
        lines.append(f"- {r['lang']}/{r['topic']}: {verdict}" + (f"; {', '.join(parts)}" if parts else ""))
    for (t, lang), o in old_rows.items():
        lines.append(f"- REMOVED {lang}/{t}")
    ro, rn = p_old.get("ranking"), p_new.get("ranking")
    if ro and rn:
        lo = [f"{x['lang']}/{x['topic']}" for x in ro["table"]]
        ln = [f"{x['lang']}/{x['topic']}" for x in rn["table"]]
        lines.append("## Ranking")
        lines.append(f"- before: {', '.join(lo[:5])}")
        lines.append(f"- after:  {', '.join(ln[:5])}")
    if changed:
        lines.append("Conclusion " + ("changed — explain which assumption drives it." if verdict_changed
                                      else "(verdicts) does not depend on the changed assumption."))
    else:
        lines.append("Conclusion unchanged.")
    print("\n".join(lines))
    return 0
