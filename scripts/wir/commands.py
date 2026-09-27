"""Secondary subcommands: report, check, verify, diff (imported lazily)."""
from __future__ import annotations

import argparse


def _report(a):
    from .report import cmd_report
    return cmd_report(a)


def _check(a):
    from .check import cmd_check
    return cmd_check(a)


def _verify(a):
    from .verify import cmd_verify
    return cmd_verify(a)


def _diff(a):
    from .diffrun import cmd_diff
    return cmd_diff(a)


def register(sub) -> None:
    rp = sub.add_parser("report", help="one-page PDF (+PNG preview) from an analyze run")
    rp.add_argument("--run", required=True, help="run directory printed by analyze")
    rp.add_argument("--lang", choices=["uk", "en"], default="en", help="report language")
    rp.add_argument("--title", help="report title (default: topic + editions)")
    rp.add_argument("--notes", help="2-4 sentences of recommendation written by you (the agent)")
    rp.add_argument("--notes-file", help="file with the notes (UTF-8)")
    rp.add_argument("--out", help="PDF path (default <run>/report.pdf)")
    rp.set_defaults(func=_report)

    ck = sub.add_parser("check", help="verify that numbers in an answer/notes exist in results.json")
    ck.add_argument("--run", required=True)
    ck.add_argument("--answer", help="file with the answer text (UTF-8); '-' = stdin")
    ck.add_argument("--text", help="answer text inline")
    ck.set_defaults(func=_check)

    vf = sub.add_parser("verify", help="robustness re-check: devices, bots, window trims, spot check")
    vf.add_argument("--run", required=True)
    vf.add_argument("--offline", action="store_true")
    vf.set_defaults(func=_verify)

    df = sub.add_parser("diff", help="what changed between two runs (follow-ups, changed assumptions)")
    df.add_argument("--runs", nargs=2, required=True, metavar=("OLD", "NEW"))
    df.set_defaults(func=_diff)

    _ = argparse  # keep import for type hints in editors
