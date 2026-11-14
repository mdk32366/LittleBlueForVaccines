"""T-0061 Visit record lookup follows the sidebar system (AppTest, F-0025). Render the tab with system A, switch the
sidebar to system B, then run the lookup WITHOUT touching its Company picker: it must find B's visit (and the picker
must show B). Switching back to A must find A's visit. Both visits share the rep and the date, so a stale company is
caught by the visit key, not only by "nothing found".
Mutation: lookup_fixed_key (the Company picker gets the old fixed key "vr_l_sid" back, so it sticks to A)."""
import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

from brief import visits
from tests import visit_fixture

APP = str(Path(__file__).resolve().parents[1] / "app.py")
D = datetime.date(2026, 11, 18)
A, B = "SYNCP000001", "SYNCP000025"


def _lookup(at):
    """Fill rep and date only; the Company picker is never set by the test."""
    at.text_input(key="vr_l_rep").input("demo rep").run()
    at.date_input(key="vr_l_date").set_value(D).run()
    at.button(key="vr_lookup").click().run()
    assert not at.exception, [e.value for e in at.exception]
    return [s.value for s in at.success if s.value.startswith("Visit ")]


def test_lookup_company_follows_sidebar(tmp_path, monkeypatch):
    db = tmp_path / "t0061.db"
    for sid, name in ((A, "System A"), (B, "Sunrise Care Partners 025")):
        visits.save_visit(**visit_fixture.visit(system_id=sid, system_name=name), db=db)
    monkeypatch.setenv("LB_VISITS_DB", str(db))
    at = AppTest.from_file(APP, default_timeout=240).run()
    assert not at.exception
    at.selectbox(key="system").set_value(A).run()  # first render of the Visit record tab: system A
    assert not at.exception
    pickers = [s for s in at.selectbox if s.label == "Company"]
    assert len(pickers) == 1 and pickers[0].value == A, [(s.key, s.value) for s in pickers]

    at.selectbox(key="system").set_value(B).run()  # the sidebar moves to system B
    assert not at.exception
    shown = _lookup(at)
    assert shown and f"demo rep|2026-11-18|{B}" in shown[-1] and "version 1 of 1" in shown[-1], shown
    pickers = [s for s in at.selectbox if s.label == "Company"]
    assert len(pickers) == 1 and pickers[0].value == B, [(s.key, s.value) for s in pickers]

    at.selectbox(key="system").set_value(A).run()  # and back to A
    assert not at.exception
    shown = _lookup(at)
    assert shown and f"demo rep|2026-11-18|{A}" in shown[-1], shown
