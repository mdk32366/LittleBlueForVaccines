"""T-0096 Bluebird in the Visit record tab, flag ON (D-0049, AS-0082, AS-0083), against a stub sidecar on loopback:
- AppTest on 03 (Raised and Not raised points) and 05 (a Partially point).
- Customer response only: one click asks the model for every Raised or Partially point and fills only vr_resp; the
  Evidence quote and Follow-up stay the rule-based values, Quality stays 3, Not raised points are not sent;
- nothing discussed is pre-picked: no Raised or Partially response is Neutral by default, and Save stays disabled
  until each is picked by the rep or filled by the model; a Not raised point takes a labelled Neutral default and is
  never sent (AS-0087, bug 2);
- edits win: a response the rep picked is never overwritten by a later click;
- model down: nothing is filled, the rep is told, and no Neutral is ever saved for them;
- a suggestion made from older notes is withdrawn when the notes change.
Mutations: bb_fills_not_raised, bb_overwrites_edit, bb_down_neutral, bb_unpicked_saves, bb_stale_kept."""
import pytest

from brief import payload as pl, visit_tab, visits
from tests import narratives_fixture as nf
from tests.bluebird_stub import Stub, free_port_url
from tests.conftest import resolve_gaps

CASE = nf.cases()["03"]
SID = CASE["sid"]
KEYS = [r[0] for r in CASE["rows"]]
STATUS = {e["key"]: e["status"] for e in nf.h1_expected(CASE)}
ELIGIBLE = [k for k in KEYS if STATUS[k] in ("Raised", "Partially")]
NOT_RAISED = [k for k in KEYS if STATUS[k] == "Not raised"]


def resp(at, k):
    return at.selectbox(key=f"vr_resp_{SID}_{KEYS.index(k)}").value


def save_button(at):
    return at.button(key="vr_save")


def click(at):
    at.button(key=visit_tab.BB_BUTTON_KEY).click().run()
    assert not at.exception, [e.value for e in at.exception]


def app_on(tmp_path, monkeypatch, url):
    monkeypatch.setenv("LB_BLUEBIRD", "on")
    monkeypatch.setenv("LB_BLUEBIRD_URL", url)
    return nf.app_with_notes(tmp_path, monkeypatch, CASE)


def pick_all(at, value_for):
    for k in KEYS:
        at.selectbox(key=f"vr_resp_{SID}_{KEYS.index(k)}").set_value(value_for(k))
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def saved_responses(at) -> dict:
    kids = at.session_state["vr_last_saved"]["payload"]["trees"]["Visit__c"]["records"][0][
        "Talking_Point_Outcomes__r"]["records"]
    return {k: kid["Customer_Response__c"] for k, kid in zip(KEYS, kids)}


@pytest.fixture
def stub():
    s = Stub(answer=lambda body: "Objection")
    yield s
    s.close()


def test_case_has_both_kinds():  # not vacuous
    assert ELIGIBLE and NOT_RAISED


def test_partially_point_is_filled(tmp_path, monkeypatch, stub):
    case = nf.cases()["05"]
    keys = [r[0] for r in case["rows"]]
    status = {e["key"]: e["status"] for e in nf.h1_expected(case)}
    part = [k for k in keys if status[k] == "Partially"]
    assert part  # not vacuous
    monkeypatch.setenv("LB_BLUEBIRD", "on")
    monkeypatch.setenv("LB_BLUEBIRD_URL", stub.url)
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    click(at)
    got = {k: at.selectbox(key=f"vr_resp_{case['sid']}_{keys.index(k)}").value for k in keys}
    assert got == {k: "Objection" for k in keys}  # every point of 05 is Raised or Partially
    assert len(stub.requests) == len(keys)


def test_nothing_prepicked_and_save_blocked(tmp_path, monkeypatch, stub):
    at = app_on(tmp_path, monkeypatch, stub.url)
    assert {k: resp(at, k) for k in ELIGIBLE} == {k: None for k in ELIGIBLE}
    assert {k: resp(at, k) for k in NOT_RAISED} == {k: "Neutral" for k in NOT_RAISED}  # AS-0087 labelled default
    assert [c.value for c in at.caption].count(visit_tab.BB["not_raised"]) == len(NOT_RAISED)
    assert stub.requests == []  # no model call before the rep clicks
    resolve_gaps(at)
    assert save_button(at).disabled
    warn = " ".join(w.value for w in at.warning if visit_tab.BB["pick"] in w.value)
    assert all(k in warn for k in ELIGIBLE) and not any(f" {k}" in warn or f"{k}," in warn for k in NOT_RAISED)
    caps = [c.value for c in at.caption]
    assert visit_tab.BB["caption"] in caps


