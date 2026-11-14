"""T-0069 (status, not number): a not-ok or not-available metric's span is its label, its value is null and the span
has no digit; national A6-A9 stay "not available: <reason>" (AS-0066 (national A6-A9 stay not available))."""
import re

from .v1_helpers import base, qa, terms

NAT_NA = ("nat_state", "nat_subs", "nat_sites", "nat_sites_by_specialty")


def test_status_fields(v1_out):
    n_bad = 0
    for sid, fields in terms(v1_out, "EXH").items():
        for k, f in fields.items():
            st = f["qualifier"]["status"]
            if st != "ok":
                n_bad += 1
                assert f["value"] is None and f["span"] == st and not re.search(r"\d", f["span"]), (sid, k, f)
            else:
                assert f["value"] is not None, (sid, k)
        for k in NAT_NA:
            assert fields[k]["value"] is None and fields[k]["span"].startswith("not available: "), (sid, k)
    assert n_bad > 180, "the real data has statuses to check (too few in-state peers, undefined, n/a)"


def test_status_answers(v1_out):
    for q in qa(v1_out):
        if q["question_type"].startswith("metric.") and q["value"] is None:
            assert not re.search(r"\d", q["spans"]["S1"]["text"]), q["qa_id"]
