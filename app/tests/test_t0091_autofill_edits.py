"""T-0091 edits and provenance (D-0048, AS-0080), AppTest of narrative 02: the auto values fill; the rep edits an
Evidence quote; the notes change and the hints re-run, then an addendum is checked: the edit survives every re-run
while unedited fields keep following the rules; nothing reaches the visit store before Save; after Save
outcomes_json carries the right `auto` provenance and the payload carries no provenance key. A 7-point visit with every
follow-up filled gives 16 Composite subrequests and check_composite passes (≤ 25).
Mutation: edit_overwritten (the auto-fill writes even when a field is `edited`)."""
import json
import sqlite3

from brief import autofill as af, payload as pl, sf_config as sc, sf_preview as sp, talking, visits, visit_tab
from tests import narratives_fixture as nf

CASES = nf.cases()
ADD02 = "Dollar share of DTaP is well above the national file, and they want to keep that volume."
MINE = "My own words about the size of the book."


def _rows(db) -> int:
    if not db.exists():
        return 0
    return sqlite3.connect(db).execute("SELECT COUNT(*) FROM sf_payloads").fetchone()[0]


def test_edit_survives_reruns_and_provenance_after_save(tmp_path, monkeypatch):
    case = CASES["02"]
    sid, db = case["sid"], tmp_path / "ui.db"
    exp = {e["key"]: e for e in nf.h1_expected(case)}
    keys = [r[0] for r in case["rows"]]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    ev = lambda k: at.text_input(key=f"vr_ev_{sid}_{keys.index(k)}").value  # noqa: E731
    assert ev("fixed.A1") == exp["fixed.A1"]["evidence"] and ev("fixed.A2.1") == exp["fixed.A2.1"]["evidence"]
    at.text_input(key=f"vr_ev_{sid}_{keys.index('fixed.A1')}").input(MINE).run()
    assert ev("fixed.A1") == MINE
    # the notes change: the hints and the auto-fill re-run
    new_notes = nf.notes(case).replace("The top class is shingles", "Shingles is the top class", 1)
    assert new_notes != nf.notes(case)
    at.text_area(key="vr_notes").input(new_notes).run()
    assert not at.exception, [e.value for e in at.exception]
    assert ev("fixed.A1") == MINE  # the edit survives
    assert ev("fixed.A2.1").startswith("Shingles is the top class")  # an unedited field follows the new notes
    # 'Address now' + Check addendum: another re-run
    at.radio(key=nf.mode_key(sid, "must.A2.2")).set_value(visit_tab.GAP["B"]).run()
    next(t for t in at.text_area if str(t.key).startswith(f"vr_gap_add_{sid}_")).input(ADD02).run()
    at.button(key=f"vr_gap_check_{sid}").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert ev("fixed.A1") == MINE and ev("must.A2.2") == ADD02
    assert _rows(db) == 0  # nothing stored before Save
    at.button(key="vr_save").click().run()
    assert not at.exception and _rows(db) == 1
    found = visits.lookup("demo rep", "2026-11-18", sid, db=db)
    auto = {o["key"]: o["auto"] for o in found["visit"]["outcomes"]}
    assert auto["fixed.A1"] == {"evidence": "edited", "follow_up": "none"}
    assert auto["fixed.A2.1"] == {"evidence": "auto-rule", "follow_up": "none"}
    assert auto["must.A2.2"] == {"evidence": "auto-rule", "follow_up": "none"}
    stored = {o["key"]: o for o in found["visit"]["outcomes"]}
    assert stored["fixed.A1"]["evidence"] == MINE and stored["must.A2.2"]["evidence"] == ADD02
    assert '"auto"' not in pl.canonical(found["payload"]) and "auto-rule" not in pl.canonical(found["payload"])
    kid = found["payload"]["trees"]["Visit__c"]["records"][0]["Talking_Point_Outcomes__r"]["records"][0]
    assert kid["Evidence_Quote__c"] == MINE and "auto" not in kid


