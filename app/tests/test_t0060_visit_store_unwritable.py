"""T-0060 Visit record tab with an unwritable visit store (AppTest): when LB_VISITS_DB can't be opened or written
(AS-0050 (visits DB path)), both save paths show a clear 'Not saved' error, raise nothing, record no save, and the rest
of the tab (lookup, Load visit file) still renders; a lookup shows a clear 'Lookup failed' message.
Two unwritable paths, both refused even when running as root: a DB path under a parent that is a regular file
(OSError from the parent mkdir), and a DB path that is an existing directory (sqlite3.Error on open).
Mutations: ro_save (the Save visit catch is removed), ro_save_loaded (the Save loaded visit catch is removed),
ro_store_errors (no store error is caught anywhere in the tab)."""
import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

from brief import visits
from tests import visit_fixture

APP = str(Path(__file__).resolve().parents[1] / "app.py")
D = datetime.date(2026, 11, 18)


def _file_parent(tmp_path) -> Path:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("a regular file, so nothing can be created under it")
    return blocker / "data" / "visits.db"


def _dir_as_db(tmp_path) -> Path:
    d = tmp_path / "visits.db"
    d.mkdir()
    return d


def _app(monkeypatch, db: Path):
    monkeypatch.setenv("LB_VISITS_DB", str(db))
    at = AppTest.from_file(APP, default_timeout=240).run()
    assert not at.exception
    at.selectbox(key="system").set_value("SYNCP000025").run()
    assert not at.exception
    return at


def _not_saved(at) -> list:
    return [e.value for e in at.error if e.value.startswith("Not saved: the visit store isn't writable")]


def _rest_of_tab_rendered(at):
    assert at.text_input(key="vr_l_rep") is not None and at.button(key="vr_lookup") is not None
    assert any(f.label == visits.LABELS["load"] for f in at.file_uploader)


def test_typed_save_not_writable(tmp_path, monkeypatch):
    for db, kind in ((_file_parent(tmp_path), "NotADirectoryError"), (_dir_as_db(tmp_path), "OperationalError")):
        at = _app(monkeypatch, db)
        at.text_input(key="vr_rep").input("Demo Rep").run()
        at.date_input(key="vr_date").set_value(D).run()
        at.button(key="vr_save").click().run()
        assert not at.exception, [e.value for e in at.exception]
        msgs = _not_saved(at)
        assert len(msgs) == 1 and "nothing was sent" in msgs[0], [e.value for e in at.error]
        assert f"({kind})" in msgs[0], msgs
        assert not [s.value for s in at.success if s.value.startswith("Saved")]
        assert "vr_saves" not in at.session_state  # no save was counted
        _rest_of_tab_rendered(at)
        assert not db.is_file()


def test_loaded_save_not_writable(tmp_path, monkeypatch):
    good = tmp_path / "good.db"
    visits.save_visit(**visit_fixture.visit(), db=good)
    body = visits.visit_file(visits.lookup("demo rep", "2026-11-18", "SYNCP000025", db=good))
    at = _app(monkeypatch, _file_parent(tmp_path))
    at.file_uploader(key="vr_upload").set_value(("visit.json", body, "application/json")).run()
    assert not at.exception
    assert any(s.value.startswith("Valid visit file") for s in at.success)
    at.button(key="vr_save_loaded").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(_not_saved(at)) == 1, [e.value for e in at.error]
    assert not [s.value for s in at.success if s.value.startswith("Saved loaded visit")]
    _rest_of_tab_rendered(at)


def test_lookup_store_unreadable(tmp_path, monkeypatch):
    at = _app(monkeypatch, _dir_as_db(tmp_path))
    at.text_input(key="vr_l_rep").input("demo rep").run()
    at.date_input(key="vr_l_date").set_value(D).run()
    at.button(key="vr_lookup").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any(e.value.startswith("Lookup failed: the visit store can't be read") for e in at.error), \
        [e.value for e in at.error]
    _rest_of_tab_rendered(at)
