"""T-0086 'Address now' (D-0047): the second pass runs hint_status on the addendum text only and only for the points
sent to it that are not Raised; the status never goes down; points that come back Raised leave the panel and the rest
return to it; rounds repeat; each round is added to the saved notes as 'Addendum n: ...' and the point is stored with
addendum=True; with no room left under the notes limit, an addendum can't be added and the panel says why.
Mutation: second_pass_rescans_covered (every point is re-checked and its status overwritten).
v0.2-h1 amendment (PR 14 review N7): a typed Save clears that system's 'Not covered yet' state, so the next visit to the
same system in the same browser session starts without the earlier addenda and floors."""
from brief import gap, payload as pl, talking, visits, visit_tab
from tests import narratives_fixture as nf

CASES = nf.cases()
ADD02 = "Dollar share of DTaP is well above the national file, and they want to keep that volume."
ADD04 = ("Shingles to adult-labelled influenza uptake runs ahead of the national file this year. "  # both ratio sides
         "Hepatitis came up only briefly.")  # (AS-0086: the numerator alone would only be Partially)
ADD04_2 = "Hepatitis dollar share is well above the national file, and they asked for the index page."
MISSED04 = ["fixed.A2.1", "must.R5", "must.A2.3", "must.R6", "question.F2"]


def _outs(n, real_client):
    case = CASES[n]
    notes = nf.notes(case)
    return [pl.Outcome(p, pl.hint_status(p, notes)) for p in talking.payload_points(case["sid"], real_client)]


def test_02_addendum_raises_the_missed_point(real_client):
    before = _outs("02", real_client)
    after = gap.second_pass(before, ADD02, ["must.A2.2"])
    a = {o.point.key: o for o in after}
    assert (a["must.A2.2"].addressed, a["must.A2.2"].addendum) == ("Raised", True)
    assert [o for o in after if o.point.key != "must.A2.2"] == [o for o in before if o.point.key != "must.A2.2"]
    assert gap.uncovered(after) == []


def test_04_round_one_then_round_two(real_client):
    after = gap.second_pass(_outs("04", real_client), ADD04, MISSED04)
    a = {o.point.key: o for o in after}
    assert a["must.R5"].addressed == "Raised" and a["must.A2.3"].addressed == "Partially"
    assert {o.point.key: o.addressed for o in gap.uncovered(after)} == {
        "fixed.A2.1": "Not raised", "must.A2.3": "Partially", "must.R6": "Not raised", "question.F2": "Not raised"}
    assert all(a[k].addendum for k in MISSED04) and not a["fixed.A1"].addendum and not a["fixed.F5"].addendum
    again = {o.point.key: o for o in gap.second_pass(after, ADD04_2, ["must.A2.3"])}
    assert again["must.A2.3"].addressed == "Raised" and again["must.R5"] == a["must.R5"]


def test_spy_only_uncovered_keys_and_raised_unchanged(real_client, monkeypatch):
    before = _outs("04", real_client)
    seen = []
    real = pl.hint_status
    monkeypatch.setattr(pl, "hint_status", lambda p, t: seen.append(p.key) or real(p, t))
    after = gap.second_pass(before, ADD04, [o.point.key for o in before])  # even when asked for every key
    assert seen == MISSED04  # covered points are never re-checked
    for b, a in zip(before, after):
        if b.addressed == "Raised":
            assert a == b  # unchanged, and never listed again
    assert "fixed.A1" not in {o.point.key for o in gap.uncovered(after)}


def test_status_never_goes_down(real_client):
    before = _outs("05", real_client)
    part = next(o for o in before if o.point.key == "must.A2.3")
    assert part.addressed == "Partially"
    after = {o.point.key: o for o in gap.second_pass(before, "We only talked about parking.",
                                                    [o.point.key for o in before])}
    assert after["must.A2.3"].addressed == "Partially" and after["must.A2.3"].addendum
    assert all(after[o.point.key].addressed == "Raised" for o in before if o.addressed == "Raised")
    assert gap.upgrade("Partially", "Not raised") == "Partially" and gap.upgrade("Not raised", "Raised") == "Raised"


def _path_b(at, sid, keys):
    for k in keys:
        at.radio(key=nf.mode_key(sid, k)).set_value(visit_tab.GAP["B"]).run()


def _add(at, sid, text):
    box = next(t for t in at.text_area if str(t.key).startswith(f"vr_gap_add_{sid}_"))
    box.input(text).run()
    at.button(key=f"vr_gap_check_{sid}").click().run()
    assert not at.exception, [e.value for e in at.exception]


