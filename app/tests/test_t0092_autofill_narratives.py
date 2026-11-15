"""T-0092 the five narratives (D-0048), AppTest: with each committed narrative typed into the notes, every point's
status, Evidence quote and Follow-up equal tests/fixtures/narratives/h1-fixture-expected.json exactly (the
Architect's fixture; status, evidence and follow-up for every Raised or Partially point); every Not raised point has
both fields empty and no auto-fill record at all.
Mutations: quote_paraphrased, followup_without_cue, autofill_on_not_raised."""
import pytest

from tests import narratives_fixture as nf

CASES = nf.cases()


def _status(at, sid, i) -> str:
    keys = [s.key for s in at.selectbox if str(s.key or "").startswith(f"vr_addr_{sid}_{i}_")]
    assert len(keys) == 1, keys
    return at.selectbox(key=keys[0]).value


def test_fixture_covers_every_point():
    for n, case in CASES.items():
        assert [e["key"] for e in nf.h1_expected(case)] == [r[0] for r in case["rows"]], n


@pytest.mark.parametrize("n", sorted(CASES))
def test_narrative_matches_fixture(n, tmp_path, monkeypatch):
    case = CASES[n]
    sid = case["sid"]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    reg = at.session_state["vr_auto"]
    for i, e in enumerate(nf.h1_expected(case)):
        got = (_status(at, sid, i), at.text_input(key=f"vr_ev_{sid}_{i}").value,
               at.text_input(key=f"vr_fu_{sid}_{i}").value)
        if e["status"] == "Not raised":
            assert got == ("Not raised", "", ""), (e["key"], got)
            assert not [k for k in reg if k[:2] == (sid, e["key"])], e["key"]  # nothing auto-filled at all
        else:
            assert got == (e["status"], e["evidence"], e["follow_up"]), (e["key"], got)