def test_apptest_second_visit_gets_fresh_suggestions(tmp_path, monkeypatch):
    """PR 15 review M-2 (v0.2-h1b): Save resets the auto-fill marks of the system, so on the next visit to the same
    system in the same session a field still holding its saved value takes the fresh suggestion, while a field the rep
    changes after the save is an edit as usual. Mutation: save_keeps_auto_marks."""
    from tests.conftest import resolve_gaps
    case = CASES["02"]
    sid = case["sid"]
    exp = {e["key"]: e for e in nf.h1_expected(case)}
    keys = [r[0] for r in case["rows"]]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    ev = lambda k: at.text_input(key=f"vr_ev_{sid}_{keys.index(k)}").value  # noqa: E731
    at.text_input(key=f"vr_ev_{sid}_{keys.index('fixed.A1')}").input(MINE).run()
    assert ev("fixed.A1") == MINE
    resolve_gaps(at)
    at.button(key="vr_save").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["vr_saves"] == 1
    # the next visit to the same system: the rep changes one field, which also re-runs the auto-fill
    at.text_input(key=f"vr_ev_{sid}_{keys.index('fixed.A2.1')}").input("After save").run()
    assert not at.exception, [e.value for e in at.exception]
    assert ev("fixed.A1") == exp["fixed.A1"]["evidence"] != MINE  # fresh suggestion, not the first visit's edit
    assert ev("fixed.A2.1") == "After save"
    assert visit_tab._provenance(at.session_state, sid, "fixed.A1")["evidence"] == "auto-rule"
    assert visit_tab._provenance(at.session_state, sid, "fixed.A2.1")["evidence"] == "edited"


def test_typed_before_any_suggestion_is_an_edit():
    p = pl.TalkingPoint("must.A2.1", "Must cover: dollar share of RSV is 70.1% for this system, an index of 1332.")
    ss = {"vr_ev_S_0": "typed first"}
    visit_tab._apply_autofill(ss, "S", 0, p, "Raised", "RSV index was discussed. Please send it.")
    assert ss["vr_ev_S_0"] == "typed first" and ss["vr_fu_S_0"] == "Please send it."
    assert visit_tab._provenance(ss, "S", "must.A2.1") == {"evidence": "edited", "follow_up": "auto-rule"}
    visit_tab._apply_autofill(ss, "S", 0, p, "Raised", "RSV index came up again.")  # re-run: edit kept, auto follows
    assert ss["vr_ev_S_0"] == "typed first" and ss["vr_fu_S_0"] == ""
    assert visit_tab._provenance(ss, "S", "must.A2.1") == {"evidence": "edited", "follow_up": "none"}


def test_seven_points_every_follow_up_filled_16_subrequests(real_client):
    pts = talking.payload_points(CASES["02"]["sid"], real_client)
    assert len(pts) == 7
    notes = " ".join(f"{p.text} We will send the summary." for p in pts)
    outs = []
    for p in pts:
        status = pl.hint_status(p, notes)
        s = af.suggest(p, status, notes)
        assert status == "Raised" and s["follow_up"] == "We will send the summary.", p.key
        outs.append(pl.Outcome(p, status, "Neutral", 3, s["evidence"], s["follow_up"]))
    payload = pl.build_payload(rep="Demo Rep", visit_date="2026-11-18", system_id=CASES["02"]["sid"],
                               system_name="Synthetic", notes=notes, outcomes=outs)
    pl.validate(payload)
    reqs = sp.build_requests(payload, sc.DEFAULTS)
    subs = reqs[0]["body"]["compositeRequest"]
    assert len(subs) == 16 == 1 + 7 + 1 + 7 <= sp.COMPOSITE_MAX
    sp.check_composite(reqs[0]["body"], sc.DEFAULTS)
    assert json.dumps(payload).count('"type": "Task"') == 7
