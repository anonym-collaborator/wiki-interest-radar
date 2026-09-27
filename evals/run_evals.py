#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf>=4,<7", "numpy>=1.26,<3"]
# ///
"""Run the skill's evals end to end with Claude Code in headless mode.

Each case runs in a fresh temporary project: with_skill copies the skill into
<workdir>/.claude/skills/, without_skill runs the same prompt with no skill.
The transcript (stream-json), the final answer, cost/tokens/turns and a
grading.json per run are saved; benchmark.json + RESULTS.md aggregate them.

    uv run evals/run_evals.py --cases if-pl-cs,astro-uk --arms with_skill,without_skill --runs 1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_NAME = SKILL_DIR.name
COPY = ["SKILL.md", "LICENSE", "scripts", "references", "assets"]
ALLOWED = ["Bash(uv run:*)", "Bash(uv:*)", "Bash(python:*)", "Bash(python3:*)", "Bash(curl:*)",
           "Bash(ls:*)", "Bash(cat:*)", "Bash(mkdir:*)", "Bash(cd:*)", "Bash(echo:*)", "Bash(head:*)",
           "Bash(find:*)", "Read", "Write", "Edit", "Glob", "Grep", "Skill", "WebFetch", "WebSearch", "TodoWrite"]


def copy_skill(dst: Path) -> None:
    target = dst / ".claude" / "skills" / SKILL_NAME
    target.mkdir(parents=True, exist_ok=True)
    for item in COPY:
        src = SKILL_DIR / item
        if src.is_dir():
            shutil.copytree(src, target / item, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                            dirs_exist_ok=True)
        elif src.exists():
            shutil.copy2(src, target / item)


def claude_exe() -> str:
    """The npm shim (claude.cmd) mangles non-ASCII arguments on Windows; call the
    native binary it wraps and pass the prompt on stdin."""
    found = shutil.which("claude")
    if found and found.lower().endswith((".cmd", ".bat")):
        exe = Path(found).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
    return found or "claude"


def run_claude(prompt: str, cwd: Path, model: str, max_turns: int, resume: str | None = None) -> list[dict]:
    cmd = [claude_exe(), "-p", "--model", model, "--output-format", "stream-json", "--verbose",
           "--max-turns", str(max_turns), "--permission-mode", "acceptEdits", "--allowedTools", *ALLOWED]
    if resume:
        cmd += ["--resume", resume]
    env = {**os.environ, "CLAUDE_CODE_SUBAGENT_MODEL": model}
    proc = subprocess.run(cmd, cwd=cwd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=1200, env=env)
    events = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    if not events:
        events.append({"type": "error", "stderr": proc.stderr[-2000:], "code": proc.returncode})
    return events


def tool_uses(events: list[dict]) -> list[dict]:
    out = []
    for ev in events:
        if ev.get("type") == "assistant":
            for block in (ev.get("message") or {}).get("content", []):
                if block.get("type") == "tool_use":
                    out.append({"name": block.get("name"), "input": block.get("input", {})})
    return out


def final(events: list[dict]) -> dict:
    res = [e for e in events if e.get("type") == "result"]
    return res[-1] if res else {}


def skill_used(tools: list[dict]) -> bool:
    for t in tools:
        inp = json.dumps(t["input"], ensure_ascii=False)
        if t["name"] == "Skill" and SKILL_NAME in inp:
            return True
        if SKILL_NAME in inp and ("SKILL.md" in inp or "radar.py" in inp):
            return True
    return False


def pdf_pages(workdir: Path) -> list[tuple[str, int]]:
    from pypdf import PdfReader
    out = []
    for p in workdir.rglob("*.pdf"):
        if ".claude" in p.parts:
            continue
        try:
            out.append((str(p), len(PdfReader(str(p)).pages)))
        except Exception:  # noqa: BLE001
            out.append((str(p), -1))
    return out


def numbers_supported(workdir: Path, answer: str) -> tuple[bool | None, str]:
    runs = sorted(workdir.rglob("results.json"), key=lambda p: p.stat().st_mtime)
    runs = [r for r in runs if ".claude" not in r.parts]
    if not runs:
        return None, "no results.json produced (numbers not traceable)"
    ans = workdir / "_answer_for_check.md"
    ans.write_text(answer, encoding="utf-8")
    # an answer may cite several runs (follow-ups): pass if any single run supports it,
    # otherwise pass if every number is supported by the union of the runs
    radar = SKILL_DIR / "scripts" / "radar.py"
    last = ""
    for r in reversed(runs):
        p = subprocess.run(["uv", "run", str(radar), "check", "--run", str(r.parent), "--answer", str(ans)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode == 0:
            return True, f"all numbers found in {r.parent.name}"
        last = p.stdout[-1500:]
    if len(runs) > 1:
        sys.path.insert(0, str(SKILL_DIR / "scripts"))
        from wir.check import allowed_values, extract_numbers, matches  # noqa: E402
        pool: dict[str, list[float]] = {}
        for r in runs:
            for k, v in allowed_values(json.loads(r.read_text(encoding="utf-8"))).items():
                pool.setdefault(k, []).extend(v)
        every = [x for g in pool.values() for x in g]
        bad = [(x, u) for x, _, u in extract_numbers(answer)
               if abs(x) > 1 and not matches(x, every if u == "any" else pool.get(u, []))]
        if not bad:
            return True, f"all numbers found across {len(runs)} runs"
        return False, f"unsupported across runs: {bad[:5]}"
    return False, last


def grade(case: dict, workdir: Path, answer: str, tools: list[dict]) -> list[dict]:
    res = []
    for a in case["assertions"]:
        t = a["type"]
        if t == "skill_used":
            ok, ev = skill_used(tools), "Skill tool / radar.py calls"
        elif t == "skill_not_used":
            ok, ev = not skill_used(tools), "no Skill tool / radar.py calls"
        elif t == "regex":
            m = re.search(a["pattern"], answer, re.I)
            ok, ev = bool(m), (m.group(0) if m else "no match")
        elif t == "tool_arg":
            hit = [x for x in tools if x["name"] == "Bash" and re.search(a["pattern"], x["input"].get("command", ""))]
            ok, ev = bool(hit), (hit[0]["input"]["command"][:200] if hit else "no matching command")
        elif t == "pdf_one_page":
            pdfs = pdf_pages(workdir)
            ok, ev = any(n == 1 for _, n in pdfs), (f"{pdfs}" if pdfs else "no PDF found")
        elif t == "numbers_supported":
            ok, ev = numbers_supported(workdir, answer)
            ok = bool(ok)
        else:
            ok, ev = False, f"unknown assertion {t}"
        res.append({"assertion": a.get("name", t), "passed": ok, "evidence": ev})
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="all")
    ap.add_argument("--arms", default="with_skill")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--iteration", default=datetime.now().strftime("iter-%Y%m%d-%H%M"))
    ap.add_argument("--root", default="C:/Temp/wir-evals" if os.name == "nt" else "/tmp/wir-evals")
    a = ap.parse_args()
    spec = json.loads((SKILL_DIR / "evals" / "evals.json").read_text(encoding="utf-8"))
    cases = spec["evals"] if a.cases == "all" else [c for c in spec["evals"] if c["id"] in a.cases.split(",")]
    out_dir = SKILL_DIR / "evals" / "results" / a.iteration
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in cases:
        for arm in a.arms.split(","):
            for k in range(1, a.runs + 1):
                wd = Path(a.root) / a.iteration / case["id"] / f"{arm}-{k}"
                if wd.exists():
                    shutil.rmtree(wd)
                wd.mkdir(parents=True)
                if arm == "with_skill":
                    copy_skill(wd)
                t0 = time.time()
                ev = run_claude(case["prompt"], wd, a.model, a.max_turns)
                answers = [final(ev).get("result", "")]
                all_ev = list(ev)
                if case.get("followup") and final(ev).get("session_id"):
                    ev2 = run_claude(case["followup"], wd, a.model, a.max_turns, resume=final(ev)["session_id"])
                    answers.append(final(ev2).get("result", ""))
                    all_ev += ev2
                dur = time.time() - t0
                tools = tool_uses(all_ev)
                answer = answers[-1]
                results = [e for e in all_ev if e.get("type") == "result"]
                usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
                for r in results:
                    u = r.get("usage") or {}
                    usage["input"] += u.get("input_tokens", 0)
                    usage["output"] += u.get("output_tokens", 0)
                    usage["cache_read"] += u.get("cache_read_input_tokens", 0)
                    usage["cache_write"] += u.get("cache_creation_input_tokens", 0)
                metrics = {"case": case["id"], "arm": arm, "run": k, "seconds": round(dur, 1),
                           "turns": sum(r.get("num_turns", 0) for r in results),
                           "cost_usd": round(sum(r.get("total_cost_usd", 0) or 0 for r in results), 4),
                           "tool_calls": len(tools), "usage": usage,
                           "models": sorted({m for r in results for m in (r.get("modelUsage") or {}).keys()}),
                           "errors": [e for e in all_ev if e.get("type") == "error"]}
                grading = grade(case, wd, answer, tools)
                passed = sum(g["passed"] for g in grading)
                dst = out_dir / case["id"] / f"{arm}-{k}"
                dst.mkdir(parents=True, exist_ok=True)
                (dst / "transcript.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in all_ev),
                                                      encoding="utf-8")
                (dst / "answer.md").write_text("\n\n---\n\n".join(answers), encoding="utf-8")
                (dst / "tools.json").write_text(json.dumps(tools, ensure_ascii=False, indent=1), encoding="utf-8")
                (dst / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
                (dst / "grading.json").write_text(json.dumps({"results": grading, "passed": passed,
                                                              "total": len(grading)}, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
                for pdf, _ in pdf_pages(wd):
                    shutil.copy2(pdf, dst / Path(pdf).name)
                rows.append({**metrics, "passed": passed, "total": len(grading)})
                print(f"{case['id']:<15} {arm:<13} run{k}: {passed}/{len(grading)} pass · {metrics['tool_calls']} tools · "
                      f"{metrics['turns']} turns · ${metrics['cost_usd']} · {metrics['seconds']}s", flush=True)
    bench = {}
    for arm in sorted({r["arm"] for r in rows}):
        rs = [r for r in rows if r["arm"] == arm]
        rate = [r["passed"] / r["total"] for r in rs]
        bench[arm] = {"pass_rate": round(statistics.mean(rate), 3),
                      "seconds": round(statistics.mean(r["seconds"] for r in rs), 1),
                      "cost_usd": round(statistics.mean(r["cost_usd"] for r in rs), 4),
                      "tool_calls": round(statistics.mean(r["tool_calls"] for r in rs), 1), "runs": len(rs)}
    (out_dir / "benchmark.json").write_text(json.dumps({"rows": rows, "summary": bench}, indent=1), encoding="utf-8")
    lines = [f"# {a.iteration} · model {a.model}", "", "| case | arm | run | pass | tools | turns | cost $ | s |",
             "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {r['case']} | {r['arm']} | {r['run']} | {r['passed']}/{r['total']} | {r['tool_calls']} | "
              f"{r['turns']} | {r['cost_usd']} | {r['seconds']} |" for r in rows]
    lines += ["", "| arm | pass rate | mean tools | mean cost $ | mean s | runs |", "|---|---|---|---|---|---|"]
    lines += [f"| {k} | {v['pass_rate']:.0%} | {v['tool_calls']} | {v['cost_usd']} | {v['seconds']} | {v['runs']} |"
              for k, v in bench.items()]
    (out_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-(len(bench) + 2):]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
