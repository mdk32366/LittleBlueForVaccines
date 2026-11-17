"""T-0097 Bluebird Contract Q&A client (D-0050, AS-0084, AS-0085), against the loopback stub sidecar:
- routing and clause choice: one system only, inside the prompt budget, the training document sets, and the gold
  clause in the prompt for (nearly) every committed test question;
- the prompt is the training prompt (system text, user turn, Qwen2.5 template), sent with the bench's greedy settings
  and JSON-slot grammar;
- nothing unchecked is shown: exact schema, slots match spans, no stray number, no commercial advice, and every quoted
  span word for word in a clause of THIS system that was in the prompt; the citation anchor is where it was found;
- pricing-advice questions are refused without asking the model;
- every failure is a status ("down" / "rejected"), never an exception or a made-up answer; flag off -> no provider.
Mutations: qa_span_unchecked, qa_digits_lax, qa_other_system, qa_advice_sent."""
import hashlib
import json

import pytest

from brief import bluebird_qa as bq, config
from tests.bluebird_stub import Stub, free_port_url

SID = "SYNCP000002"
Q = "Starting when is the master arrangement binding?"
GOOD = {"answer": "Commencement: {S1}.", "spans": {"S1": {"anchor": "SYN-SYNCP000002-MSA1#2", "text": "1 June 2024"}}}


