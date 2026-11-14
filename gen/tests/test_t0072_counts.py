"""T-0072 (counts, structural): 180 systems split 135 / 45, exactly one EXH1 per system, the manifest's doc and QA
counts agree with the files, at least 15% unanswerable per split. The NUMBER pin of the doc and QA totals is
PENDING the Architect's ruling on the post-regen counts (GATE 2 banked ruling 1: report first, then pin)."""
import json
from collections import Counter

from .v1_helpers import SPLITS


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
