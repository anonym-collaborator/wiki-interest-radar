#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf>=4,<7", "numpy>=1.26,<3"]
# ///
"""Grade runs executed outside run_evals.py (e.g. Claude Code subagents on Haiku).

Each work directory must contain answer.md (the final answer shown to the user);
artifacts (wir-runs/*/results.json, PDFs) are inspected in place.

    uv run evals/grade_dir.py --root C:/Temp/wir-evals/haiku-it1 --out evals/results/haiku-it1
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from run_evals import SKILL_DIR, numbers_supported, pdf_pages

ARTIFACT_ASSERTIONS = {"skill_used", "tool_arg"}
# Without the skill there is no radar.py run and no results.json to trace numbers to,
# so these assertions say nothing about the baseline's answer quality: not scored there.
NOT_SCORED_WITHOUT_SKILL = {"skill_used", "numbers_supported", "tool_arg"}


def spec_checks(workdir: Path, pattern: str) -> tuple[bool, str]:
    """tool_arg fallback: look for the pattern in the saved specs/commands of runs."""
    for p in workdir.rglob("results.json"):
        if ".claude" in p.parts:
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        blob = json.dumps(data.get("spec", {})) + " " + data.get("command", "")
        if pattern == "--from":
            if len(list(workdir.rglob("results.json"))) >= 2:
                return True, "two runs in the work dir (follow-up reused the first)"
        elif re.search(pattern, blob):
            return True, f"{p.parent.name}: {data.get('command', '')[:160]}"
    return False, "no run with that setting"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--meta", help="JSON file with per-run metrics {case/arm: {tool_calls, tokens, seconds}}")
    a = ap.parse_args()
    spec = {c["id"]: c for c in json.loads((SKILL_DIR / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]}
    meta = json.loads(Path(a.meta).read_text(encoding="utf-8")) if a.meta else {}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for case_dir in sorted(Path(a.root).iterdir()):
        case = spec.get(case_dir.name)
        if not case:
            continue
        for arm_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
            ans_p = arm_dir / "answer.md"
            if not ans_p.exists():
                continue
            answer = ans_p.read_text(encoding="utf-8")
            baseline = arm_dir.name.startswith("without")
            res = []
            for asr in case["assertions"]:
                t = asr["type"]
                if baseline and t in NOT_SCORED_WITHOUT_SKILL:
                    continue
                if t == "skill_used":
                    used = any(arm_dir.rglob("results.json"))
                    res.append({"assertion": "skill used", "passed": used,
                                "evidence": "results.json produced by radar.py" if used else "no radar.py run"})
                elif t == "skill_not_used":
                    res.append({"assertion": "skill not used", "passed": not any(arm_dir.rglob("results.json")),
                                "evidence": ""})
                elif t == "regex":
                    m = re.search(asr["pattern"], answer, re.I)
                    res.append({"assertion": asr["name"], "passed": bool(m), "evidence": m.group(0) if m else "no match"})
                elif t == "tool_arg":
                    ok, ev = spec_checks(arm_dir, asr["pattern"])
                    res.append({"assertion": asr["name"], "passed": ok, "evidence": ev})
                elif t == "pdf_one_page":
                    pdfs = pdf_pages(arm_dir)
                    res.append({"assertion": "one-page PDF", "passed": any(n == 1 for _, n in pdfs),
                                "evidence": str(pdfs) if pdfs else "no PDF"})
                elif t == "numbers_supported":
                    ok, ev = numbers_supported(arm_dir, answer)
                    res.append({"assertion": "numbers supported by results.json", "passed": bool(ok), "evidence": ev})
            passed = sum(r["passed"] for r in res)
            key = f"{case_dir.name}/{arm_dir.name}"
            dst = out / case_dir.name / arm_dir.name
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ans_p, dst / "answer.md")
            for pdf, _ in pdf_pages(arm_dir):
                shutil.copy2(pdf, dst / Path(pdf).name)
            (dst / "grading.json").write_text(json.dumps({"results": res, "passed": passed, "total": len(res),
                                                          "metrics": meta.get(key, {})}, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
            rows.append((case_dir.name, arm_dir.name, passed, len(res), meta.get(key, {}), res))
    lines = ["| case | arm | pass | tool calls | tokens | seconds | failed assertions |", "|---|---|---|---|---|---|---|"]
    for c, arm, p, n, m, res in rows:
        failed = "; ".join(f"{r['assertion']}" for r in res if not r["passed"]) or "—"
        lines.append(f"| {c} | {arm} | {p}/{n} | {m.get('tool_calls', '')} | {m.get('tokens', '')} | "
                     f"{m.get('seconds', '')} | {failed} |")
    for arm in ("with_skill", "without_skill"):
        rs = [(p, n) for _, a2, p, n, _, _ in rows if a2 == arm]
        if rs:
            lines.append(f"| **{arm}** | | **{sum(p for p, _ in rs)}/{sum(n for _, n in rs)}** | | | | |")
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
