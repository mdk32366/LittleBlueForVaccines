"""T-0036 contract Q&A (LLM off, TermSet lookup): answers cite only this system's docs, every cited span is verbatim
in its clause, lookups agree with gen/out ground truth, and unknowns get D-0027 (refusal string)."""
import json

from brief import config, contracts

SAMPLE = ["SYNCP000001", "SYNCP000002", "SYNCP000025", "SYNCP000180"]


def test_ground_truth_agreement():
    n = 0
    for sid in SAMPLE:
        for q in contracts.system_questions(sid):
            res = contracts.answer(sid, q["question"])
            for h in res["citations"]:
                assert h["anchor"].split("#")[0].split("-")[1] == sid, (sid, h["anchor"])
                assert h["verbatim"] and h["span"] in h["clause_text"]
            if q.get("field_name"):
                assert res["answer"] == q["spans"]["S1"]["text"], q["qa_id"]
                assert res["citations"][0]["anchor"] == q["spans"]["S1"]["anchor"]
                n += 1
            elif q["answer_type"] == "unanswerable":
                assert res["answer"] == contracts.REFUSAL == "not in the contracts"
    assert n > 40


def test_free_text_isolated():
    for sid in SAMPLE:
        res = contracts.answer(sid, "When does the MSA expire?")
        assert res["citations"] and all(f"-{sid}-" in h["anchor"] for h in res["citations"])
        terms = contracts.system_terms(sid)
        assert terms and all(f"-{sid}-" in d for d, _k, _f in terms)


def test_unknown_question_refused():
    assert contracts.answer("SYNCP000001", "What is the weather on the moon?")["answer"] == "not in the contracts"


def test_gen_out_read_only_source():
    m = json.loads((config.GEN_OUT / "manifest.json").read_text())
    assert m["synthetic"] is True and m["seed"] == 562
