"""T-0068 (app part): in gen/out qa.jsonl every refusal row answers exactly the app's refusal string, and no answer or
answerable question trips the app validator's clinical or advice rules (F-0027). Refusal and unanswerable
questions are meant to ask for clinical or advisory content; only their answers are checked. Mutation: refusal_text."""
import json

from brief import config, contracts, validator


def _trips(t):
    """The validator's own clinical and advice rules (validate() minus the token and digit checks, which Q&A text
    is not subject to): a clinical word anywhere, 'should charge', or advice and a commercial term in one sentence."""
    if validator.CLINICAL.search(t) or validator.SHOULD_CHARGE.search(t):
        return True
    return any(validator.ADVISORY.search(x) and validator.COMMERCIAL.search(x) for x in validator.SENT.split(t))


def _rows():
    for split in ("train", "test"):
        for line in (config.GEN_OUT / split / "qa.jsonl").read_text().splitlines():
            yield json.loads(line)


def test_refusal_rows_use_app_string():
    refusals = [r for r in _rows() if r["question_type"].startswith("refuse.")]
    assert len(refusals) == 3 * 180
    assert {r["answer"] for r in refusals} == {contracts.REFUSAL}
    unans = [r for r in _rows() if r["answer_type"] == "unanswerable"]
    assert unans and all(r["answer"] == contracts.REFUSAL for r in unans)


def test_no_clinical_or_advisory_text():
    bad = []
    for r in _rows():
        for part in (("question", "answer") if r["answer_type"] != "unanswerable" else ("answer",)):
            t = r[part]
            if _trips(t):
                bad.append((r["qa_id"], part, t))
    assert not bad, (len(bad), bad[:5])
