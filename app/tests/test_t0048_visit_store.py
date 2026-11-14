"""T-0048 visit store (AS-0048 (visit key, exact lookup), AS-0057 (sf payload is a database record, not a send)):
save writes a payload record; a re-save appends version 2 and never overwrites; lookup is by the exact key only and no
list-all is exposed; Load rejects an invalid file; the backup subcommand copies the rows.
Mutations: store_nopayload, store_overwrite, store_prefix, store_listall, load_lax, backup_empty."""
import json
import sqlite3

import pytest

from brief import payload as pl, visits
from tests import visit_fixture as vf

PUBLIC = {"db_path", "connect", "save_visit", "lookup", "visit_file", "parse_visit_file", "backup", "main",
          "InvalidVisitFile", "BANNER", "LABELS", "NOTES_MAX", "SAVES_PER_SESSION"}


@pytest.fixture
def db(tmp_path):
    return tmp_path / "visits.db"


def _rows(db, sql, args=()):
    c = sqlite3.connect(db)
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


def test_save_writes_payload_row(db):
    res = visits.save_visit(db=db, **vf.visit())
    assert res["visit_key"] == "demo rep|2026-11-18|SYNCP000025" and res["version"] == 1
    rows = _rows(db, "SELECT visit_key, version, schema_version, payload_json, sha256 FROM sf_payloads")
    assert len(rows) == 1
    key, ver, sv, pj, sha = rows[0]
    assert (key, ver, sv) == (res["visit_key"], 1, pl.SCHEMA_VERSION)
    pl.validate(json.loads(pj))
    assert sha == pl.sha256(json.loads(pj)) == res["sha256"]
    assert _rows(db, "SELECT rep_name, rep_key, notes_text FROM visits") == [
        ("Demo Rep", "demo rep", "Talked about MenB with the clinic manager.")]


def test_resave_versions_not_overwrites(db):
    first = visits.save_visit(db=db, **vf.visit())
    second = visits.save_visit(db=db, **vf.visit(notes="Second pass: flu and shingles."))
    assert (first["version"], second["version"]) == (1, 2)
    rows = _rows(db, "SELECT version, sha256, payload_json FROM sf_payloads ORDER BY version")
    assert [r[0] for r in rows] == [1, 2] and rows[0][1] == first["sha256"] and rows[1][1] == second["sha256"]
    assert "Talked about MenB" in rows[0][2] and "Second pass" in rows[1][2]  # version 1 is untouched
    assert _rows(db, "SELECT COUNT(*) FROM visits") == [(1,)]
    c = sqlite3.connect(db)
    with pytest.raises(sqlite3.DatabaseError):  # append-only, enforced in the DB too
        c.execute("UPDATE sf_payloads SET payload_json = '{}' WHERE version = 1")
    with pytest.raises(sqlite3.DatabaseError):
        c.execute("DELETE FROM sf_payloads")
    c.close()
    found = visits.lookup("demo rep", "2026-11-18", "SYNCP000025", db=db)
    assert found["version"] == 2 and [v["version"] for v in found["versions"]] == [1, 2]
    assert found["sha256"] == second["sha256"] and found["visit"]["notes_text"] == "Second pass: flu and shingles."


def test_lookup_exact_key_only(db):
    visits.save_visit(db=db, **vf.visit())
    found = visits.lookup("  DEMO rep ", "2026-11-18", "syncp000025", db=db)  # AS-0048 normalisation is not fuzziness
    assert found and found["payload"]["lb_visit_key"] == "demo rep|2026-11-18|SYNCP000025"
    assert pl.sha256(found["payload"]) == found["sha256"]
    for rep, d, sid in (("demo", "2026-11-18", "SYNCP000025"), ("demo rep x", "2026-11-18", "SYNCP000025"),
                        ("demo%", "2026-11-18", "SYNCP000025"), ("demo rep", "2026-11-17", "SYNCP000025"),
                        ("demo rep", "2026-11-18", "SYNCP000026")):
        assert visits.lookup(rep, d, sid, db=db) is None, (rep, d, sid)
    assert visits.lookup("demo rep", "2026-11-18", "SYNCP000025", db=db.parent / "missing.db") is None
    inj = "x'; DROP TABLE visits; --"
    visits.save_visit(db=db, **vf.visit(rep=inj))  # parameterised SQL: stored literally
    assert visits.lookup(inj, "2026-11-18", "SYNCP000025", db=db)["visit"]["rep_name"] == inj


def test_no_list_all_exposed():
    public = {n for n in vars(visits) if not n.startswith("_") and callable(getattr(visits, n)) and
              getattr(getattr(visits, n), "__module__", "") == visits.__name__}
    public |= {n for n in vars(visits) if n.isupper() and not n.startswith("_")} & PUBLIC
    assert public <= PUBLIC, public - PUBLIC
    assert set(visits.__all__) == PUBLIC
    for name in vars(visits):
        assert not any(w in name.lower() for w in ("list", "all_visits", "search", "enumerate", "dump")), name
    src = (visits.__file__ and open(visits.__file__).read())
    selects = [ln for ln in src.splitlines() if "SELECT" in ln and "FROM" in ln and "RAISE" not in ln]
    assert selects and all("WHERE visit_key = ?" in ln for ln in selects), selects


def test_load_rejects_invalid_file(db):
    visits.save_visit(db=db, **vf.visit())
    good = visits.visit_file(visits.lookup("demo rep", "2026-11-18", "SYNCP000025", db=db))
    loaded = visits.parse_visit_file(good)
    assert loaded["visit_key"] == "demo rep|2026-11-18|SYNCP000025" and len(loaded["outcomes"]) == 2
    doc = json.loads(good)
    bad = {"not json": b"{nope", "wrong kind": json.dumps({"hello": 1}).encode()}
    d = json.loads(good); d["payload"]["trees"]["Event"]["records"][0].pop("ActivityDate"); bad["payload schema"] = d
    d = json.loads(good); d["visit"]["notes"] = "edited after the payload was built"; bad["mismatch"] = d
    d = json.loads(good); d["lb_marker"] = "REAL"; bad["marker"] = d
    d = json.loads(good); d["visit"]["outcomes"][0]["quality"] = 9; bad["outcome"] = d
    for why, b in bad.items():
        with pytest.raises(visits.InvalidVisitFile):
            visits.parse_visit_file(b if isinstance(b, bytes) else json.dumps(b).encode())
    assert doc["lb_marker"] == "FAKE-SYNTHETIC"


def test_backup_subcommand(db, tmp_path, capsys):
    visits.save_visit(db=db, **vf.visit())
    visits.save_visit(db=db, **vf.visit())
    dest = tmp_path / "bk" / "backup-1.db"
    assert visits.main(["backup", str(dest), "--db", str(db)]) == 0
    assert "backup written" in capsys.readouterr().out
    assert _rows(dest, "SELECT version FROM sf_payloads ORDER BY version") == [(1,), (2,)]
    assert (dest.stat().st_mode & 0o777) == 0o600


def test_notes_cap(db):
    with pytest.raises(ValueError):
        visits.save_visit(db=db, **vf.visit(notes="x" * (visits.NOTES_MAX + 1)))
    assert not db.exists() or _rows(db, "SELECT COUNT(*) FROM sf_payloads") == [(0,)]
