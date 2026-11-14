"""T-0047 payload (AS-0070 (sf payload lb-sf-tree-0.3, Visit__c root); AS-0049 (sf payload field names) for 0.2): the
FAKE Salesforce sObject Tree bodies validate against the JSON Schema of their own version; the Visit__c tree carries the
Event fields, the Account external-id match and the rep, with the outcomes nested under Talking_Point_Outcomes__r; Event
and Task are their own trees with WhatId = the Visit__c reference; a bad payload fails in both versions; a stored 0.2
payload still validates and reads back; the FAKE-SYNTHETIC marker is on every record; the keyword hint is deterministic.
Mutations: pay_drop (Visit_Date__c removed), pay_nofake (marker dropped), schema_lax (validator accepts anything),
pay_none_str, hint, root_event (outcomes nested under Event again)."""
import copy
import json

import pytest

from brief import payload as pl
from tests import visit_fixture as vf

KID_FIELDS = {"attributes", "Talking_Point_Key__c", "Point_Text__c", "Metric_Value__c", "Benchmark_State__c",
              "Benchmark_National__c", "Addressed__c", "Customer_Response__c", "Quality_Score__c", "Evidence_Quote__c",
              "Follow_Up__c"}


def _p(**kw):
    v = vf.visit(**kw)
    return pl.build_payload(**v)


def _visit(p):
    return p["trees"][pl.ROOT_OBJECT]["records"][0]


def test_payload_validates_against_schema():
    p = _p()
    pl.validate(p)
    assert p["lb_schema_version"] == pl.SCHEMA_VERSION == "lb-sf-tree-0.3"
    assert list(p["trees"]) == ["Visit__c", "Event", "Task"] == list(pl.TREE_ORDER)
    v = _visit(p)
    assert v["attributes"] == {"type": "Visit__c", "referenceId": "visit"}
    assert v["Subject__c"] == "Vaccine rep visit – Sunrise Care Partners 025"
    assert v["Visit_Date__c"] == "2026-11-18" and v["Start_DateTime__c"] == "2026-11-18T09:00:00Z"
    assert v["Duration_Minutes__c"] == 30
    assert v["Account__r"] == {"attributes": {"type": "Account"}, "LB_System_Id__c": "SYNCP000025"}  # external id
    assert v["Rep_Name__c"] == "Demo Rep" and v["LB_Rep_Key__c"] == "demo rep"
    assert v["LB_Visit_Key__c"] == "demo rep|2026-11-18|SYNCP000025"
    kids = v[pl.CHILD_REL]["records"]  # master-detail children of the Visit__c
    assert [k["Talking_Point_Key__c"] for k in kids] == ["R1", "R3"]
    assert all(k["attributes"]["type"] == "Talking_Point_Outcome__c" for k in kids)
    assert set(kids[0]) == KID_FIELDS
    assert kids[0]["Metric_Value__c"] == "0.62" and kids[0]["Benchmark_National__c"] == "0.55"
    ev = p["trees"]["Event"]["records"]
    assert len(ev) == 1 and ev[0]["attributes"] == {"type": "Event", "referenceId": "event"}
    assert ev[0]["WhatId"] == pl.VISIT_REF == "@{visit.id}" and pl.CHILD_REL not in ev[0] and "What" not in ev[0]
    assert ev[0]["ActivityDate"] == "2026-11-18" and ev[0]["Subject"] == v["Subject__c"]
    tasks = p["trees"]["Task"]["records"]  # one Task per non-empty follow-up only
    assert len(tasks) == 1 and tasks[0]["Subject"] == "Follow-up: R1" and tasks[0]["WhatId"] == pl.VISIT_REF
    assert "Task" not in _p(outcomes=vf.outcomes(follow_up=""))["trees"]
    assert pl.CHILD_REL not in _visit(_p(outcomes=[]))
    assert _p() == _p() and pl.sha256(_p()) == pl.sha256(_p())  # pure and deterministic


