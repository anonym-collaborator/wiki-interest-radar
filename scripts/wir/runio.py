"""Load a finished run directory (results.json + data.csv) back into rows."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

from .series import parse_month_label


@dataclass
class TopicRef:
    name: str


@dataclass
class LoadedRow:
    topic: TopicRef
    lang: str
    result: dict
    months: list[date] = field(default_factory=list)
    raw: np.ndarray | None = None
    proj: np.ndarray | None = None
    spike_months: list[date] = field(default_factory=list)


def load_run(run: str | Path) -> tuple[dict, list[LoadedRow]]:
    run = Path(run)
    rp = run / "results.json"
    if not rp.exists():
        raise ValueError(f"{rp} not found. Pass the run directory printed by `analyze`.")
    payload = json.loads(rp.read_text(encoding="utf-8"))
    series: dict[tuple[str, str], list[tuple[date, float, float]]] = {}
    dp = run / "data.csv"
    if dp.exists():
        with dp.open(encoding="utf-8") as f:
            for rec in csv.DictReader(f):
                series.setdefault((rec["topic"], rec["lang"]), []).append(
                    (parse_month_label(rec["month"]), float(rec["views"]), float(rec["edition_views"])))
    rows = []
    for r in payload["rows"]:
        lr = LoadedRow(TopicRef(r["topic"]), r["lang"], r)
        pts = sorted(series.get((r["topic"], r["lang"]), []))
        if pts:
            lr.months = [p[0] for p in pts]
            lr.raw = np.array([p[1] for p in pts])
            lr.proj = np.array([p[2] for p in pts])
            sp = r.get("spikes") or {}
            if "months" in sp:
                lr.spike_months = [parse_month_label(m) for m in sp["months"]]
            else:
                lr.spike_months = sorted({date.fromisoformat(s["date"]).replace(day=1) for s in sp.get("days", [])})
        rows.append(lr)
    return payload, rows