def test_apptest_path_b_02(tmp_path, monkeypatch):
    case = CASES["02"]
    sid = case["sid"]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    _path_b(at, sid, ["must.A2.2"])
    assert at.button(key="vr_save").disabled  # B alone does not resolve; the addendum has to be checked
    _add(at, sid, ADD02)
    assert nf.panel(at) == {} and not at.button(key="vr_save").disabled
    at.button(key="vr_save").click().run()
    found = visits.lookup("demo rep", "2026-11-18", sid, db=tmp_path / "ui.db")
    assert found["visit"]["notes_text"] == nf.notes(case) + "\n\nAddendum 1: " + ADD02
    o = {x["key"]: x for x in found["visit"]["outcomes"]}["must.A2.2"]
    assert (o["addressed"], o["addendum"], o["reason_code"]) == ("Raised", True, None)


def test_apptest_path_b_04_repeat_rounds(tmp_path, monkeypatch):
    case = CASES["04"]
    sid = case["sid"]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    _path_b(at, sid, MISSED04)
    _add(at, sid, ADD04)
    assert nf.panel(at) == {"fixed.A2.1": "Not raised", "must.A2.3": "Partially", "must.R6": "Not raised",
                            "question.F2": "Not raised"}
    for k in ("fixed.A2.1", "must.R6", "question.F2"):
        at.radio(key=nf.mode_key(sid, k)).set_value(visit_tab.GAP["A"]).run()
        at.selectbox(key=nf.reason_key(sid, k)).set_value(gap.REASONS["OUT_OF_TIME"]).run()
    assert at.button(key="vr_save").disabled and "must.A2.3" in " ".join(w.value for w in at.warning)
    _add(at, sid, ADD04_2)  # round 2: must.A2.3 is still on Address now
    assert nf.panel(at) == {"fixed.A2.1": "Not raised", "must.R6": "Not raised", "question.F2": "Not raised"}
    assert not at.button(key="vr_save").disabled
    at.button(key="vr_save").click().run()
    found = visits.lookup("demo rep", "2026-11-18", sid, db=tmp_path / "ui.db")
    assert found["visit"]["notes_text"] == (nf.notes(case) + "\n\nAddendum 1: " + ADD04 + "\n\nAddendum 2: " + ADD04_2)
    outs = {x["key"]: x for x in found["visit"]["outcomes"]}
    assert {k: (o["addressed"], o["addendum"], o["reason_code"]) for k, o in outs.items()} == {
        "fixed.A1": ("Raised", False, None), "fixed.F5": ("Raised", False, None),
        "fixed.A2.1": ("Not raised", True, "OUT_OF_TIME"), "must.R5": ("Raised", True, None),
        "must.A2.3": ("Raised", True, None), "must.R6": ("Not raised", True, "OUT_OF_TIME"),
        "question.F2": ("Not raised", True, "OUT_OF_TIME")}
    kids = found["payload"]["trees"]["Visit__c"]["records"][0]["Talking_Point_Outcomes__r"]["records"]
    assert {r["Talking_Point_Key__c"]: r["Addendum__c"] for r in kids} == {k: o["addendum"] for k, o in outs.items()}


def test_notes_limit_disables_addendum(tmp_path, monkeypatch):
    case = dict(CASES["02"])
    pad = visits.NOTES_MAX - len(nf.notes(case)) - 10
    case["file"] = tmp_path / "long.txt"
    case["file"].write_text(nf.notes(CASES["02"]) + "z" * pad)
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    sid = case["sid"]
    assert nf.panel(at) == {"must.A2.2": "Not raised"}
    _path_b(at, sid, ["must.A2.2"])
    assert any(w.value.startswith("No room for an addendum") for w in at.warning)
    assert not [t for t in at.text_area if str(t.key).startswith(f"vr_gap_add_{sid}_")]
    short = dict(CASES["02"])
    at2 = nf.app_with_notes(tmp_path / "b", monkeypatch, short)
    _path_b(at2, sid, ["must.A2.2"])
    box = next(t for t in at2.text_area if str(t.key).startswith(f"vr_gap_add_{sid}_"))
    assert box.max_chars == visits.NOTES_MAX - len(nf.notes(short)) - 16


def test_save_clears_gap_state_n7(tmp_path, monkeypatch):
    case = CASES["02"]
    sid = case["sid"]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    _path_b(at, sid, ["must.A2.2"])
    _add(at, sid, ADD02)
    assert at.session_state["vr_gap"][sid]["addenda"] == [ADD02]
    at.button(key="vr_save").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert sid not in at.session_state["vr_gap"]  # cleared on Save
    at.text_input(key="vr_rep").input("Second Rep").run()  # the next visit to the same system, same session
    assert nf.panel(at) == {"must.A2.2": "Not raised"}  # no inherited floor
    assert not [c.value for c in at.caption if c.value.startswith("Added to the notes on save")]
    assert at.button(key="vr_save").disabled
