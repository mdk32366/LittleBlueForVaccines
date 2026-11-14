"""T-0047 payload (AS-0049 (sf payload field names)): the FAKE Salesforce sObject Tree body validates against the JSON
Schema; a bad payload fails; the FAKE-SYNTHETIC marker is on every record; the keyword hint is deterministic.
Mutations: pay_drop (ActivityDate removed), pay_nofake (marker dropped), schema_lax (validator accepts anything), hint."""
import copy
import json

import pytest

from brief import payload as pl
from tests import visit_fixture as vf


def _p(**kw):
    v = vf.visit(**kw)
    return pl.build_payload(**v)


def test_payload_validates_against_schema():
    p = _p()
    pl.validate(p)
    ev = p["trees"]["Event"]["records"][0]
    assert ev["attributes"] == {"type": "Event", "referenceId": "visit"}
    assert ev["Subject"] == "Vaccine rep visit – Sunrise Care Partners 025"
    assert ev["ActivityDate"] == "2026-11-18" and ev["StartDateTime"] == "2026-11-18T09:00:00Z"
    assert ev["DurationInMinutes"] == 30 and ev["What"]["LB_System_Id__c"] == "SYNCP000025"
    assert ev["LB_Rep_Key__c"] == "demo rep" and ev["LB_Visit_Key__c"] == "demo rep|2026-11-18|SYNCP000025"
    kids = ev[pl.CHILD_REL]["records"]
    assert [k["Talking_Point_Key__c"] for k in kids] == ["R1", "R3"]
    assert set(kids[0]) == {"attributes", "Talking_Point_Key__c", "Point_Text__c", "Metric_Value__c",
                            "Benchmark_State__c", "Benchmark_National__c", "Addressed__c", "Customer_Response__c",
                            "Quality_Score__c", "Evidence_Quote__c", "Follow_Up__c"}
    assert kids[0]["Metric_Value__c"] == "0.62" and kids[0]["Benchmark_National__c"] == "0.55"
    tasks = p["trees"]["Task"]["records"]  # one Task per non-empty follow-up only
    assert len(tasks) == 1 and tasks[0]["Subject"] == "Follow-up: R1"
    assert "Task" not in _p(outcomes=vf.outcomes(follow_up=""))["trees"]
    assert _p() == _p() and pl.sha256(_p()) == pl.sha256(_p())  # pure and deterministic


@pytest.mark.parametrize("breaker", ["drop_date", "extra_field", "bad_enum", "bad_score", "bad_system", "not_fake"])
def test_bad_payload_rejected(breaker):
    p = copy.deepcopy(_p())
    ev = p["trees"]["Event"]["records"][0]
    kid = ev[pl.CHILD_REL]["records"][0]
    if breaker == "drop_date":
        del ev["ActivityDate"]
    elif breaker == "extra_field":
        ev["Unlisted__c"] = "x"
    elif breaker == "bad_enum":
        kid["Addressed__c"] = "Maybe"
    elif breaker == "bad_score":
        kid["Quality_Score__c"] = 6
    elif breaker == "bad_system":
        ev["What"]["LB_System_Id__c"] = "ACME1"
    elif breaker == "not_fake":
        p["lb_marker"] = "REAL"
    with pytest.raises(pl.InvalidPayload):
        pl.validate(p)


def test_payload_carries_fake_marker():
    p = _p()
    assert p["lb_marker"] == pl.FAKE_MARKER == "FAKE-SYNTHETIC"
    roots = [r for tree in p["trees"].values() for r in tree["records"]]
    assert roots and all(r["Description"].startswith(pl.FAKE_MARKER + " ") for r in roots)
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
    kids = p["trees"]["Event"]["records"][0][pl.CHILD_REL]["records"]
    assert (kids[0]["Metric_Value__c"], kids[0]["Benchmark_State__c"], kids[0]["Benchmark_National__c"]) == (0.2083, 0.7885, 1.257)
    for k in kids[1:]:
        assert (k["Metric_Value__c"], k["Benchmark_State__c"], k["Benchmark_National__c"]) == (None, None, None)
    text = pl.canonical(p)
    assert '"Metric_Value__c":null' in text and "NaN" not in text and "Infinity" not in text and '"None"' not in text
    assert not pl.mentioned_hint(pts[1], "What should we cover next? Which question to ask?")  # template words only
