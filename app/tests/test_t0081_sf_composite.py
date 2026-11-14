"""T-0081 one Composite request (D-0046 (one Composite request, allOrNone), AS-0072 (composite subrequest mapping),
closes F-0033): allOrNone is true; the Visit__c is the first subrequest (referenceId visit); every outcome's
master-detail field and every Event and Task WhatId is @{visit.id}; referenceIds are unique; 25 subrequests build and
26 or more are refused with a clear error; check_composite refuses each broken shape on its own.
Mutations: allornone_off (allOrNone false accepted), ref_break (an Event, Task or outcome no longer points at
@{visit.id}), over_25 (26 or more subrequests accepted), visit_not_first (Visit__c not the first subrequest)."""
import copy

import pytest

from brief import payload as pl, sf_config as sc, sf_preview as sp
from tests import visit_fixture as vf


def _outcomes(n: int, follow_ups: int) -> list:
    pts = [pl.TalkingPoint(f"R{i}", f"R{i} demo point {i}: system 1.0; state peers 1.0; national 1.0", "1.0", "1.0",
                           "1.0") for i in range(1, n + 1)]
    return [pl.Outcome(p, "Raised", "Neutral", 3, "", "Follow up" if i < follow_ups else "") for i, p in enumerate(pts)]


def _req(n=2, follow_ups=1, cfg=sc.DEFAULTS):
    return sp.build_requests(pl.build_payload(**vf.visit(outcomes=_outcomes(n, follow_ups))), cfg)[0]


def test_all_or_none_and_order():
    r = _req()
    body = r["body"]
    assert set(body) == {"allOrNone", "compositeRequest"} and body["allOrNone"] is True
    subs = body["compositeRequest"]
    assert subs[0]["referenceId"] == "visit" and subs[0]["url"].endswith("/sobjects/Visit__c")
    kinds = [s["url"].rsplit("/", 1)[1] for s in subs]
    assert kinds == ["Visit__c", "Talking_Point_Outcome__c", "Talking_Point_Outcome__c", "Event", "Task"]
    assert all(s["method"] == "POST" and s["url"].startswith("/services/data/v62.0/sobjects/") for s in subs)
    assert len({s["referenceId"] for s in subs}) == len(subs)


def test_every_reference_points_at_the_visit():
    subs = _req(n=3, follow_ups=3)["body"]["compositeRequest"]
    assert pl.VISIT_REF == "@{visit.id}" == "@{" + subs[0]["referenceId"] + ".id}"
    for s in subs[1:]:
        field = "Visit__c" if s["url"].endswith("/Talking_Point_Outcome__c") else "WhatId"
        assert s["body"][field] == "@{visit.id}", s["referenceId"]
    assert "WhatId" not in subs[0]["body"] and "Visit__c" not in subs[0]["body"]
    ren = _req(n=1, follow_ups=1, cfg=dict(sc.DEFAULTS, outcome_parent_field="LB_Visit_Ref__c"))
    assert ren["body"]["compositeRequest"][1]["body"]["LB_Visit_Ref__c"] == "@{visit.id}"


def test_at_most_25_subrequests():
    assert len(_req(n=12, follow_ups=11)["body"]["compositeRequest"]) == 25  # 1 + 12 + 1 + 11
    with pytest.raises(sp.TooManySubrequests, match="26 subrequests; one Composite request allows at most 25"):
        _req(n=12, follow_ups=12)  # 1 + 12 + 1 + 12 = 26
    with pytest.raises(sp.TooManySubrequests):
        _req(n=50, follow_ups=50)
    assert sp.COMPOSITE_MAX == 25


def test_check_composite_refuses_each_broken_shape():
    good = _req()["body"]
    sp.check_composite(good, sc.DEFAULTS)

    def broken(f):
        b = copy.deepcopy(good)
        f(b)
        return b
    cases = {
        "allOrNone": lambda b: b.update(allOrNone=False),
        "allOrNone missing": lambda b: b.pop("allOrNone"),
        "first": lambda b: b["compositeRequest"].reverse(),
        "event ref": lambda b: b["compositeRequest"][3]["body"].update(WhatId="@{event.id}"),
        "task ref": lambda b: b["compositeRequest"][4]["body"].update(WhatId="001000000000000AAA"),
        "outcome ref": lambda b: b["compositeRequest"][1]["body"].pop("Visit__c"),
        "dup ref": lambda b: b["compositeRequest"][2].update(referenceId="tp1"),
        "over 25": lambda b: b["compositeRequest"].extend(  # 26, unique referenceIds, every ref intact
            [dict(copy.deepcopy(b["compositeRequest"][4]), referenceId=f"extra{i}") for i in range(21)]),
    }
    for name, f in cases.items():
        with pytest.raises(sp.NotPreviewable):
            sp.check_composite(broken(f), sc.DEFAULTS)
            pytest.fail(f"not refused: {name}")
