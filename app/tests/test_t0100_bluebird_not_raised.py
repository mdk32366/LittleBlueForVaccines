"""T-0100 Bluebird on the Visit record tab, bug 2 and the empty button (AS-0087), AppTest against the stub:
- a Not raised point takes a labelled Neutral default and is never sent; Save needs a pick only for Raised and
  Partially points, and the saved Not raised responses are Neutral;
- the rep's own pick on a Not raised point is kept and saved; when the rep sets a Not raised point to Raised, the
  unedited default is withdrawn and Save waits for a pick again;
- the Suggest button with nothing Raised or Partially says so and why (no notes, or nothing covered), and sends nothing.
Mutations: bb_not_raised_unpicked, bb_button_silent."""
import datetime

import pytest
from streamlit.testing.v1 import AppTest

from brief import visit_tab
from tests import narratives_fixture as nf
from tests.bluebird_stub import Stub
from tests.conftest import resolve_gaps

CASE = nf.cases()["03"]
SID = CASE["sid"]
KEYS = [r[0] for r in CASE["rows"]]
STATUS = {e["key"]: e["status"] for e in nf.h1_expected(CASE)}
ELIGIBLE = [k for k in KEYS if STATUS[k] in ("Raised", "Partially")]
NOT_RAISED = [k for k in KEYS if STATUS[k] == "Not raised"]


@pytest.fixture
def stub():
    s = Stub(answer=lambda body: "Positive")
    yield s
    s.close()


def on(monkeypatch, url):
    monkeypatch.setenv("LB_BLUEBIRD", "on")
    monkeypatch.setenv("LB_BLUEBIRD_URL", url)


def resp(at, k):
    return at.selectbox(key=f"vr_resp_{SID}_{KEYS.index(k)}").value


def saved(at) -> dict:
    kids = at.session_state["vr_last_saved"]["payload"]["trees"]["Visit__c"]["records"][0][
        "Talking_Point_Outcomes__r"]["records"]
    return {k: kid["Customer_Response__c"] for k, kid in zip(KEYS, kids)}


def app_typed(tmp_path, monkeypatch, notes):
    monkeypatch.setenv("LB_VISITS_DB", str(tmp_path / "ui.db"))
    at = AppTest.from_file(nf.APP, default_timeout=240).run()
    at.selectbox(key="system").set_value(SID).run()
    at.text_input(key="vr_rep").input("Demo Rep").run()
    at.date_input(key="vr_date").set_value(datetime.date(2026, 11, 18)).run()
    if notes:
        at.text_area(key="vr_notes").input(notes).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_case_has_both_kinds():
    assert ELIGIBLE and NOT_RAISED


def test_not_raised_default_needs_no_pick_and_saves_neutral(tmp_path, monkeypatch, stub):
    on(monkeypatch, stub.url)
    at = nf.app_with_notes(tmp_path, monkeypatch, CASE)
    at.button(key=visit_tab.BB_BUTTON_KEY).click().run()
    assert {k: resp(at, k) for k in ELIGIBLE} == {k: "Positive" for k in ELIGIBLE}
    assert {k: resp(at, k) for k in NOT_RAISED} == {k: "Neutral" for k in NOT_RAISED}
    assert len(stub.requests) == len(ELIGIBLE)
    assert all(visit_tab._bb_provenance(at.session_state, SID, k) == visit_tab.SRC_NR for k in NOT_RAISED)
    resolve_gaps(at)
    assert not at.button(key="vr_save").disabled  # no pick needed for the Not raised points
    at.button(key="vr_save").click().run()
    assert not at.exception, [e.value for e in at.exception]
    got = saved(at)
    assert all(got[k] == "Neutral" for k in NOT_RAISED) and all(got[k] == "Positive" for k in ELIGIBLE)


def test_rep_pick_on_not_raised_is_kept(tmp_path, monkeypatch, stub):
    on(monkeypatch, stub.url)
    at = nf.app_with_notes(tmp_path, monkeypatch, CASE)
    mine = NOT_RAISED[0]
    at.selectbox(key=f"vr_resp_{SID}_{KEYS.index(mine)}").set_value("Objection").run()
    at.button(key=visit_tab.BB_BUTTON_KEY).click().run()
    assert resp(at, mine) == "Objection"
    assert visit_tab._bb_provenance(at.session_state, SID, mine) == "edited"


def test_not_raised_set_to_raised_withdraws_the_default(tmp_path, monkeypatch, stub):
    on(monkeypatch, stub.url)
    at = nf.app_with_notes(tmp_path, monkeypatch, CASE)
    k = NOT_RAISED[0]
    i = KEYS.index(k)
    assert resp(at, k) == "Neutral"
    at.selectbox(key=f"vr_addr_{SID}_{i}_Not raised").set_value("Raised").run()
    assert not at.exception, [e.value for e in at.exception]
    assert resp(at, k) is None  # the default does not carry over to a discussed point
    warn = " ".join(w.value for w in at.warning if visit_tab.BB["pick"] in w.value)
    assert k in warn and at.button(key="vr_save").disabled


def test_button_with_no_notes_says_why(tmp_path, monkeypatch, stub):
    on(monkeypatch, stub.url)
    at = app_typed(tmp_path, monkeypatch, "")
    at.button(key=visit_tab.BB_BUTTON_KEY).click().run()
    assert visit_tab.BB["no_notes"] in [m.value for m in at.info]
    assert stub.requests == []


def test_button_with_nothing_covered_says_why(tmp_path, monkeypatch, stub):
    on(monkeypatch, stub.url)
    at = app_typed(tmp_path, monkeypatch, "We only talked about parking and the weather.")
    at.button(key=visit_tab.BB_BUTTON_KEY).click().run()
    assert visit_tab.BB["nothing"] in [m.value for m in at.info]
    assert stub.requests == []
