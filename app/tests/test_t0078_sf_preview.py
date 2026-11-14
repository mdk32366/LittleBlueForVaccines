"""T-0078 'Preview Salesforce request' (D-0045 (Salesforce dry run), AS-0070): a pure function of (stored payload,
latest setup). One POST per tree in order Visit__c, Event, Task, to {instance}/services/data/v{api}/composite/tree/
{object}; the headers are exactly the placeholder Authorization and the JSON content type; each body is the stored
tree, so the stored payload's sha256 is reproduced from the preview bodies (also through a renaming setup); the curl
text carries the same body and the placeholder token; a 0.2 payload or a sha mismatch gets no preview.
Mutation: body_drift (the preview body is no longer the stored tree)."""
import copy
import json
import re

import pytest

from brief import payload as pl, sf_config as sc, sf_preview as sp, visits
from tests import visit_fixture as vf

RENAMED = dict(sc.DEFAULTS, instance_url="https://example-dev.my.salesforce.com", api_version="61.0",
               visit_object="LB_Visit__c", outcome_object="LB_Outcome__c", outcome_relationship="LB_Outcomes__r",
               account_relationship="LB_Account__r", account_external_id_field="LB_Ext_Id__c",
               record_type_id="012000000000000AAA")


@pytest.fixture
def saved(tmp_path):
    return visits.save_visit(db=tmp_path / "v.db", **vf.visit())


def _reassemble(payload, reqs, cfg):
    return dict(payload, trees={r["root"]: sp.stored_tree(r["body"], r["root"], cfg) for r in reqs})


def test_requests_method_url_headers(saved):
    reqs = sp.build_requests(saved["payload"], sc.DEFAULTS)
    assert [r["root"] for r in reqs] == ["Visit__c", "Event", "Task"]
    base = "https://example.my.salesforce.com/services/data/v62.0/composite/tree/"
    assert [(r["method"], r["url"]) for r in reqs] == [("POST", base + o) for o in ("Visit__c", "Event", "Task")]
    for r in reqs:
        assert r["headers"] == {"Authorization": "Bearer <NOT CONFIGURED>", "Content-Type": "application/json"}
    two = sp.build_requests(pl.build_payload(**vf.visit(outcomes=vf.outcomes(follow_up=""))), sc.DEFAULTS)
    assert [r["root"] for r in two] == ["Visit__c", "Event"]
    ren = sp.build_requests(saved["payload"], RENAMED)
    assert ren[0]["url"] == "https://example-dev.my.salesforce.com/services/data/v61.0/composite/tree/LB_Visit__c"
    v = ren[0]["body"]["records"][0]
    assert v["attributes"]["type"] == "LB_Visit__c" and v["RecordTypeId"] == "012000000000000AAA"
    assert v["LB_Account__r"] == {"attributes": {"type": "Account"}, "LB_Ext_Id__c": "SYNCP000025"}
    assert {k["attributes"]["type"] for k in v["LB_Outcomes__r"]["records"]} == {"LB_Outcome__c"}
    assert sp.BANNER == "DRY RUN. Nothing is sent. No credentials are stored."


def test_body_is_the_stored_payload(saved):
    p, sha = saved["payload"], saved["sha256"]
    reqs = sp.build_requests(p, sc.DEFAULTS)
    for r in reqs:  # default setup: each body is the stored tree exactly
        assert pl.canonical(r["body"]) == pl.canonical(p["trees"][r["root"]]), r["root"]
    assert pl.sha256(dict(p, trees={r["root"]: r["body"] for r in reqs})) == sha
    assert pl.sha256(_reassemble(p, sp.build_requests(p, RENAMED), RENAMED)) == sha
    rs = sp.request_set(p, sc.DEFAULTS, sha)
    assert rs["payload_sha256"] == sha and rs["dry_run"] is True and rs["banner"] == sp.BANNER
    assert [q["body"] for q in rs["requests"]] == [r["body"] for r in reqs]
    assert json.loads(sp.request_set_bytes(p, sc.DEFAULTS, sha)) == rs
    for r in reqs:  # the curl text carries the same body
        m = re.search(r"--data-binary '(.*)'$", r["curl"], re.S)
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
