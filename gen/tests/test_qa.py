"""T-0032 unanswerable >= 15% per split; QA record shape (§7.7 + D-0020); T-0014 SYNTHETIC stamp."""
import pytest

from bia562gen import checks
from bia562gen.generate import GenerationError, generate
from bia562gen.seam import REFUSAL
from bia562gen.specs.schema_stub import StubV0Spec

from .conftest import SEED

KEYS_77 = {"qa_id", "doc_id", "system_id", "family", "question", "answer", "answer_type", "source_anchor", "spans"}


def test_unanswerable_at_least_15pct(out):
    r = checks.unanswerable_rate(out)
    assert r["train"] >= 0.15 and r["test"] >= 0.15, r


class FewUnanswerable(StubV0Spec):
    def qa(self, ds):
        return [q for q in super().qa(ds) if q.answer_type != "unanswerable"]


def test_generator_refuses_low_unanswerable(tmp_path, systems):
    with pytest.raises(GenerationError, match="unanswerable rate"):
        generate(FewUnanswerable(), systems, tmp_path / "x", SEED)


def test_qa_record_shape(out):
    for sp in ("train", "test"):
        for q in checks.load_qa(out, sp):
            assert KEYS_77 <= set(q) and q["synthetic"] is True
            assert "span" not in q  # G-04: spans dict is canonical
            if q["answer_type"] == "unanswerable":
                assert q["answer"] == REFUSAL and q["spans"] == {} and q["source_anchor"] is None
            else:
                assert "{S1}" in q["answer"] and q["spans"]["S1"]["anchor"] == q["source_anchor"]


def test_question_type_coverage(out):
    types = {q["question_type"] for q in checks.load_qa(out, "train")}
    assert {"expiration_date", "amendment_exclusivity", "proposal_get", "unanswerable"} <= types


def test_synthetic_stamp(out):
    assert checks.synthetic_stamp(out) == []


def test_stamp_cites_decisions_by_name(out):
    """T-0014: the stamp cites decisions by name, never a bare number (GATE 2 STAMP fix), and docs carry it verbatim."""
    import re
    from bia562gen import generate as G
    assert "D-0022 (fake data)" in G.STAMP
    assert re.findall(r"D-\d{4}(?! \([a-z])", G.STAMP) == [], G.STAMP
    doc = next((out / "train" / "docs").glob("*.md")).read_text()
    assert G.STAMP in doc
