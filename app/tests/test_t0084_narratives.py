"""T-0084 the five committed narratives (tests/fixtures/narratives, expected.md tables parsed verbatim; D-0047): for
each narrative and key, the provider's point text equals the expected.md 'Talking point (app text)' column; with the
hint pre-fill, gap.uncovered() is exactly the planted missed/partial set with the planted status; and an AppTest of
the Visit record tab lists exactly those keys in the 'Not covered yet' panel, with Save disabled unless the set is
empty. Mutations: gap_panel_off (uncovered() returns []), partial_dropped (05), a1_stopworded (01, 02, 04, 05)."""
import pytest

from brief import gap, payload as pl, talking
from tests import narratives_fixture as nf

CASES = nf.cases()
IDS = sorted(CASES)


def test_five_cases_parsed():
    assert IDS == ["01", "02", "03", "04", "05"]
    assert all(len(CASES[n]["rows"]) == 7 for n in IDS)
    assert {n: list(nf.planted_gaps(CASES[n])) for n in IDS} == {
        "01": [], "02": ["must.A2.2"], "03": ["fixed.F5", "must.A2.3"],
        "04": ["fixed.A2.1", "must.R5", "must.A2.3", "must.R6", "question.F2"], "05": ["must.A2.3"]}


@pytest.mark.parametrize("n", IDS)
def test_point_text_equals_expected(n, real_client):
    case = CASES[n]
    got = [(p.key, p.text) for p in talking.payload_points(case["sid"], real_client)]
    assert got == [(k, t) for k, t, _, _ in case["rows"]]


@pytest.mark.parametrize("n", IDS)
def test_uncovered_equals_planted(n, real_client):
    case = CASES[n]
    notes = nf.notes(case)
    outs = [pl.Outcome(p, pl.hint_status(p, notes)) for p in talking.payload_points(case["sid"], real_client)]
    assert {o.point.key: o.addressed for o in gap.uncovered(outs)} == nf.planted_gaps(case)
    assert [o.point.key for o in gap.unresolved(outs)] == list(nf.planted_gaps(case))  # each one blocks a save


@pytest.mark.parametrize("n", IDS)
def test_apptest_panel_lists_planted(n, tmp_path, monkeypatch):
    case = CASES[n]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    planted = nf.planted_gaps(case)
    assert nf.panel(at) == planted
    listed = sorted(str(r.key).rsplit("_", 1)[1] for r in at.radio if str(r.key or "").startswith("vr_gap_mode_typed_"))
    assert listed == sorted(planted)
    assert at.button(key="vr_save").disabled == bool(planted)
    if not planted:
        assert not [w for w in at.warning if w.value.startswith("Not saved yet")]
