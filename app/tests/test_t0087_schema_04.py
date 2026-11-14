"""T-0087 lb-sf-tree-0.4 and the frozen 0.3 (AS-0074): the 0.4 schema accepts the valid reason shapes and rejects each
invalid one (no reason on a point that is not Raised, a reason on a Raised point, OTHER without text, 281 characters,
an unknown code, no Addendum__c). The 0.3 schema file's bytes and the 0.3 builder's output are pinned (sha256 at main
0f8471d), a 0.3 payload still validates and previews, and stored 0.2 and 0.3 rows are never rewritten. The 0.4 preview
carries the reason fields in the outcome subrequests with the same subrequest count, passes check_composite, and the
25 guard is unchanged. Visit files of version 0.2 and 0.3 load, and an old store row reads back with the defaults.
Mutations: schema_03_mutated (0.3 builder emits Addendum__c / one byte of the 0.3 schema changed), reason_optional."""
import copy
import hashlib
import json
import sqlite3

import pytest

from brief import payload as pl, sf_config as sc, sf_preview as sp, visits
from tests import visit_fixture as vf

V03_SCHEMA_SHA = "be91c1a87ba6e8ba3e1618c89049fba74b8bd6676516e994a60e18ca977ae88e"  # schemas/visit_payload.schema.json
V03_FIXTURE_SHA = "3bf44409b75fdcc43bf1b33058ae5f2fef2cf244e121ef0a101819b44cc69d3f"  # build_payload(**vf.visit()) at 0f8471d
NEW = ("Not_Addressed_Reason__c", "Not_Addressed_Reason_Text__c", "Addendum__c")


def _kids(p):
    return p["trees"][pl.ROOT_OBJECT]["records"][0][pl.CHILD_REL]["records"]


def test_schema_04_accepts_valid():
    p = pl.build_payload(**vf.visit())
    pl.validate(p)
    assert p["lb_schema_version"] == "lb-sf-tree-0.4"
    assert [(k["Addressed__c"], k["Not_Addressed_Reason__c"], k["Addendum__c"]) for k in _kids(p)] == [
        ("Raised", None, False), ("Not raised", "OUT_OF_TIME", False)]
    for code, text, addressed in (("OTHER", "Closed early", "Not raised"), ("NOT_RELEVANT", None, "Partially"),
                                  ("COVERED_PREVIOUSLY", "x" * 280, "Not raised"), ("CONTACT_DECLINED", "", "Partially")):
        q = copy.deepcopy(p)
        _kids(q)[1].update(Addressed__c=addressed, Not_Addressed_Reason__c=code, Not_Addressed_Reason_Text__c=text,
                           Addendum__c=True)
        pl.validate(q)


@pytest.mark.parametrize("breaker", ["missing_reason", "reason_on_raised", "other_no_text", "text_281",
                                     "unknown_code", "no_addendum"])
def test_schema_04_rejects(breaker):
    p = copy.deepcopy(pl.build_payload(**vf.visit()))
    raised, nr = _kids(p)
    if breaker == "missing_reason":
        nr["Not_Addressed_Reason__c"] = None
    elif breaker == "reason_on_raised":
        raised["Not_Addressed_Reason__c"] = "OUT_OF_TIME"
    elif breaker == "other_no_text":
        nr.update(Not_Addressed_Reason__c="OTHER", Not_Addressed_Reason_Text__c="   ")
    elif breaker == "text_281":
        nr["Not_Addressed_Reason_Text__c"] = "x" * 281
    elif breaker == "unknown_code":
        nr["Not_Addressed_Reason__c"] = "BUSY"
    elif breaker == "no_addendum":
        del nr["Addendum__c"]
    with pytest.raises(pl.InvalidPayload):
        pl.validate(p)


def test_v03_schema_bytes_pinned():
    assert hashlib.sha256(pl.SCHEMA_PATHS[pl.V03_VERSION].read_bytes()).hexdigest() == V03_SCHEMA_SHA
    assert pl.SCHEMA_PATHS[pl.V03_VERSION].name == "visit_payload.schema.json"
    assert pl.SCHEMA_PATHS[pl.SCHEMA_VERSION].name == "visit_payload-0.4.schema.json"


def test_v03_builder_frozen():
    old = pl.BUILDERS[pl.V03_VERSION](**vf.visit())
    assert old["lb_schema_version"] == "lb-sf-tree-0.3" and pl.sha256(old) == V03_FIXTURE_SHA
    assert not [f for k in _kids(old) for f in NEW if f in k]
    pl.validate(old)
    with pytest.raises(pl.InvalidPayload):  # a 0.3 body is not 0.4, and the other way round
        pl.validate(dict(old, lb_schema_version=pl.SCHEMA_VERSION))
    with pytest.raises(pl.InvalidPayload):
        pl.validate(dict(pl.build_payload(**vf.visit()), lb_schema_version=pl.V03_VERSION))


