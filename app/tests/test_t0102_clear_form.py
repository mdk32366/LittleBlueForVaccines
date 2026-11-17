"""T-0102 'Clear form' on the Visit record tab (AS-0089), AppTest on narrative 03:
- the first click only asks; Cancel keeps everything;
- 'Yes, clear the form' empties the rep, notes and every per-point value (Addressed back to the hint of empty notes,
  quotes and follow-ups blank, 'Not covered yet' reasons gone), and says so;
- a saved visit is still found by lookup after a clear, and the save counter is not reset;
- with Bluebird on, the model's suggestions and their provenance are dropped too.
Mutations: clear_keeps_points, clear_resets_saves."""
import datetime

import pytest

from brief import visit_tab
from tests import narratives_fixture as nf
from tests.bluebird_stub import Stub
from tests.conftest import resolve_gaps

CASE = nf.cases()["03"]
SID = CASE["sid"]
KEYS = [r[0] for r in CASE["rows"]]


def ask_and_confirm(at):
    at.button(key=visit_tab.CLEAR_KEY).click().run()
    assert visit_tab.CLEAR["ask"] in [w.value for w in at.warning]
    at.button(key=visit_tab.CLEAR_YES_KEY).click().run()
    assert not at.exception, [e.value for e in at.exception]


def addressed(at):
    return [s.value for s in at.selectbox if str(s.key or "").startswith(f"vr_addr_{SID}_")]


def filled(at, prefix):
    return [t.value for t in at.text_input if str(t.key or "").startswith(f"{prefix}{SID}_") and t.value]


def test_cancel_keeps_the_form(tmp_path, monkeypatch):
    at = nf.app_with_notes(tmp_path, monkeypatch, CASE)
    before = at.text_area(key="vr_notes").value
    at.button(key=visit_tab.CLEAR_KEY).click().run()
    at.button(key=visit_tab.CLEAR_NO_KEY).click().run()
    assert at.text_area(key="vr_notes").value == before and before
    assert visit_tab.CLEAR["ask"] not in [w.value for w in at.warning]


def test_clear_empties_the_form(tmp_path, monkeypatch):
    at = nf.app_with_notes(tmp_path, monkeypatch, CASE)
    resolve_gaps(at)
    assert filled(at, "vr_ev_") and "Raised" in addressed(at)
    assert any(s.value for s in at.selectbox if str(s.key or "").startswith(f"vr_gap_reason_typed_{SID}_"))
    ask_and_confirm(at)
    assert visit_tab.CLEAR["done"] in [m.value for m in at.success]
    assert not at.text_input(key="vr_rep").value and not at.text_area(key="vr_notes").value
    assert addressed(at) == ["Not raised"] * len(KEYS)  # what empty notes hint
    assert not filled(at, "vr_ev_") and not filled(at, "vr_fu_")
    assert not any(s.value for s in at.selectbox if str(s.key or "").startswith(f"vr_gap_reason_typed_{SID}_"))
    assert at.button(key="vr_save").disabled  # nothing resolved again


def test_saved_visit_survives_and_save_count_kept(tmp_path, monkeypatch):
    at = nf.app_with_notes(tmp_path, monkeypatch, CASE)
    resolve_gaps(at)
    at.button(key="vr_save").click().run()
    assert at.session_state["vr_saves"] == 1
    ask_and_confirm(at)
    assert at.session_state["vr_saves"] == 1
    at.text_input(key="vr_l_rep").input("Demo Rep").run()
    at.date_input(key="vr_l_date").set_value(datetime.date(2026, 11, 18)).run()
    at.button(key="vr_lookup").click().run()
    found = at.session_state["vr_found"]
    assert isinstance(found, dict) and found["visit"]["notes_text"].startswith(nf.notes(CASE)[:40])


@pytest.fixture
def stub():
    s = Stub(answer=lambda body: "Positive")
    yield s
    s.close()


def test_clear_drops_bluebird_suggestions(tmp_path, monkeypatch, stub):
    monkeypatch.setenv("LB_BLUEBIRD", "on")
    monkeypatch.setenv("LB_BLUEBIRD_URL", stub.url)
    at = nf.app_with_notes(tmp_path, monkeypatch, CASE)
    at.button(key=visit_tab.BB_BUTTON_KEY).click().run()
    assert any(v == "Positive" for v in (at.selectbox(key=f"vr_resp_{SID}_{i}").value for i in range(len(KEYS))))
    ask_and_confirm(at)
    assert SID not in at.session_state["vr_bb"]
    srcs = [r["src"] for k, r in at.session_state["vr_bb_auto"].items() if k[0] == SID]
    assert visit_tab.SRC_BB not in srcs  # only the Not raised defaults of the now empty notes are left
    assert all(at.selectbox(key=f"vr_resp_{SID}_{i}").value != "Positive" for i in range(len(KEYS)))
