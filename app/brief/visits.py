"""visits.py (v0.2-d, PR 8): the visit store. Stdlib sqlite3, parameterised SQL only, no network.

The owner: "all sessions saved to a database" (12:20 PT 11/13) and "No actual send. Just create the payload and place it
into a database record." (2:26 PT 11/13), AS-0057 (sf payload is a database record, not a send).
- `visits`: one row per visit key (AS-0048 (visit key, exact lookup)): rep + visit date + company (system id).
- `sf_payloads`: one row per save, version 1, 2, 3...; a re-save adds a row and never overwrites (triggers refuse
  UPDATE and DELETE).
- Lookup is by the exact key only. There is deliberately no list-all or search function (AS-0058 (open visit store,
  no passcode)): the store is open to anyone with the app URL, so it must not be enumerable from the UI.
v0.2-g (D-0047, AS-0074): a save is refused (ValueError) while any talking point is unresolved (brief/gap.py); each
outcome stores reason_code, reason_text and addendum; old rows default them on read.
v0.2-h1 (D-0048, AS-0080 (provenance is app-side)): an outcome may carry `auto` ({"evidence": src, "follow_up": src},
src one of auto-rule, edited, none) in outcomes_json and in the visit file only, never in the payload; older rows read
it as absent. Visit files are lb-visit-file-0.4; 0.2 and 0.3 files still load.
Path: LB_VISITS_DB, default <repo>/data/visits.db (AS-0050 (visits DB path), gitignored).
CLI: python -m brief.visits backup DEST [--db PATH]  (online copy via the sqlite3 backup API)
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import gap, payload as pl
from .config import PROJECT

DEFAULT_DB = PROJECT / "data" / "visits.db"
NOTES_MAX = 8000          # AS-0058 (open visit store, no passcode) mitigation: notes capped
SAVES_PER_SESSION = 30    # AS-0058 (open visit store, no passcode) mitigation: the UI caps saves per browser session
FILE_SCHEMA_PATH = pl.SCHEMA_PATH.parent / "visit_file.schema.json"
FILE_VERSION = "lb-visit-file-0.4"  # v0.2-h1: outcomes may carry `auto` (AS-0080); 0.3 added the reasons (AS-0074)
FILE_VERSIONS = ("lb-visit-file-0.2", "lb-visit-file-0.3", FILE_VERSION)
OUTCOME_DEFAULTS = {"reason_code": None, "reason_text": None, "addendum": False}  # a row or file saved before v0.2-g
AUTO_FIELDS = ("evidence", "follow_up")  # v0.2-h1 provenance keys (AS-0080); no default: older rows read it as absent
BANNER = ("Demo: synthetic data only. No patient information (no PHI). There is no Salesforce connection: saving "
          "creates a FAKE payload record in this app's own database. Anyone with this app's address can save a "
          "visit or look one up by its exact rep, date and company.")
LABELS = {"save": "Save visit & create payload record", "lookup": "Look up visit", "download": "Download visit (.json)",
          "load": "Load visit file", "save_loaded": "Save loaded visit & create payload record"}
__all__ = ["db_path", "connect", "save_visit", "lookup", "visit_file", "parse_visit_file", "backup", "main",
           "InvalidVisitFile", "BANNER", "LABELS", "NOTES_MAX", "SAVES_PER_SESSION"]

DDL = """
CREATE TABLE IF NOT EXISTS visits (
  visit_key   TEXT PRIMARY KEY,
  rep_name    TEXT NOT NULL,
  rep_key     TEXT NOT NULL,
  visit_date  TEXT NOT NULL CHECK (visit_date GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]'),
  system_id   TEXT NOT NULL CHECK (system_id GLOB 'SYNCP[0-9][0-9][0-9][0-9][0-9][0-9]'),
  system_name TEXT NOT NULL,
  notes_text  TEXT NOT NULL,
  outcomes_json TEXT NOT NULL,
  start_time  TEXT NOT NULL,
  duration    INTEGER NOT NULL,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  synthetic   INTEGER NOT NULL DEFAULT 1 CHECK (synthetic = 1),
  UNIQUE (rep_key, visit_date, system_id)
);
CREATE TABLE IF NOT EXISTS sf_payloads (
  id             INTEGER PRIMARY KEY,
  visit_key      TEXT NOT NULL REFERENCES visits(visit_key),
  version        INTEGER NOT NULL CHECK (version >= 1),
  created_at     TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  payload_json   TEXT NOT NULL,
  sha256         TEXT NOT NULL,
  UNIQUE (visit_key, version)
);
CREATE TRIGGER IF NOT EXISTS sf_payloads_no_update BEFORE UPDATE ON sf_payloads
  BEGIN SELECT RAISE(ABORT, 'sf_payloads rows are append-only'); END;
