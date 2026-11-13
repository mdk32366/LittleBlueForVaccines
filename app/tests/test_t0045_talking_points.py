"""T-0045 talking points (AS-0045 (must-cover selection)): every point passes the validator; numbers come only from
computed facts; selection is deterministic; tokens resolve only to status-ok, available facts; no clinical or advice
language across all 180 systems. Mutations: tp_digit (a literal number in a template), tp_inject (a rendered point
gains a number no fact produced), tp_select (threshold 25 -> 0), tp_na (status / NOT AVAILABLE tokens let through)."""
import re

import pytest

from brief import talking, validator
from brief.narrative import fmt_fact

DIGIT = re.compile(r"\d")


@pytest.fixture(scope="module")
def built(real_client):
    return {sid: talking.build(fs) for sid, fs in real_client.items()}


def test_every_point_passes_guardrails(real_client):
    assert len(real_client) == 180
    for sid, fs in real_client.items():
        pts = talking.build(fs)  # built here, not in a fixture: a guardrail failure must be a test failure
        assert [p.slot for p in pts[:3]] == ["fixed"] * 3 and pts[-1].slot == "question"
        assert 1 <= sum(p.slot == "must" for p in pts) <= talking.MUST_COVER_TOP
        for p in pts:
            assert talking.check(p.text, fs).ok, (sid, p.text)
            assert not validator.CLINICAL.search(p.rendered), (sid, p.rendered)
            assert not re.search(r"should\s+charge", p.rendered, re.I)
            for s in re.split(r"(?<=[.!?])\s+", p.rendered):
                assert not (validator.ADVISORY.search(s) and validator.COMMERCIAL.search(s)), (sid, s)


def test_numbers_trace_to_facts(real_client, built):
    """Strip every rendered fact value from the rendered text: no digit may remain."""
    for sid, pts in built.items():
        fs = real_client[sid]
        for p in pts:
            rest = p.rendered
            for fid in sorted({m.group(1) for m in validator.TOKEN.finditer(p.text)},
                              key=lambda f: -len(fmt_fact(fs.facts[f]))):
                rest = rest.replace(fmt_fact(fs.facts[fid]), "")
            assert not DIGIT.search(rest), (sid, p.rendered, rest)


def test_deterministic(real_client, built):
    for sid in ("SYNCP000001", "SYNCP000025", "SYNCP000180"):
        assert [p.rendered for p in talking.build(real_client[sid])] == [p.rendered for p in built[sid]]


def test_select_rule_unit_cases():
    assert talking.select([("R3", "state", 80.0), ("R6", "national", 100.0), ("R5", "state", 124.9)]) == []
    cands = [("R1", "state", 133.0), ("R1", "national", 160.0), ("R2", "state", 50.0), ("A2.1", "national", 126.0),
             ("R5", "state", 76.0), ("R6", "state", 0.0)]
    assert talking.select(cands) == [("R2", "state", 50.0), ("R1", "national", 160.0), ("A2.1", "national", 126.0)]
    assert talking.select([("R5", "state", 200.0), ("R1", "national", 50.0)]) == [("R1", "national", 50.0),
                                                                                 ("R5", "state", 200.0)]


def test_none_qualify_message(real_client, monkeypatch):
    monkeypatch.setattr(talking, "candidates", lambda fs: [("R3", "state", 90.0)])
    must = [p for p in talking.build(real_client["SYNCP000025"]) if p.slot == "must"]
    assert [p.rendered for p in must] == [talking.NONE_QUALIFY]


def test_status_and_not_available_tokens_rejected(real_client):
    fs = real_client["SYNCP000025"]
    assert not talking.check("National outlets: {F10.n_ddd_nat_st}.", fs).ok          # a status label
    assert not talking.check("Peer median: {F9.peer_median_dollars_nat_st}.", fs).ok  # NOT AVAILABLE item (A1M)
    assert not talking.check("OBGYN: {F13.r7_flu_tdap_st}.", fs).ok                    # status undefined
    assert talking.check("Size: {F1.dollars}.", fs).ok


def test_payload_fields(real_client):
    """The payload seam: field names and order are pinned (the visit-record payload maps them 1:1)."""
    from dataclasses import fields
    items = talking.payload_points("SYNCP000025", real_client)
    names = ("key", "text", "metric_value", "bench_state", "bench_national")
    assert tuple(f.name for f in fields(type(items[0]))) == names == talking.PAYLOAD_FIELDS
    assert [i.text for i in items] == [p.rendered for p in talking.build(real_client["SYNCP000025"])]
    a1 = items[0]
    assert a1.key == "fixed.A1" and a1.metric_value == real_client["SYNCP000025"].v("F1.dollars")
    assert 0 < a1.bench_state <= 1 and items[-1].key == "question.F2" and items[-1].metric_value is None
    for i in items:
        for v in (i.metric_value, i.bench_state, i.bench_national):
            assert v is None or isinstance(v, float)
