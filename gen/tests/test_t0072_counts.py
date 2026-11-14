"""T-0072 (counts): 180 systems split 135 / 45, exactly one EXH1 per system, the manifest's doc and QA counts agree
with the files, at least 15% unanswerable per split; and the number pin, per the Architect's GATE 2 ruling: 623 docs
(468 / 155) and 8,363 Q&A rows (6,273 / 2,090). F-0028 records the gap against the spec's estimate."""
import json
from collections import Counter

from .v1_helpers import SPLITS

PIN = {"train": {"docs": 468, "qa_rows": 6273}, "test": {"docs": 155, "qa_rows": 2090}}


def test_counts_structural(v1_out):
    m = json.loads((v1_out / "manifest.json").read_text())
    assert len(m["split"]["train"]["systems"]) == 135 and len(m["split"]["test"]["systems"]) == 45
    allsys = set(m["split"]["train"]["systems"]) | set(m["split"]["test"]["systems"])
    assert len(allsys) == 180
    exh = Counter()
    for sp in SPLITS:
        docs = sorted((v1_out / sp / "docs").glob("*.md"))
        assert m["counts"][sp]["docs"] == len(docs)
        qa = (v1_out / sp / "qa.jsonl").read_text().splitlines()
        assert m["counts"][sp]["qa_rows"] == len(qa)
        assert m["counts"][sp]["unanswerable_rate"] >= 0.15
        for p in docs:
            if p.stem.endswith("-EXH1"):
                exh[p.stem.split("-")[1]] += 1
        for kind in ("MSA1", "P1"):
            assert sum(p.stem.endswith(kind) for p in docs) == m["counts"][sp]["systems"], (sp, kind)
    assert set(exh) == allsys and set(exh.values()) == {1}


def test_counts_pinned(v1_out):
    m = json.loads((v1_out / "manifest.json").read_text())
    for sp in SPLITS:
        assert len(list((v1_out / sp / "docs").glob("*.md"))) == PIN[sp]["docs"], sp
        assert len((v1_out / sp / "qa.jsonl").read_text().splitlines()) == PIN[sp]["qa_rows"], sp
        assert {k: m["counts"][sp][k] for k in ("docs", "qa_rows")} == PIN[sp], sp
    assert sum(v["docs"] for v in PIN.values()) == 623 and sum(v["qa_rows"] for v in PIN.values()) == 8363
