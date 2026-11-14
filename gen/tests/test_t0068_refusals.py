"""T-0068 (refusals hold), gen side: every refuse.* row is exactly the refusal string (D-0027 (refusal string)) with no
spans; each system has one pricing, one clinical and one real-data refusal plus the extra stub item. The app side
(no answerable row matches the validator's CLINICAL or advisory + COMMERCIAL pattern) is in app/tests."""
from collections import Counter

from bia562gen.seam import REFUSAL

from .v1_helpers import qa


def test_refusal_rows_exact(v1_out):
    rows = qa(v1_out)
    ref = [q for q in rows if q["question_type"].startswith("refuse.")]
    assert len(ref) == 3 * 180
    for q in ref:
        assert q["answer"] == REFUSAL and q["spans"] == {} and q["source_anchor"] is None, q["qa_id"]
        assert q["answer_type"] == "unanswerable" and q["value"] is None, q["qa_id"]
    per = Counter((q["system_id"], q["question_type"]) for q in ref)
    assert set(per.values()) == {1}
    unans = Counter(q["system_id"] for q in rows if q["question_type"] == "unanswerable")
    assert set(unans.values()) == {6}, "five stub items + the extra stub item per system"
