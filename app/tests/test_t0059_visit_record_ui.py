"""T-0059 Visit record tab (AppTest): the synthetic/no-PHI/no-Salesforce banner; no action labelled 'Send'; save then
look up by the exact key round-trips with the same payload sha256; a near-miss key finds nothing.
Mutations: ui_lookup (lookup finds nothing), ui_banner (banner text blank), ui_send (save button says Send)."""
import datetime
import json
import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from brief import payload as pl, visits

APP = str(Path(__file__).resolve().parents[1] / "app.py")
D = datetime.date(2026, 11, 18)


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("LB_VISITS_DB", str(tmp_path / "ui.db"))
    at = AppTest.from_file(APP, default_timeout=240).run()
    assert not at.exception
    at.selectbox(key="system").set_value("SYNCP000025").run()
    assert not at.exception
    return at


def test_banner_and_no_send_action(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    info = " ".join(i.value for i in at.info)
    for phrase in ("synthetic data", "no PHI", "no Salesforce connection", "FAKE payload record"):
        assert phrase in info, phrase
    labels = [b.label for b in at.button] + [b.proto.label for b in at.get("download_button")]
    assert visits.LABELS["save"] in labels and visits.LABELS["lookup"] in labels
    assert not [l for l in labels if re.search(r"\bsend\b", l, re.I)], labels
    assert any(t.label == "Visit record" for t in at.tabs)


def test_save_then_lookup_round_trip(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.text_input(key="vr_rep").input("Demo  Rep").run()
    at.date_input(key="vr_date").set_value(D).run()
    at.text_area(key="vr_notes").input("We talked about HPV uptake with the clinic manager.").run()
    at.button(key="vr_save").click().run()
    assert not at.exception
    saved = [s.value for s in at.success if s.value.startswith("Saved visit")]
    assert saved and "demo rep|2026-11-18|SYNCP000025" in saved[0] and "version 1" in saved[0]
    stored = visits.lookup("demo rep", "2026-11-18", "SYNCP000025", db=tmp_path / "ui.db")
    assert stored and stored["version"] == 1
    outs = {o["key"]: o for o in stored["visit"]["outcomes"]}  # the talking-points provider's points (v0.2-b)
    assert {"fixed.A1", "must.R2", "question.F2"} <= set(outs)
    assert outs["must.R2"]["addressed"] == "Raised"  # keyword hint pre-filled from the notes ("HPV")
    assert outs["fixed.A1"]["addressed"] == "Not raised"
    kids = {k["Talking_Point_Key__c"]: k for k in
            stored["payload"]["trees"]["Event"]["records"][0]["Talking_Point_Outcomes__r"]["records"]}
    assert isinstance(kids["must.R2"]["Metric_Value__c"], float)  # numbers stay numbers
    assert kids["question.F2"]["Metric_Value__c"] is None  # None is JSON null

    at.text_input(key="vr_l_rep").input("demo rep").run()
    at.date_input(key="vr_l_date").set_value(D).run()
    at.selectbox(key="vr_l_sid_SYNCP000025").set_value("SYNCP000025").run()
    at.button(key="vr_lookup").click().run()
    assert not at.exception
    assert any("version 1 of 1" in s.value for s in at.success)
    shown = json.loads(at.code[-1].value)
    assert shown["lb_marker"] == "FAKE-SYNTHETIC" and pl.sha256(shown) == stored["sha256"]
    assert any(b.proto.label == visits.LABELS["download"] for b in at.get("download_button"))

    at.text_input(key="vr_l_rep").input("demo").run()  # a prefix is not a key
    at.button(key="vr_lookup").click().run()
    assert any("No visit for that exact rep, date and company" in i.value for i in at.info)
