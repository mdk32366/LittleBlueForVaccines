"""T-0085 the save gate (D-0047, AS-0075): on narratives 02 and 04 Save is disabled and an inline warning names every
unresolved key; nothing is pre-picked (no resolution radio and no reason has a default); a reason of Other without
details still blocks, and so do details over 280 characters; once every point is resolved Save is enabled and the
reasons reach the stored payload. visits.save_visit refuses an unresolved outcome on its own (ValueError, nothing
written). Mutations: reason_optional (0.4 reason rules dropped and unresolved() ignores reasons), gap_panel_off.
v0.2-h1 amendments (PR 14 review N4, N5): save_visit's own gate is told apart from the 0.4 schema (its message, and not
InvalidPayload; mutation savevisit_gate_off), and 'Save loaded visit' is disabled until the loaded file's missing
reason is set (AppTest; mutation loaded_gate_off)."""
import copy
import json
import sqlite3

import pytest

from brief import gap, payload as pl, visits, visit_tab
from tests import narratives_fixture as nf, visit_fixture as vf
from tests.conftest import resolve_gaps

CASES = nf.cases()


def _warning(at) -> str:
    return " ".join(w.value for w in at.warning if w.value.startswith("Not saved yet"))


def _stored(tmp_path, sid):
    return visits.lookup("demo rep", "2026-11-18", sid, db=tmp_path / "ui.db")


@pytest.mark.parametrize("n", ["02", "04"])
def test_save_blocked_and_warning_names_keys(n, tmp_path, monkeypatch):
    case = CASES[n]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    planted = nf.planted_gaps(case)
    assert at.button(key="vr_save").disabled
    msg = _warning(at)
    assert msg.startswith(f"Not saved yet: {len(planted)} talking point") and all(k in msg for k in planted), msg
    for k in planted:  # no silent default: the rep has to pick a path
        assert at.radio(key=nf.mode_key(case["sid"], k)).value is None


def test_reason_has_no_default_other_needs_details(tmp_path, monkeypatch):
    case = CASES["02"]
    sid, k = case["sid"], "must.A2.2"
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    at.radio(key=nf.mode_key(sid, k)).set_value(visit_tab.GAP["A"]).run()
    assert at.selectbox(key=nf.reason_key(sid, k)).value is None  # no default reason
    assert at.button(key="vr_save").disabled
    at.selectbox(key=nf.reason_key(sid, k)).set_value(gap.REASONS["OTHER"]).run()
    assert at.button(key="vr_save").disabled and k in _warning(at)  # Other needs details
    at.text_input(key=nf.text_key(sid, k)).input("   ").run()
    assert at.button(key="vr_save").disabled  # blank details are not details
    at.text_input(key=nf.text_key(sid, k)).input("d" * 281).run()
    assert at.button(key="vr_save").disabled  # 281 characters are refused
    at.text_input(key=nf.text_key(sid, k)).input("Clinic closed early for a staff meeting.").run()
    assert not at.button(key="vr_save").disabled and not _warning(at)
    at.button(key="vr_save").click().run()
    assert not at.exception
    outs = {o["key"]: o for o in _stored(tmp_path, sid)["visit"]["outcomes"]}
    assert (outs[k]["reason_code"], outs[k]["reason_text"]) == ("OTHER", "Clinic closed early for a staff meeting.")


def test_all_resolved_enables_save_and_stores_reasons(tmp_path, monkeypatch):
    case = CASES["04"]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    resolve_gaps(at, "NOT_RELEVANT")
    assert not at.button(key="vr_save").disabled and not _warning(at)
    at.button(key="vr_save").click().run()
    assert not at.exception
    found = _stored(tmp_path, case["sid"])
    assert found and found["payload"]["lb_schema_version"] == pl.SCHEMA_VERSION == "lb-sf-tree-0.4"
    pl.validate(found["payload"])
    kids = {r["Talking_Point_Key__c"]: r for r in
            found["payload"]["trees"]["Visit__c"]["records"][0]["Talking_Point_Outcomes__r"]["records"]}
    planted = nf.planted_gaps(case)
    for key, rec in kids.items():
        want = "NOT_RELEVANT" if key in planted else None
        assert (rec["Not_Addressed_Reason__c"], rec["Addendum__c"]) == (want, False), key
        assert rec["Addressed__c"] == planted.get(key, "Raised"), key