CREATE TRIGGER IF NOT EXISTS sf_payloads_no_delete BEFORE DELETE ON sf_payloads
  BEGIN SELECT RAISE(ABORT, 'sf_payloads rows are append-only'); END;
"""


class InvalidVisitFile(ValueError):
    pass


def db_path(path=None) -> Path:
    return Path(path or os.environ.get("LB_VISITS_DB") or DEFAULT_DB)


def connect(path=None) -> sqlite3.Connection:
    p = db_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(DDL)
    conn.execute("PRAGMA user_version = 1")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _outcome_item(o) -> dict:
    item = {"key": o.point.key, "text": o.point.text, "metric_value": pl._val(o.point.metric_value),
            "bench_state": pl._val(o.point.bench_state), "bench_national": pl._val(o.point.bench_national),
            "addressed": o.addressed, "response": o.response, "quality": int(o.quality),
            "evidence": o.evidence, "follow_up": o.follow_up, "reason_code": o.reason_code,
            "reason_text": o.reason_text, "addendum": bool(o.addendum)}
    if getattr(o, "auto", None) is not None:  # v0.2-h1 (AS-0080): app-side provenance, only when the UI recorded it
        item["auto"] = {f: o.auto[f] for f in AUTO_FIELDS}
    return item


def _outcomes_json(outcomes) -> str:
    return json.dumps([_outcome_item(o) for o in outcomes], ensure_ascii=False)


def _with_defaults(items) -> list:
    return [{**OUTCOME_DEFAULTS, **i} for i in items]


def _outcomes_from(items) -> list:
    return [pl.Outcome(pl.TalkingPoint(i["key"], i["text"], i["metric_value"], i["bench_state"], i["bench_national"]),
                       i["addressed"], i["response"], int(i["quality"]), i["evidence"], i["follow_up"],
                       i["reason_code"], i["reason_text"], bool(i["addendum"]), i.get("auto"))
            for i in _with_defaults(items)]


def _next_version(conn, key: str) -> int:
    row = conn.execute("SELECT MAX(version) FROM sf_payloads WHERE visit_key = ?", (key,)).fetchone()
    return (row[0] or 0) + 1


def _write_payload(conn, key: str, payload: dict, now: str) -> int:
    """Append the payload as version n+1. Never UPDATE or DELETE (the triggers would refuse)."""
    version = _next_version(conn, key)
    conn.execute("INSERT INTO sf_payloads (visit_key, version, created_at, schema_version, payload_json, sha256) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (key, version, now, payload["lb_schema_version"], pl.canonical(payload),
                                               pl.sha256(payload)))
    return version


def save_visit(*, rep: str, visit_date: str, system_id: str, system_name: str, notes: str, outcomes: list,
               start_time: str = pl.DEFAULT_START, duration: int = pl.DEFAULT_DURATION, db=None) -> dict:
    """Build + validate the FAKE payload, upsert the visit row, append a payload record. Returns key, version, sha256.
    Refuses (ValueError) while any talking point is unresolved (D-0047): the UI gate is not the only gate."""
    notes = notes or ""
    if len(notes) > NOTES_MAX:
        raise ValueError(f"notes are limited to {NOTES_MAX} characters")
    if gap.unresolved(outcomes):
        raise ValueError(f"{len(gap.unresolved(outcomes))} talking points need a reason or an addendum: "
                         f"{gap.describe(outcomes)}")
    payload = pl.build_payload(rep=rep, visit_date=visit_date, system_id=system_id, system_name=system_name,
                               notes=notes, outcomes=outcomes, start_time=start_time, duration=duration)
    pl.validate(payload)
    key = payload["lb_visit_key"]
    rk, d, sid = key.split("|")
    now = _now()
    conn = connect(db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO visits (visit_key, rep_name, rep_key, visit_date, system_id, system_name, notes_text, "
                "outcomes_json, start_time, duration, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(visit_key) DO UPDATE SET rep_name = excluded.rep_name, system_name = excluded.system_name, "
                "notes_text = excluded.notes_text, outcomes_json = excluded.outcomes_json, "
                "start_time = excluded.start_time, duration = excluded.duration, updated_at = excluded.updated_at",
                (key, " ".join(rep.split()), rk, d, sid, system_name or sid, notes, _outcomes_json(outcomes),
                 start_time, int(duration), now, now))
            version = _write_payload(conn, key, payload, now)
    finally:
        conn.close()
    return {"visit_key": key, "version": version, "sha256": pl.sha256(payload), "payload": payload}


def lookup(rep: str, visit_date: str, system_id: str, db=None) -> dict | None:
    """Exact key only (AS-0048): the normalised rep, the ISO date and the system id must all match. Returns the visit,
    its latest payload record and the version history, or None."""
    key = pl.visit_key(rep, visit_date, system_id)
    if not db_path(db).exists():
        return None
    conn = connect(db)
    try:
        v = conn.execute("SELECT * FROM visits WHERE visit_key = ?", (key,)).fetchone()
        if v is None:
            return None
        vers = conn.execute("SELECT version, created_at, sha256 FROM sf_payloads WHERE visit_key = ? ORDER BY version",
                            (key,)).fetchall()
        last = conn.execute("SELECT * FROM sf_payloads WHERE visit_key = ? ORDER BY version DESC LIMIT 1",
                            (key,)).fetchone()
    finally:
        conn.close()
    visit = dict(v)
    visit["outcomes"] = _with_defaults(json.loads(visit.pop("outcomes_json")))  # rows before v0.2-g lack the reasons
    return {"visit_key": key, "visit": visit, "version": last["version"] if last else 0,
            "payload": json.loads(last["payload_json"]) if last else None, "sha256": last["sha256"] if last else None,
            "versions": [dict(r) for r in vers]}


def visit_file(found: dict) -> bytes:
    """The 'Download visit (.json)' body for a looked-up visit."""
    v = found["visit"]
    doc = {"lb_visit_file": FILE_VERSION, "lb_marker": pl.FAKE_MARKER,
           "visit": {"rep": v["rep_name"], "visit_date": v["visit_date"], "system_id": v["system_id"],
                     "system_name": v["system_name"], "notes": v["notes_text"], "start_time": v["start_time"],
                     "duration": v["duration"], "outcomes": v["outcomes"]},
           "payload": found["payload"], "version": found["version"], "payload_sha256": found["sha256"]}
    return json.dumps(doc, indent=2, ensure_ascii=False).encode()


def parse_visit_file(data: bytes) -> dict:
    """'Load visit file': JSON, the visit-file schema (lb-visit-file-0.4, or 0.3 or 0.2), the payload schema of the payload's
    own version (0.4; 0.3, or 0.2 for a file saved before v0.2-f), and the payload must match the visit (rebuilt from
    the file's own fields in that same version). Anything else raises InvalidVisitFile. Saving a loaded visit always
    writes a new 0.4 payload, through the same unresolved-point gate (D-0047)."""
    import jsonschema
    try:
        doc = json.loads(data)
    except (ValueError, UnicodeDecodeError) as e:
        raise InvalidVisitFile(f"not JSON: {e}") from None
    try:
        jsonschema.validate(doc, json.loads(FILE_SCHEMA_PATH.read_text()), cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as e:
        raise InvalidVisitFile(f"visit file: {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}") from None
    try:
        pl.validate(doc["payload"])
    except pl.InvalidPayload as e:
        raise InvalidVisitFile(f"payload: {e}") from None
    v = doc["visit"]
    build = pl.BUILDERS[doc["payload"]["lb_schema_version"]]  # an older file is checked against its own shape
    try:
        rebuilt = build(rep=v["rep"], visit_date=v["visit_date"], system_id=v["system_id"],
                                   system_name=v["system_name"], notes=v["notes"], outcomes=_outcomes_from(v["outcomes"]),
                                   start_time=v["start_time"], duration=v["duration"])
    except ValueError as e:
        raise InvalidVisitFile(f"visit: {e}") from None
    if pl.canonical(rebuilt) != pl.canonical(doc["payload"]):
        raise InvalidVisitFile("payload does not match the visit fields")
    return {"visit": v, "outcomes": _outcomes_from(v["outcomes"]), "payload": doc["payload"],
            "visit_key": rebuilt["lb_visit_key"]}


def backup(dest, db=None) -> Path:
    """Online, consistent copy with sqlite3's backup API."""
    src = db_path(db)
    if not src.exists():
        raise FileNotFoundError(src)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    s, d = sqlite3.connect(str(src)), sqlite3.connect(str(dest))
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()
    os.chmod(dest, 0o600)
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m brief.visits", description="Little Blue visit store tools")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup", help="online copy of the visits DB (sqlite3 backup API)")
    b.add_argument("dest")
    b.add_argument("--db", default=None, help="source DB (default: LB_VISITS_DB or data/visits.db)")
    a = ap.parse_args(argv)
    if a.cmd == "backup":
        out = backup(a.dest, a.db)
        print(f"backup written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
