"""T-0093 scope (D-0048): the auto-fill writes only the Evidence quote and Follow-up widget state; it never writes
Customer response (vr_resp) or Quality (vr_q), which keep today's defaults (Neutral, 3) and the rep's own picks; a
Not raised point gets nothing; the fixed caveat caption and the "auto (rule-based)" labels are shown.
Mutations: autofill_on_not_raised, score_autofilled, response_autofilled."""
from brief import autofill as af, payload as pl, visit_tab
from tests import narratives_fixture as nf

CASES = nf.cases()
RSV = pl.TalkingPoint("must.A2.1", "Must cover: dollar share of RSV is 70.1% for this system against 5.3% for the pooled "
                                   "national file (45,462 rows), an index of 1332.")
TEXT = "RSV index against the national file was discussed. Please send it."


def test_writes_only_evidence_and_follow_up_keys():
    for status in ("Raised", "Partially"):
        ss = {}
        visit_tab._apply_autofill(ss, "S", 3, RSV, status, TEXT)
        assert set(ss) == {"vr_auto", "vr_ev_S_3", "vr_fu_S_3"}, (status, sorted(ss))
        assert set(af.suggest(RSV, status, TEXT)) == {"evidence", "follow_up"}


def test_not_raised_gets_nothing():
    assert af.suggest(RSV, "Not raised", TEXT) == {}
    ss = {}
    visit_tab._apply_autofill(ss, "S", 0, RSV, "Not raised", TEXT)
    assert ss == {"vr_auto": {}}


def test_apptest_defaults_kept_caption_and_labels(tmp_path, monkeypatch):
    case = CASES["02"]
    sid = case["sid"]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    n = len(case["rows"])
    assert [at.selectbox(key=f"vr_resp_{sid}_{i}").value for i in range(n)] == ["Neutral"] * n
    assert [at.number_input(key=f"vr_q_{sid}_{i}").value for i in range(n)] == [3] * n
    caps = [c.value for c in at.caption]
    assert caps.count(af.CAPTION) == 1
    assert af.CAPTION == ("Suggestions from keyword rules. Review every value before saving. "
                          "Accuracy has not been measured.")
    filled = sum(bool(at.text_input(key=f"vr_{f}_{sid}_{i}").value) for i in range(n) for f in ("ev", "fu"))
    assert filled == 6 and caps.count(af.LABEL) == filled == caps.count("auto (rule-based)")
    i_nr = [r[0] for r in case["rows"]].index("must.A2.2")
    assert at.text_input(key=f"vr_ev_{sid}_{i_nr}").value == at.text_input(key=f"vr_fu_{sid}_{i_nr}").value == ""
    # the rep's own Customer response and Quality survive a re-run of the auto-fill
    at.selectbox(key=f"vr_resp_{sid}_0").set_value("Objection")
    at.number_input(key=f"vr_q_{sid}_0").set_value(5)
    at.run()
    at.text_area(key="vr_notes").input(nf.notes(case) + " One more line.").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key=f"vr_resp_{sid}_0").value == "Objection" and at.number_input(key=f"vr_q_{sid}_0").value == 5


def test_apptest_not_raised_pick_withdraws_auto(tmp_path, monkeypatch):
    """PR 15 review M-1 (v0.2-h1b): the rep's own Addressed pick of Not raised withdraws the unedited suggestions of
    that point, so its auto follow-up never becomes a Task; a pick back to Raised brings them back.
    Mutation: downgrade_keeps_auto."""
    from tests.conftest import resolve_gaps
    case = CASES["01"]
    sid = case["sid"]
    exp = {e["key"]: e for e in nf.h1_expected(case)}
    keys = [r[0] for r in case["rows"]]
    i = keys.index("fixed.F5")
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    ev, fu = (lambda: at.text_input(key=f"vr_ev_{sid}_{i}").value), (lambda: at.text_input(key=f"vr_fu_{sid}_{i}").value)
    assert exp["fixed.F5"]["status"] == "Raised" and exp["fixed.F5"]["follow_up"]
    assert ev() == exp["fixed.F5"]["evidence"] and fu() == exp["fixed.F5"]["follow_up"]  # not vacuous
    addr = f"vr_addr_{sid}_{i}_Raised"
    at.selectbox(key=addr).set_value("Not raised").run()
    assert not at.exception, [e.value for e in at.exception]
    assert ev() == fu() == ""
    assert visit_tab._provenance(at.session_state, sid, "fixed.F5") == {"evidence": "none", "follow_up": "none"}
    at.selectbox(key=addr).set_value("Raised").run()  # back to Raised: the suggestions return
    assert ev() == exp["fixed.F5"]["evidence"] and fu() == exp["fixed.F5"]["follow_up"]
    at.selectbox(key=addr).set_value("Not raised").run()
    resolve_gaps(at)
    at.button(key="vr_save").click().run()
    assert not at.exception, [e.value for e in at.exception]
    saved = at.session_state["vr_last_saved"]["payload"]
    kids = saved["trees"]["Visit__c"]["records"][0]["Talking_Point_Outcomes__r"]["records"]
    assert [k["Follow_Up__c"] for k in kids] == [""] * len(kids)
    assert "Task" not in saved["trees"]  # no follow-up Task on a Not raised point, so none in the preview either


def test_apptest_edit_survives_not_raised_pick(tmp_path, monkeypatch):
    """PR 16 review L-3 (v0.2-h1c): a Follow-up the rep edited survives a Not raised pick (edits win) with provenance
    `edited`, while the unedited Evidence quote of the same point is withdrawn; the rep's own follow-up still makes its
    Task (rep intent, not auto output). Mutation: not_raised_blanks_edits."""
    from tests.conftest import resolve_gaps
    case = CASES["01"]
    sid = case["sid"]
    exp = {e["key"]: e for e in nf.h1_expected(case)}
    i = [r[0] for r in case["rows"]].index("fixed.F5")
    mine = "Call the pharmacy director back on Friday with the window table."
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    ev, fu = (lambda: at.text_input(key=f"vr_ev_{sid}_{i}").value), (lambda: at.text_input(key=f"vr_fu_{sid}_{i}").value)
    assert fu() == exp["fixed.F5"]["follow_up"] != mine and ev() == exp["fixed.F5"]["evidence"]  # not vacuous
    at.text_input(key=f"vr_fu_{sid}_{i}").input(mine).run()
    at.selectbox(key=f"vr_addr_{sid}_{i}_Raised").set_value("Not raised").run()
    assert not at.exception, [e.value for e in at.exception]
    assert fu() == mine and ev() == ""
    assert visit_tab._provenance(at.session_state, sid, "fixed.F5") == {"evidence": "none", "follow_up": "edited"}
    resolve_gaps(at)
    at.button(key="vr_save").click().run()
    assert not at.exception, [e.value for e in at.exception]
    tasks = at.session_state["vr_last_saved"]["payload"]["trees"]["Task"]["records"]
    assert len(tasks) == 1 and tasks[0]["Description"].endswith(mine)
