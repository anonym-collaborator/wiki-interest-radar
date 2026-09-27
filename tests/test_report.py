"""The PDF must always be exactly one page, in both languages, for 1 and 9+ rows."""
from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from conftest import Synthetic, make_topic, options
from wir import analysis
from wir.report import build_pdf
from wir.summary import write_outputs


def _run_dir(tmp_path: Path, fake_api, n_langs: int) -> Path:
    fake_api(Synthetic(base=300, growth=-0.2, noise=0.05))
    codes = ["cs", "pl", "uk", "de", "fr", "es", "it", "pt", "tr", "ro"][:n_langs]
    rows = []
    for c in codes:
        topic = make_topic(lang=c, title=f"Article {c}")
        rows.append(analysis.analyze_row(None, topic, c, options()))
    spec = {"topics": [{"name": "test topic", "kind": "topic",
                        "members": [{"label_uk": "тестова тема", **m.to_dict()} for m in rows[0].topic.members]}],
            "langs": codes, "agent": "user", "access": "all-access", "redirects": True}
    out = tmp_path / f"run{n_langs}"
    write_outputs(out, rows, spec, None, "radar.py analyze --topic test")
    return out


@pytest.mark.parametrize("n_langs,ui", [(1, "uk"), (3, "en"), (10, "uk")])
def test_report_is_one_page(tmp_path, fake_api, n_langs, ui):
    run = _run_dir(tmp_path, fake_api, n_langs)
    notes = "Коротка рекомендація для команди. " * 12
    pdf = build_pdf(run, ui, None, notes[:600], run / "report.pdf")
    assert len(PdfReader(str(pdf)).pages) == 1
    assert pdf.with_suffix(".png").exists()