def test_outcomes_only_under_visit():
    """root_event guard: no record outside the Visit__c tree carries outcome children."""
    p = _p()
    pl.validate(p)
    for root, tree in p["trees"].items():
        for r in tree["records"]:
            assert (pl.CHILD_REL in r) == (root == pl.ROOT_OBJECT), root
    ev = copy.deepcopy(p)
    ev["trees"]["Event"]["records"][0][pl.CHILD_REL] = _visit(p)[pl.CHILD_REL]
    with pytest.raises(pl.InvalidPayload):
        pl.validate(ev)


@pytest.mark.parametrize("breaker", ["drop_date", "extra_field", "bad_enum", "bad_score", "bad_system", "not_fake",
                                     "what_id", "no_visit", "bad_version"])
def test_bad_payload_rejected(breaker):
    p = copy.deepcopy(_p())
    v = _visit(p)
    kid = v[pl.CHILD_REL]["records"][0]
    if breaker == "drop_date":
        del v["Visit_Date__c"]
    elif breaker == "extra_field":
        v["Unlisted__c"] = "x"
    elif breaker == "bad_enum":
        kid["Addressed__c"] = "Maybe"
    elif breaker == "bad_score":
        kid["Quality_Score__c"] = 6
    elif breaker == "bad_system":
        v["Account__r"]["LB_System_Id__c"] = "ACME1"
    elif breaker == "not_fake":
        p["lb_marker"] = "REAL"
    elif breaker == "what_id":
        p["trees"]["Event"]["records"][0]["WhatId"] = "001000000000000AAA"
    elif breaker == "no_visit":
        del p["trees"]["Visit__c"]
    elif breaker == "bad_version":
        p["lb_schema_version"] = "lb-sf-tree-9.9"
    with pytest.raises(pl.InvalidPayload):
        pl.validate(p)


@pytest.mark.parametrize("breaker", ["drop_date", "bad_enum", "not_fake", "visit_root_in_02"])
def test_legacy_02_payload_still_validates(breaker):
    """Rows saved before v0.2-f keep lb-sf-tree-0.2 (Event root): the 0.2 schema still accepts them and still refuses
    a bad one, and a 0.2 body is not accepted as 0.3 (or the other way round)."""
    old = pl.build_payload_v02(**vf.visit())
    assert old["lb_schema_version"] == pl.LEGACY_VERSION == "lb-sf-tree-0.2" and list(old["trees"]) == ["Event", "Task"]
    pl.validate(old)
    assert old["trees"]["Event"]["records"][0][pl.CHILD_REL]["records"][0]["Talking_Point_Key__c"] == "R1"
    with pytest.raises(pl.InvalidPayload):
        pl.validate(dict(old, lb_schema_version=pl.SCHEMA_VERSION))
    with pytest.raises(pl.InvalidPayload):
        pl.validate(dict(_p(), lb_schema_version=pl.LEGACY_VERSION))
    bad = copy.deepcopy(old)
    ev = bad["trees"]["Event"]["records"][0]
    if breaker == "drop_date":
        del ev["ActivityDate"]
    elif breaker == "bad_enum":
        ev[pl.CHILD_REL]["records"][0]["Addressed__c"] = "Maybe"
    elif breaker == "not_fake":
        bad["lb_marker"] = "REAL"
    elif breaker == "visit_root_in_02":
        bad["trees"]["Visit__c"] = _p()["trees"]["Visit__c"]
    with pytest.raises(pl.InvalidPayload):
        pl.validate(bad)