def _raw(**over):
    o = pl.Outcome(vf.POINTS[1], "Not raised", "Neutral", 3, "", "")
    return [vf.outcomes()[0], pl.Outcome(**{**o.__dict__, **over})]


@pytest.mark.parametrize("over", [{}, {"reason_code": "OTHER"}, {"reason_code": "OTHER", "reason_text": "  "},
                                  {"reason_code": "OUT_OF_TIME", "reason_text": "x" * 281},
                                  {"reason_code": "BUSY"}, {"addressed": "Partially"},
                                  {"addressed": "Raised", "reason_code": "OUT_OF_TIME"}])
def test_save_visit_refuses_unresolved(over, tmp_path):
    db = tmp_path / "v.db"
    outs = _raw(**over)
    assert gap.unresolved(outs)
    with pytest.raises(ValueError):
        visits.save_visit(db=db, **vf.visit(outcomes=outs))
    if db.exists():
        assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM sf_payloads").fetchone() == (0,)


def test_resolved_outcomes_save(tmp_path):
    for over in ({"reason_code": "OUT_OF_TIME"}, {"reason_code": "OTHER", "reason_text": "x" * 280},
                 {"addressed": "Partially", "reason_code": "CONTACT_DECLINED"}, {"addressed": "Raised"}):
        outs = _raw(**over)
        assert not gap.unresolved(outs), over
        res = visits.save_visit(db=tmp_path / "ok.db", **vf.visit(outcomes=outs))
        kid = res["payload"]["trees"]["Visit__c"]["records"][0]["Talking_Point_Outcomes__r"]["records"][1]
        assert kid["Not_Addressed_Reason__c"] == over.get("reason_code"), over
    assert json.loads(sqlite3.connect(tmp_path / "ok.db").execute(
        "SELECT outcomes_json FROM visits").fetchone()[0])[1]["reason_code"] is None  # last save: Raised, no reason


@pytest.mark.parametrize("over", [{}, {"addressed": "Partially"}])
def test_save_visit_gate_is_its_own_refusal(over, tmp_path):
    """N4: the refusal comes from save_visit's gap.unresolved check, not from the 0.4 schema (InvalidPayload is a
    ValueError too, so a bare pytest.raises(ValueError) could not tell them apart)."""
    db = tmp_path / "v.db"
    with pytest.raises(ValueError, match="need a reason or an addendum") as e:
        visits.save_visit(db=db, **vf.visit(outcomes=_raw(**over)))
    assert not isinstance(e.value, pl.InvalidPayload), repr(e.value)
    assert not db.exists() or sqlite3.connect(db).execute("SELECT COUNT(*) FROM sf_payloads").fetchone() == (0,)


def test_apptest_save_loaded_gate(tmp_path, monkeypatch):
    """N5: a loaded visit file whose Not raised point has no reason (a file saved before v0.2-g) keeps 'Save loaded
    visit' disabled until the (A) reason is picked; then it saves."""
    good = tmp_path / "good.db"
    visits.save_visit(db=good, **vf.visit())
    doc = json.loads(visits.visit_file(visits.lookup("demo rep", "2026-11-18", "SYNCP000025", db=good)))
    doc["lb_visit_file"] = "lb-visit-file-0.2"
    for o in doc["visit"]["outcomes"]:
        for k in ("reason_code", "reason_text", "addendum"):
            o.pop(k)
    doc["payload"] = pl.build_payload_v03(**vf.visit())
    body = json.dumps(copy.deepcopy(doc)).encode()
    at = nf.app_with_notes(tmp_path, monkeypatch, CASES["01"])  # 01: nothing to resolve in the typed panel
    at.file_uploader(key="vr_upload").set_value(("visit.json", body, "application/json")).run()
    assert not at.exception, [e.value for e in at.exception]
    assert any(s.value.startswith("Valid visit file") for s in at.success)
    rk = nf.reason_key("SYNCP000025", "R3", "loaded")
    assert at.selectbox(key=rk).value is None
    assert at.button(key="vr_save_loaded").disabled  # the gate under test
    at.selectbox(key=rk).set_value(gap.REASONS["OUT_OF_TIME"]).run()
    assert not at.button(key="vr_save_loaded").disabled
    at.button(key="vr_save_loaded").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any(s.value.startswith("Saved loaded visit") for s in at.success)