def test_v03_preview_still_builds():
    old = pl.build_payload_v03(**vf.visit())
    r = sp.build_requests(old, sc.DEFAULTS)[0]
    sp.check_composite(r["body"], sc.DEFAULTS)
    assert sp.stored_trees(r["body"], sc.DEFAULTS) == old["trees"]
    assert pl.sha256(dict(old, trees=sp.stored_trees(r["body"], sc.DEFAULTS))) == V03_FIXTURE_SHA


def test_v04_preview_carries_reasons_same_count():
    new, old = pl.build_payload(**vf.visit()), pl.build_payload_v03(**vf.visit())
    subs = sp.build_requests(new, sc.DEFAULTS)[0]["body"]["compositeRequest"]
    assert len(subs) == len(sp.build_requests(old, sc.DEFAULTS)[0]["body"]["compositeRequest"])
    outs = [s["body"] for s in subs if s["url"].endswith("/Talking_Point_Outcome__c")]
    assert [(o["Not_Addressed_Reason__c"], o["Addendum__c"]) for o in outs] == [(None, False), ("OUT_OF_TIME", False)]
    assert all(set(NEW) <= set(o) for o in outs)
    body = {"allOrNone": True, "compositeRequest": subs}
    sp.check_composite(body, sc.DEFAULTS)
    assert sp.stored_trees(body, sc.DEFAULTS) == new["trees"]
    assert sp.COMPOSITE_MAX == 25 and sp.PREVIEWABLE == ("lb-sf-tree-0.3", "lb-sf-tree-0.4")


def test_v02_and_unknown_not_previewable():
    with pytest.raises(sp.NotPreviewable, match="Event root"):
        sp.build_requests(pl.build_payload_v02(**vf.visit()), sc.DEFAULTS)
    with pytest.raises(sp.NotPreviewable) as e:
        sp.build_requests(dict(pl.build_payload(**vf.visit()), lb_schema_version="lb-sf-tree-9.9"), sc.DEFAULTS)
    assert "Event root" not in str(e.value)


def test_stored_03_row_never_rewritten(tmp_path, monkeypatch):
    db = tmp_path / "v.db"
    with monkeypatch.context() as m:  # a save made before v0.2-g
        m.setattr(pl, "build_payload", pl.build_payload_v03)
        old = visits.save_visit(db=db, **vf.visit())
    new = visits.save_visit(db=db, **vf.visit())
    rows = sqlite3.connect(db).execute("SELECT version, schema_version, sha256 FROM sf_payloads ORDER BY version").fetchall()
    assert rows == [(1, "lb-sf-tree-0.3", V03_FIXTURE_SHA), (2, "lb-sf-tree-0.4", new["sha256"])]
    assert old["sha256"] == V03_FIXTURE_SHA


def test_visit_files_02_and_03_and_old_rows(tmp_path):
    db = tmp_path / "v.db"
    visits.save_visit(db=db, **vf.visit())
    f03 = visits.visit_file(visits.lookup("demo rep", "2026-11-18", "SYNCP000025", db=db))
    doc = json.loads(f03)
    assert doc["lb_visit_file"] == visits.FILE_VERSION == "lb-visit-file-0.3"
    loaded = visits.parse_visit_file(f03)
    assert [(o.reason_code, o.addendum) for o in loaded["outcomes"]] == [(None, False), ("OUT_OF_TIME", False)]
    assert visits.save_visit(db=db, **{**vf.visit(), "outcomes": loaded["outcomes"]})["version"] == 2
    # a 0.2 file (before v0.2-g): no reason keys, a 0.3 payload
    d02 = copy.deepcopy(doc)
    d02["lb_visit_file"] = "lb-visit-file-0.2"
    for o in d02["visit"]["outcomes"]:
        for k in ("reason_code", "reason_text", "addendum"):
            o.pop(k)
    d02["payload"] = pl.build_payload_v03(**vf.visit())
    l02 = visits.parse_visit_file(json.dumps(d02).encode())
    assert l02["payload"]["lb_schema_version"] == "lb-sf-tree-0.3"
    assert [(o.reason_code, o.addendum) for o in l02["outcomes"]] == [(None, False), (None, False)]
    with pytest.raises(ValueError):  # saving it as 0.4 needs the missing reason first (D-0047)
        visits.save_visit(db=db, **{**vf.visit(), "outcomes": l02["outcomes"]})
    # an old store row without the new keys reads back with the defaults
    c = sqlite3.connect(db)
    old = [{k: v for k, v in o.items() if k not in ("reason_code", "reason_text", "addendum")}
           for o in json.loads(c.execute("SELECT outcomes_json FROM visits").fetchone()[0])]
    with c:
        c.execute("UPDATE visits SET outcomes_json = ?", (json.dumps(old),))
    c.close()
    got = visits.lookup("demo rep", "2026-11-18", "SYNCP000025", db=db)["visit"]["outcomes"]
    assert [(o["reason_code"], o["reason_text"], o["addendum"]) for o in got] == [(None, None, False)] * 2