def qa_rows(split="test"):
    return [json.loads(line) for line in (config.GEN_OUT / split / "qa.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def stub():
    s = Stub(answer=lambda body: json.dumps(GOOD))
    yield s
    s.close()


@pytest.mark.parametrize("q,r", [
    (Q, "contract"),
    ("Service charge rate, please?", "contract"),
    ("Where did the 2026 pitch land?", "proposal"),
    ("Which return item was sought in 2025?", "proposal"),
    ("Post-update minimum portion, please?", "amendment"),
    ("Account figure for total dollars (A1), please?", "exhibit"),
    ("Nationwide relative standing on R5 (Shingles to adult-labelled Influenza)?", "exhibit"),
    ("Has the account cleared its Influenza minimum take over the latest year?", "cross"),
])
def test_route(q, r):
    assert bq.route(q) == r


def test_units_one_system_and_budget():
    for sid, q in [(SID, Q), ("SYNCP000045", "Account figure for total dollars (A1), please?"),
                   ("SYNCP000077", "Which product led Influenza drift across windows?"),
                   ("SYNCP000003", "Where did the 2026 pitch land?")]:
        us = bq.units(sid, q)
        assert us, (sid, q)
        assert all(u["doc_id"].startswith(f"SYN-{sid}-") and u["id"].startswith(u["doc_id"] + "#") for u in us)
        assert sum(len(u["text"]) for u in us) <= bq.UNIT_CHARS


def test_units_follow_training_document_sets():
    def kinds(q, sid="SYNCP000003"):
        return sorted({u["doc_id"].rsplit("-", 1)[1].rstrip("0123456789") for u in bq.units(sid, q)})
    assert kinds(Q) == ["MSA"]
    assert kinds("Where did the 2026 pitch land?") == ["MSA", "P"]
    assert kinds("Post-update minimum portion, please?") == ["AMD"]
    assert kinds("Account figure for total dollars (A1), please?") == ["EXH"]
    assert kinds("Has the account cleared its Influenza minimum take over the latest year?") == ["AMD", "EXH", "MSA"]


def test_gold_clause_is_in_the_prompt_for_nearly_every_test_question():
    rows = [r for r in qa_rows() if r.get("spans")]
    rows = sorted(rows, key=lambda r: hashlib.sha256(r["qa_id"].encode()).hexdigest())[:400]
    hit = 0
    for r in rows:
        ids = {u["id"] for u in bq.units(r["system_id"], r["question"])}
        hit += all(s["anchor"] in ids or s["anchor"].split("#")[0] + "#*" in ids for s in r["spans"].values())
    assert hit / len(rows) >= 0.97, f"{hit}/{len(rows)}"  # measured 2,071/2,090 on the full test split


def test_prompt_is_the_training_prompt():
    us = bq.units(SID, Q)
    p = bq.render_prompt(Q, us)
    assert p.startswith("<|im_start|>system\nAnswer from the contract text only. Return JSON {answer, spans}; "
                        "no raw digits in answer.<|im_end|>\n<|im_start|>user\nQuestion: " + Q + "\n\nContract text:\n")
    assert p.endswith("<|im_end|>\n<|im_start|>assistant\n")
    assert "\n\n".join(u["text"] for u in us) in p


def test_verify_ok_cites_where_the_span_is():
    us = bq.units(SID, Q)
    wrong_anchor = {"answer": "Commencement: {S1}.",
                    "spans": {"S1": {"anchor": "SYN-SYNCP000002-MSA1#7", "text": "1 June 2024"}}}
    res = bq.verify(wrong_anchor, us, Q)
    assert res["status"] == "ok" and res["answer"] == "Commencement: 1 June 2024."
    assert res["citations"][0]["anchor"] == "SYN-SYNCP000002-MSA1#2"
    assert "1 June 2024" in res["citations"][0]["clause_text"]


def test_span_not_in_contract_rejected():
    us = bq.units(SID, Q)
    other_system = "May 1, 2025"  # SYNCP000003's start date: real contract text, but not this system's
    for text in ("1 January 2099", other_system):
        o = {"answer": "Commencement: {S1}.", "spans": {"S1": {"anchor": "SYN-SYNCP000002-MSA1#2", "text": text}}}
        with pytest.raises(bq.Rejected, match="not in this system"):
            bq.verify(o, us, Q)


def test_numbers_outside_slots_rejected_d0023():
    q = "How many yearly doses unlock Band 2?"
    us = bq.units(SID, q)
    span = next(u for u in us if u["anchor"] == "4.2")["text"].split(" doses")[0].split()[-1]
    o = {"answer": "Threshold: {S1} doses.", "spans": {"S1": {"anchor": "SYN-SYNCP000002-MSA1#4.2", "text": span}}}
    assert bq.verify(o, us, q)["status"] == "ok"
    for prose in ("Band 2 is reached after {S1} doses per year.", "Threshold: {S1} doses, about 300 a year."):
        with pytest.raises(bq.Rejected, match="number"):  # D-0023: even a number the question used
            bq.verify({**o, "answer": prose}, us, q)
    assert bq.stray_numbers("Threshold: {S1} and {S12}.") == []


@pytest.mark.parametrize("raw,why", [
    ("not json", "expected form"),
    (json.dumps({"answer": "x"}), "expected form"),
    (json.dumps({**GOOD, "extra": 1}), "expected form"),
    (json.dumps({"answer": "Commencement: {S1} and {S2}.", "spans": GOOD["spans"]}), "slots"),
    (json.dumps({"answer": "not in the contracts", "spans": GOOD["spans"]}), "also quoted spans"),
    (json.dumps({"answer": "We should push the rebate to {S1}.", "spans": GOOD["spans"]}), "commercial advice"),
])
def test_bad_replies_rejected(raw, why):
    with pytest.raises(bq.Rejected, match=why):
        bq.verify(bq.parse(raw), bq.units(SID, Q), Q)


def test_refusal_is_a_result():
    res = bq.verify({"answer": "not in the contracts", "spans": {}}, bq.units(SID, Q), Q)
    assert res == {"status": "refusal", "answer": bq.REFUSAL, "template": "not in the contracts", "citations": []}


def test_ask_via_stub_sends_the_training_request(stub):
    res = bq.ask(stub.url, SID, Q)
    assert res["status"] == "ok" and res["answer"] == "Commencement: 1 June 2024."
    assert res["route"] == "contract" and res["units"] and all(SID in u for u in res["units"])
    (req,) = stub.requests
    assert req["path"] == "/completion"
    body = req["body"]
    assert body["grammar"] == bq.GRAMMAR and body["n_predict"] == bq.N_PREDICT and body["temperature"] == 0.0
    assert body["prompt"] == bq.render_prompt(Q, bq.units(SID, Q))


@pytest.mark.parametrize("q", ["What price should we offer PFIZER for Pneumococcal?",
                               "Best discount level to request from SANOFI?",
                               "Rebate figure to aim for in talks with GSK PHARM?"])
def test_advice_question_never_sent(stub, q):
    res = bq.ask(stub.url, SID, q)
    assert res["status"] == "refusal" and res["reason"] == bq.ADVICE_REASON
    assert stub.requests == []


def test_advice_guard_keeps_contract_questions():
    assert not bq.asks_for_advice("What rebate does tier 2 offer?")
    assert not bq.asks_for_advice("Does the rebate increase at band 2?")
    rows = qa_rows()
    assert not [r["question"] for r in rows if r["question_type"] != "refuse.pricing" and bq.asks_for_advice(r["question"])]
    assert all(bq.asks_for_advice(r["question"]) for r in rows if r["question_type"] == "refuse.pricing")


def test_failures_are_statuses_never_exceptions():
    assert bq.ask(free_port_url(), SID, Q)["status"] == "down"
    assert bq.ask("http://user:pw@127.0.0.1:1", SID, Q)["status"] == "down"
    assert bq.ask("", SID, Q)["status"] == "down"
    s = Stub(answer=lambda body: json.dumps(GOOD), status=500)
    try:
        assert bq.ask(s.url, SID, Q)["status"] == "down"
    finally:
        s.close()
    s = Stub(answer=lambda body: "Sure! The start date is 1 June 2024.")
    try:
        res = bq.ask(s.url, SID, Q)
        assert res["status"] == "rejected" and res["citations"] == []
    finally:
        s.close()


def test_provider_only_with_the_flag(stub):
    assert bq.provider({}) is None and bq.provider({"LB_BLUEBIRD": "off", "LB_BLUEBIRD_URL": stub.url}) is None
    ask = bq.provider({"LB_BLUEBIRD": "on", "LB_BLUEBIRD_URL": stub.url})
    assert ask(SID, Q)["status"] == "ok"