def test_click_fills_customer_response_only(tmp_path, monkeypatch, stub):
    at = app_on(tmp_path, monkeypatch, stub.url)
    exp = {e["key"]: e for e in nf.h1_expected(CASE)}
    before = {k: (at.text_input(key=f"vr_ev_{SID}_{KEYS.index(k)}").value,
                  at.text_input(key=f"vr_fu_{SID}_{KEYS.index(k)}").value) for k in KEYS}
    click(at)
    assert {k: resp(at, k) for k in ELIGIBLE} == {k: "Objection" for k in ELIGIBLE}
    assert {k: resp(at, k) for k in NOT_RAISED} == {k: "Neutral" for k in NOT_RAISED}  # the default, not the model
    assert len(stub.requests) == len(ELIGIBLE)  # Not raised points are never sent
    for k in KEYS:  # the rule-based fields and Quality are untouched by the model
        i = KEYS.index(k)
        assert (at.text_input(key=f"vr_ev_{SID}_{i}").value, at.text_input(key=f"vr_fu_{SID}_{i}").value) == before[k]
        assert at.number_input(key=f"vr_q_{SID}_{i}").value == 3
        if STATUS[k] != "Not raised":
            assert before[k] == (exp[k]["evidence"], exp[k]["follow_up"])
    caps = [c.value for c in at.caption]
    assert caps.count(visit_tab.BB["label"]) == len(ELIGIBLE)
    sent = " ".join(r["body"]["prompt"] for r in stub.requests)
    assert all(nf.notes(CASE).strip()[:200] in r["body"]["prompt"] for r in stub.requests) and sent


def test_edits_win(tmp_path, monkeypatch, stub):
    at = app_on(tmp_path, monkeypatch, stub.url)
    click(at)
    mine = ELIGIBLE[0]
    at.selectbox(key=f"vr_resp_{SID}_{KEYS.index(mine)}").set_value("Negative").run()
    stub.answer = lambda body: "Positive"
    click(at)
    assert resp(at, mine) == "Negative"
    assert all(resp(at, k) == "Positive" for k in ELIGIBLE[1:])
    assert visit_tab._bb_provenance(at.session_state, SID, mine) == "edited"
    pick_all(at, lambda k: resp(at, k) or "Negative")
    resolve_gaps(at)
    assert not save_button(at).disabled
    save_button(at).click().run()
    assert not at.exception, [e.value for e in at.exception]
    got = saved_responses(at)
    assert got[mine] == "Negative" and all(got[k] == "Positive" for k in ELIGIBLE[1:])


def test_model_down_never_saves_neutral(tmp_path, monkeypatch):
    at = app_on(tmp_path, monkeypatch, free_port_url())
    click(at)
    assert {k: resp(at, k) for k in ELIGIBLE} == {k: None for k in ELIGIBLE}  # no Neutral for a discussed point
    msgs = " ".join(m.value for m in list(at.warning) + list(at.caption))
    assert visit_tab.BB["down"] in msgs
    resolve_gaps(at)
    assert save_button(at).disabled
    picks = {k: ("Negative" if n % 2 else "Positive") for n, k in enumerate(KEYS)}
    pick_all(at, picks.get)
    assert not save_button(at).disabled
    save_button(at).click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert saved_responses(at) == picks and "Neutral" not in saved_responses(at).values()


def test_notes_change_withdraws_stale_suggestions(tmp_path, monkeypatch, stub):
    at = app_on(tmp_path, monkeypatch, stub.url)
    click(at)
    assert all(resp(at, k) == "Objection" for k in ELIGIBLE)
    mine = ELIGIBLE[0]
    at.selectbox(key=f"vr_resp_{SID}_{KEYS.index(mine)}").set_value("Positive").run()
    at.text_area(key="vr_notes").input(nf.notes(CASE) + " One more line.").run()
    assert not at.exception, [e.value for e in at.exception]
    assert resp(at, mine) == "Positive"  # the rep's own pick stays
    assert all(resp(at, k) is None for k in ELIGIBLE[1:])  # model values from the old notes are withdrawn
    assert visit_tab.BB["stale"] in " ".join(c.value for c in at.caption)


def test_save_visit_refuses_an_unpicked_response(tmp_path):
    p = pl.TalkingPoint("k1", "Point one.")
    with pytest.raises(ValueError):
        visits.save_visit(db=tmp_path / "v.db", rep="demo rep", visit_date="2026-11-18", system_id="SYNCP000025",
                          system_name="x", notes="n", outcomes=[pl.Outcome(p, "Raised", None, 3)])
