"""T-0078 'Preview Salesforce request' (D-0045 (Salesforce dry run), D-0046 (one Composite request, allOrNone), AS-0070,
AS-0072 (composite subrequest mapping)): a pure function of (stored payload, latest setup). ONE POST to
{instance}/services/data/v{api}/composite; the headers are exactly the placeholder Authorization and the JSON content
type; the body's subrequests are the stored records (attributes moved to the subrequest URL and referenceId, the
outcome's master-detail field added), so the stored payload's sha256 is rebuilt from the request body (also through a
renaming setup); the curl text carries the same body and the placeholder token; a 0.2 payload or a sha mismatch gets no
preview.
Shape change in 6c (the body_drift guarantee, restated): 0.1 had one body per tree, equal to the stored tree; now the
one body's compositeRequest holds every stored record in order, and `stored_trees` rebuilds the stored trees from it.
Mutation: body_drift (a subrequest body gains a field)."""
import copy
import json
import re

import pytest

from brief import payload as pl, sf_config as sc, sf_preview as sp, visits
from tests import visit_fixture as vf

RENAMED = dict(sc.DEFAULTS, instance_url="https://example-dev.my.salesforce.com", api_version="61.0",
               visit_object="LB_Visit__c", outcome_object="LB_Outcome__c", outcome_relationship="LB_Outcomes__r",
               outcome_parent_field="LB_Visit_Ref__c", account_relationship="LB_Account__r",
               account_external_id_field="LB_Ext_Id__c", record_type_id="012000000000000AAA")


@pytest.fixture
def saved(tmp_path):
    return visits.save_visit(db=tmp_path / "v.db", **vf.visit())


def _rebuilt(payload, req, cfg):
    return dict(payload, trees=sp.stored_trees(req["body"], cfg))


def test_one_request_method_url_headers(saved):
    reqs = sp.build_requests(saved["payload"], sc.DEFAULTS)
    assert len(reqs) == 1
    r = reqs[0]
    assert (r["method"], r["url"]) == ("POST", "https://example.my.salesforce.com/services/data/v62.0/composite")
    assert r["headers"] == {"Authorization": "Bearer <NOT CONFIGURED>", "Content-Type": "application/json"}
    subs = r["body"]["compositeRequest"]
    base = "/services/data/v62.0/sobjects/"
    assert [(s["method"], s["url"], s["referenceId"]) for s in subs] == [
        ("POST", base + "Visit__c", "visit"), ("POST", base + "Talking_Point_Outcome__c", "tp1"),
        ("POST", base + "Talking_Point_Outcome__c", "tp2"), ("POST", base + "Event", "event"),
        ("POST", base + "Task", "followup1")]
    ren = sp.build_requests(saved["payload"], RENAMED)[0]
    assert ren["url"] == "https://example-dev.my.salesforce.com/services/data/v61.0/composite"
    rs = ren["body"]["compositeRequest"]
    v = rs[0]["body"]
    assert rs[0]["url"] == "/services/data/v61.0/sobjects/LB_Visit__c" and v["RecordTypeId"] == "012000000000000AAA"
    assert v["LB_Account__r"] == {"attributes": {"type": "Account"}, "LB_Ext_Id__c": "SYNCP000025"}
    assert "LB_Outcomes__r" not in v and "attributes" not in v
    assert {s["url"] for s in rs[1:3]} == {"/services/data/v61.0/sobjects/LB_Outcome__c"}
    assert all(s["body"]["LB_Visit_Ref__c"] == "@{visit.id}" for s in rs[1:3])
    assert sp.BANNER == "DRY RUN. Nothing is sent. No credentials are stored."


def test_body_is_the_stored_payload(saved):
    p, sha = saved["payload"], saved["sha256"]
    r = sp.build_requests(p, sc.DEFAULTS)[0]
    subs = r["body"]["compositeRequest"]
    stored_visit = p["trees"]["Visit__c"]["records"][0]
    kids = stored_visit["Talking_Point_Outcomes__r"]["records"]
    # default setup: each subrequest body is its stored record, without attributes (and the visit without children)
    assert subs[0]["body"] == {k: v for k, v in stored_visit.items() if k not in ("attributes", pl.CHILD_REL)}
    for s, k in zip(subs[1:3], kids):
        assert s["body"] == dict({x: y for x, y in k.items() if x != "attributes"}, Visit__c="@{visit.id}")
    rest = p["trees"]["Event"]["records"] + p["trees"]["Task"]["records"]
    assert [s["body"] for s in subs[3:]] == [{x: y for x, y in k.items() if x != "attributes"} for k in rest]
    assert pl.sha256(_rebuilt(p, r, sc.DEFAULTS)) == sha
    assert pl.sha256(_rebuilt(p, sp.build_requests(p, RENAMED)[0], RENAMED)) == sha
    rs = sp.request_set(p, sc.DEFAULTS, sha)
    assert rs["payload_sha256"] == sha and rs["dry_run"] is True and rs["banner"] == sp.BANNER
    assert rs["lb_request_set"] == "lb-sf-dryrun-requests-0.2" and [q["body"] for q in rs["requests"]] == [r["body"]]
    assert json.loads(sp.request_set_bytes(p, sc.DEFAULTS, sha)) == rs
    m = re.search(r"--data-binary '(.*)'$", r["curl"], re.S)  # the curl text carries the same body
    assert m and json.loads(m.group(1).replace("'\\''", "'")) == r["body"]


def test_pure_and_curl_placeholder(saved):
    p = copy.deepcopy(saved["payload"])
    a, b = sp.build_requests(p, RENAMED), sp.build_requests(p, RENAMED)
    assert a == b and p == saved["payload"]  # same output, input untouched
    for r in a:
        assert r["curl"].startswith(f"curl -X POST '{r['url']}'")
        assert "-H 'Authorization: Bearer <NOT CONFIGURED>'" in r["curl"]
        assert "-H 'Content-Type: application/json'" in r["curl"]
    q = pl.build_payload(**vf.visit(notes="it's the rep's note"))  # a quote in the body stays shell-safe
    c = sp.build_requests(q, sc.DEFAULTS)[0]["curl"]
    assert "it'\\''s the rep'\\''s note" in c


def test_no_preview_for_legacy_or_mismatch(saved):
    old = pl.build_payload_v02(**vf.visit())
    with pytest.raises(sp.NotPreviewable, match="lb-sf-tree-0.2"):
        sp.build_requests(old, sc.DEFAULTS)
    with pytest.raises(sp.NotPreviewable, match="sha256"):
        sp.request_set(saved["payload"], sc.DEFAULTS, "0" * 64)
    with pytest.raises(sc.InvalidConfig):
        sp.build_requests(saved["payload"], dict(sc.DEFAULTS, instance_url="https://example.test"))
    with pytest.raises(sc.InvalidConfig):  # a setup name that would collide with a payload field
        sp.build_requests(saved["payload"], dict(sc.DEFAULTS, account_external_id_field="LB_Visit_Key__c"))
    with pytest.raises(sc.InvalidConfig):  # the master-detail field may not overwrite an outcome field
        sp.build_requests(saved["payload"], dict(sc.DEFAULTS, outcome_parent_field="Follow_Up__c"))