def test_payload_carries_fake_marker():
    for p in (_p(), pl.build_payload_v02(**vf.visit())):
        assert p["lb_marker"] == pl.FAKE_MARKER == "FAKE-SYNTHETIC"
        roots = [r for tree in p["trees"].values() for r in tree["records"]]
        desc = [r.get("Description", r.get("Description__c")) for r in roots]
        assert roots and all(d.startswith(pl.FAKE_MARKER + " ") for d in desc)
        assert all(r["LB_Synthetic__c"] is True for r in roots)
        assert json.loads(pl.canonical(p))["lb_marker"] == "FAKE-SYNTHETIC"


def test_visit_key_rules():
    assert pl.visit_key("  Demo   REP ", "2026-11-18", "syncp000025") == "demo rep|2026-11-18|SYNCP000025"
    for bad in (("", "2026-11-18", "SYNCP000025"), ("x", "11/18/2026", "SYNCP000025"), ("x", "2026-11-18", "ACME")):
        with pytest.raises(ValueError):
            pl.visit_key(*bad)


def test_mentioned_hint():
    p = vf.POINTS[0]
    assert pl.mentioned_hint(p, "We discussed menb uptake today.")
    assert pl.mentioned_hint(p, "MenACWY came up")
    assert not pl.mentioned_hint(p, "Only scheduling and parking.")
    assert not pl.mentioned_hint(p, "the system and state peers, national 0.62")  # stop words and digits never count
    assert not pl.mentioned_hint(p, "")


def test_points_from_client_rows(real_client):
    from brief import client_metrics as cm
    pts = pl.points_from_client_rows(cm.table_rows(real_client["SYNCP000025"]))
    assert [p.key for p in pts][:2] == ["R1", "R2"] and pts[0].metric_value == "0.62" and pts[0].bench_national == "0.55"
    assert all(not p.metric_value.startswith("not available") for p in pts)


def test_duck_typed_points_accepted():
    from dataclasses import dataclass, fields

    @dataclass(frozen=True)
    class ProviderPoint:  # stands in for the PR 6 provider's own frozen dataclass
        key: str
        text: str
        metric_value: str | None
        bench_state: str | None
        bench_national: str | None
    assert [f.name for f in fields(ProviderPoint)] == [f.name for f in fields(pl.TalkingPoint)]
    pp = ProviderPoint(*[getattr(vf.POINTS[0], f.name) for f in fields(pl.TalkingPoint)])
    assert pl.mentioned_hint(pp, "menb came up")
    p = pl.build_payload(**vf.visit(outcomes=[pl.Outcome(pp, "Raised", "Positive", 5, "", "")]))
    pl.validate(p)
    assert p == pl.build_payload(**vf.visit(outcomes=[pl.Outcome(vf.POINTS[0], "Raised", "Positive", 5, "", "")]))


def test_provider_values_numbers_and_null():
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class PayloadPoint:  # the v0.2-b provider shape: floats or None
        key: str
        text: str
        metric_value: float | None
        bench_state: float | None
        bench_national: float | None
    pts = [PayloadPoint("must.R2", "Must cover: HPV to MenACWY + MenABCWY doses", 0.2083, 0.7885, 1.2570),
           PayloadPoint("question.F2", "Question to ask: what is driving purchasing", None, None, None),
           PayloadPoint("must.none", "No ratio differs", float("nan"), float("inf"), None)]
    p = pl.build_payload(**vf.visit(outcomes=[pl.Outcome(x) for x in pts]))
    pl.validate(p)
    kids = _visit(p)[pl.CHILD_REL]["records"]
    assert (kids[0]["Metric_Value__c"], kids[0]["Benchmark_State__c"], kids[0]["Benchmark_National__c"]) == (0.2083, 0.7885, 1.257)
    for k in kids[1:]:
        assert (k["Metric_Value__c"], k["Benchmark_State__c"], k["Benchmark_National__c"]) == (None, None, None)
    text = pl.canonical(p)
    assert '"Metric_Value__c":null' in text and "NaN" not in text and "Infinity" not in text and '"None"' not in text
    assert not pl.mentioned_hint(pts[1], "What should we cover next? Which question to ask?")  # template words only
