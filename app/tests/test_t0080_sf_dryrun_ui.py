"""T-0080 Salesforce dry-run UI (AppTest; D-0045 (Salesforce dry run)): the 'Integration (dry run)' tab is last, shows
the DRY RUN banner and a display-only auth method, has no password-type input (nor does any app source), saves a
non-secret setup and refuses a token-shaped one; the Visit record tab shows 'Preview Salesforce request' after a save and
after a lookup, with the banner, the one Composite request's POST URL and headers, the body (allOrNone, the
stored records as subrequests), the curl text and the request-set
download, following the latest setup; no label anywhere says Send. Mutation: send_label (a Send label added)."""
import datetime
import json
import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from brief import payload as pl, sf_config as sc, sf_preview as sp, visits

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")
D = datetime.date(2026, 11, 18)
SEND = re.compile(r"\bsend\b", re.I)
JWT = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJkZW1vIiwic3ViIjoiZGVtbyJ9.c2lnbmF0dXJlLWZha2UtZm9yLXRlc3Rz"


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("LB_VISITS_DB", str(tmp_path / "ui.db"))
    at = AppTest.from_file(APP, default_timeout=240).run()
    assert not at.exception
    at.selectbox(key="system").set_value("SYNCP000025").run()
    assert not at.exception
    return at


def _labels(at) -> list:
    """Every label the user can read on a control or heading."""
    out = [b.label for b in at.button] + [b.proto.label for b in at.get("download_button")]
    out += [w.label for kind in ("text_input", "text_area", "selectbox", "date_input", "time_input", "number_input",
                                 "checkbox") for w in getattr(at, kind)]
    out += [u.proto.label for u in at.get("file_uploader")] + [t.label for t in at.tabs]
    out += [h.value for h in at.subheader] + [h.value for h in at.header]
    return out


def _submit(at):
    return next(b for b in at.button if b.label == sc.LABELS["save"])


def test_integration_tab_form_and_no_password(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    assert [t.label for t in at.tabs][-1] == "Integration (dry run)"
    assert any(w.value == sp.BANNER for w in at.warning)
    assert any(sc.AUTH_METHOD_DISPLAY in m.value for m in at.markdown)  # display only: no input for it
    assert at.text_input(key="ig_instance_url_0").value == "https://example.my.salesforce.com"
    assert at.text_input(key="ig_api_version_0").value == sc.DEFAULT_API_VERSION
    assert all(t.proto.type == t.proto.DEFAULT for t in at.text_input), [t.label for t in at.text_input]
    for f in [ROOT / "app.py", *sorted((ROOT / "brief").glob("*.py"))]:  # no password input in any app source
        assert not re.search(r"type\s*=\s*['\"]password['\"]", f.read_text()), f.name
    at.text_input(key="ig_instance_url_0").set_value("https://example-dev.my.salesforce.com")
    at.text_input(key="ig_record_type_id_0").set_value(JWT)
    _submit(at).click().run()
    assert any("looks like a token" in e.value for e in at.error), [e.value for e in at.error]
    assert sc.latest_config(tmp_path / "ui.db")["id"] is None
    at.text_input(key="ig_record_type_id_0").set_value("012000000000000AAA")
    _submit(at).click().run()
    assert not at.exception and any(s.value.startswith("Saved setup") for s in at.success)
    latest = sc.latest_config(tmp_path / "ui.db")
    assert latest["id"] == 1 and latest["config"]["instance_url"] == "https://example-dev.my.salesforce.com"
    at.run()
    assert at.text_input(key="ig_instance_url_1").value == "https://example-dev.my.salesforce.com"


def test_preview_after_save_and_lookup_and_no_send(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.text_input(key="vr_rep").input("Demo  Rep").run()
    at.date_input(key="vr_date").set_value(D).run()
    at.text_area(key="vr_notes").input("We talked about HPV uptake.").run()
    at.button(key="vr_save").click().run()
    assert not at.exception
    stored = visits.lookup("demo rep", "2026-11-18", "SYNCP000025", db=tmp_path / "ui.db")
    assert [h.value for h in at.subheader].count(sp.LABELS["panel"]) == 1
    assert sum(w.value == sp.BANNER for w in at.warning) >= 2  # the preview panel and the Integration tab
    codes = [c.value for c in at.code]
    url = "POST https://example.my.salesforce.com/services/data/v62.0/composite"
    assert sum(c == url + "\nAuthorization: Bearer <NOT CONFIGURED>\nContent-Type: application/json"
               for c in codes) == 1  # one Composite request (D-0046)
    bodies = [json.loads(c) for c in codes if c.startswith('{\n  "allOrNone"')]
    assert len(bodies) == 1 and bodies[0]["allOrNone"] is True
    subs = bodies[0]["compositeRequest"]
    visit = stored["payload"]["trees"]["Visit__c"]["records"][0]
    assert subs[0]["referenceId"] == "visit"
    assert subs[0]["body"] == {k: v for k, v in visit.items() if k not in ("attributes", pl.CHILD_REL)}  # stored
    assert sp.stored_trees(bodies[0], sc.DEFAULTS) == stored["payload"]["trees"]
    assert any(c.startswith("curl -X POST 'https://example.my.salesforce.com/") for c in codes)
    dl = [b for b in at.get("download_button") if b.proto.label == sp.LABELS["download"]]
    assert dl, "request-set download missing"

    sc.save_config({"instance_url": "https://example-dev.my.salesforce.com"}, db=tmp_path / "ui.db")
    at.text_input(key="vr_l_rep").input("demo rep").run()
    at.date_input(key="vr_l_date").set_value(D).run()
    at.button(key="vr_lookup").click().run()
    assert not at.exception
    assert [h.value for h in at.subheader].count(sp.LABELS["panel"]) == 2  # after the save and after the lookup
    codes = [c.value for c in at.code]
    assert any(c.startswith("POST https://example-dev.my.salesforce.com/services/data/v62.0/composite\n")
               for c in codes)  # the latest setup
    shown = next(json.loads(c) for c in codes if '"lb_marker"' in c)
    assert pl.sha256(shown) == stored["sha256"]
    labels = _labels(at)
    assert sp.LABELS["download"] in labels and sc.LABELS["save"] in labels and "Integration (dry run)" in labels
    assert not [lb for lb in labels if SEND.search(lb)], [lb for lb in labels if SEND.search(lb)]
    assert not [v for v in list(sp.LABELS.values()) + list(sc.LABELS.values()) if SEND.search(v)]
