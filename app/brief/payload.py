"""payload.py (v0.2-d, PR 8; re-rooted on Visit__c in v0.2-f): a FAKE Salesforce-shaped visit record, built and
validated locally, never sent.

The owner's rule, AS-0057 (sf payload is a database record, not a send): "No actual send. Just create the payload and
place it into a database record." This module only builds a dict and checks it against a JSON Schema. It has no
Salesforce client and imports no HTTP or socket library (T-0049 (no egress) and T-0079 (dry-run no egress) guard that).

Shape lb-sf-tree-0.3, AS-0070 (sf payload lb-sf-tree-0.3, Visit__c root), D-0045 (Salesforce dry run): one sObject Tree
(Composite Tree) request body per root type, kept side by side, each sent as its own tree request in a real build:
  trees.Visit__c = {"records": [Visit__c (the Event fields, Account by external id on the system id, the rep)
                                + nested Talking_Point_Outcomes__r master-detail child records]}
  trees.Event    = {"records": [one Event, WhatId = VISIT_REF]}
  trees.Task     = {"records": [one Task per non-empty follow-up, WhatId = VISIT_REF]} (omitted when there are none)
VISIT_REF "@{visit.id}" is a placeholder for the Id the Visit__c request returns; separate tree requests can't
reference each other, so a real integration fills it in (F-0033).
Every __c and __r name (Visit__c, Talking_Point_Outcome__c, Talking_Point_Outcomes__r, Account__r and every custom
field) is still a proposal and has not been checked against any org (AS-0070).
Rows saved before v0.2-f keep lb-sf-tree-0.2 (Event root, AS-0049 (sf payload field names)); `validate` checks each
payload against the schema of its own version and `build_payload_v02` rebuilds the old shape for an old visit file.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import jsonschema

FAKE_MARKER = "FAKE-SYNTHETIC"
SCHEMA_VERSION = "lb-sf-tree-0.3"
LEGACY_VERSION = "lb-sf-tree-0.2"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "visit_payload.schema.json"
SCHEMA_PATHS = {SCHEMA_VERSION: SCHEMA_PATH, LEGACY_VERSION: SCHEMA_PATH.parent / "visit_payload-0.2.schema.json"}
ADDRESSED = ("Raised", "Partially", "Not raised")
RESPONSES = ("Positive", "Neutral", "Negative", "Objection")
DEFAULT_START = "09:00"
DEFAULT_DURATION = 30
CHILD_REL = "Talking_Point_Outcomes__r"
ROOT_OBJECT = "Visit__c"
ACCOUNT_REL = "Account__r"
ACCOUNT_EXT_ID = "LB_System_Id__c"
VISIT_REF = "@{visit.id}"  # placeholder for the Visit__c Id (F-0033); the dry run never resolves it
TREE_ORDER = (ROOT_OBJECT, "Event", "Task")  # request order: the Visit__c tree first
SYSTEM_ID = re.compile(r"^SYNCP\d{6}$")


@dataclass(frozen=True)
class TalkingPoint:
    """The seam with the talking-points provider (PR 6, `payload_points(system_id, ...)`): only these five attributes
    are read, in this order. Duck-typed: any object with key, text, metric_value, bench_state and bench_national
    works; this module never imports the provider."""
    key: str
    text: str
    metric_value: float | str | None = None
    bench_state: float | str | None = None
    bench_national: float | str | None = None


@dataclass
class Outcome:
    """The rep's record for one talking point. The keyword hint pre-fills `addressed`; the rep confirms."""
    point: TalkingPoint
    addressed: str = "Not raised"
    response: str = "Neutral"
    quality: int = 3
    evidence: str = ""
    follow_up: str = ""


STOP = frozenset("""a about above against all also an and any are as at be below between by for from has have in incl
into is it its of on or over per share than that the their this to under vs was were with without system systems state
states national peers peer synthetic ratio index total value values point points season dollars doses
must cover question ask what which next size net in-state dollar file pooled rows top leads nationally move moved
windows two class company against programs planned driving purchasing""".split())  # template words never count
WORD = re.compile(r"[a-z][a-z0-9+\-]*")


def keywords(point: TalkingPoint) -> set:
    """Content words of the point text (casefolded, 3+ letters, stop words dropped). Digits never count."""
    return {w for w in WORD.findall(point.text.casefold()) if len(w) >= 3 and w not in STOP}


def mentioned_hint(point: TalkingPoint, transcript: str) -> bool:
    """Deterministic pre-fill: True when any content word of the point appears as a whole word in the notes.
    Only a hint for the 'Addressed' control; the rep confirms or changes it."""
    words = set(WORD.findall((transcript or "").casefold()))
    return bool(keywords(point) & words)


def rep_key(rep: str) -> str:
    """AS-0048 (visit key, exact lookup): casefold, trim, collapse whitespace."""
    return " ".join((rep or "").split()).casefold()


def visit_key(rep: str, visit_date: str, system_id: str) -> str:
    r, d, s = rep_key(rep), str(visit_date), str(system_id).strip().upper()
    if not r:
        raise ValueError("rep is required")
    date.fromisoformat(d)  # raises on a non-ISO date
    if not SYSTEM_ID.match(s):
        raise ValueError(f"company must be a system id like SYNCP000025, got {system_id!r}")
    return f"{r}|{d}|{s}"


def _val(v):
    """A metric or benchmark value as JSON: a finite number stays a number, None (and NaN/inf, bool) becomes null,
    anything else is its text. The provider's floats and the fallback's display strings both pass the schema."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    try:  # numpy scalars and similar
        import numbers
        if isinstance(v, numbers.Real):
            fv = float(v)
            return fv if math.isfinite(fv) else None
    except (TypeError, ValueError):
        pass
    return str(v)


def _outcome_record(i: int, o: Outcome) -> dict:
    p = o.point
    return {"attributes": {"type": "Talking_Point_Outcome__c", "referenceId": f"tp{i}"},
            "Talking_Point_Key__c": p.key, "Point_Text__c": p.text, "Metric_Value__c": _val(p.metric_value),
            "Benchmark_State__c": _val(p.bench_state), "Benchmark_National__c": _val(p.bench_national),
            "Addressed__c": o.addressed, "Customer_Response__c": o.response, "Quality_Score__c": int(o.quality),
            "Evidence_Quote__c": o.evidence or "", "Follow_Up__c": o.follow_up or ""}


def _common(rep, visit_date, system_id, system_name, notes, start_time):
    key = visit_key(rep, visit_date, system_id)
    sid = key.rsplit("|", 1)[1]
    hh, mm = (int(x) for x in str(start_time).split(":"))
    return {"key": key, "sid": sid, "rep_key": key.split("|", 1)[0],
            "subject": f"Vaccine rep visit – {system_name or sid}", "start": f"{visit_date}T{hh:02d}:{mm:02d}:00Z",
            "description": f"{FAKE_MARKER} demo record, synthetic data, never sent. Visit notes: {notes or ''}"}


def _tasks(outcomes, visit_date, key, what_key, what) -> list:
    return [{"attributes": {"type": "Task", "referenceId": f"followup{i}"},
             "Subject": f"Follow-up: {o.point.key}", "ActivityDate": str(visit_date), "Status": "Not Started",
             "Priority": "Normal", "Description": f"{FAKE_MARKER} follow-up from a demo visit: {o.follow_up}",
             what_key: what() if callable(what) else what, "LB_Visit_Key__c": key, "LB_Synthetic__c": True}
            for i, o in enumerate(outcomes or [], 1) if (o.follow_up or "").strip()]


def _envelope(version: str, key: str, trees: dict, as_ref: str) -> dict:
    return {"lb_marker": FAKE_MARKER, "lb_schema_version": version, "lb_visit_key": key,
            "lb_note": "Synthetic demo payload stored as a database record. Nothing is sent to Salesforce. "
                       f"Field names are proposals ({as_ref}).",
            "trees": trees}


def build_payload(*, rep: str, visit_date: str, system_id: str, system_name: str, notes: str,
                  outcomes: list, start_time: str = DEFAULT_START, duration: int = DEFAULT_DURATION) -> dict:
    """The FAKE lb-sf-tree-0.3 payload for one visit. Pure: same inputs give the same dict (no clock, no network)."""
    c = _common(rep, visit_date, system_id, system_name, notes, start_time)
    visit = {"attributes": {"type": ROOT_OBJECT, "referenceId": "visit"},
             "Subject__c": c["subject"],
             "Visit_Date__c": str(visit_date),
             "Start_DateTime__c": c["start"],
             "Duration_Minutes__c": int(duration),
             "Description__c": c["description"],
             ACCOUNT_REL: {"attributes": {"type": "Account"}, ACCOUNT_EXT_ID: c["sid"]},
             "Rep_Name__c": " ".join(rep.split()),
             "LB_Rep_Key__c": c["rep_key"],
             "LB_Visit_Key__c": c["key"],
             "LB_Synthetic__c": True}
    if outcomes:
        visit[CHILD_REL] = {"records": [_outcome_record(i, o) for i, o in enumerate(outcomes, 1)]}
    event = {"attributes": {"type": "Event", "referenceId": "event"},
             "Subject": c["subject"],
             "ActivityDate": str(visit_date),
             "StartDateTime": c["start"],
             "DurationInMinutes": int(duration),
             "Description": c["description"],
             "WhatId": VISIT_REF,
             "LB_Rep_Key__c": c["rep_key"],
             "LB_Visit_Key__c": c["key"],
             "LB_Synthetic__c": True}
    trees = {ROOT_OBJECT: {"records": [visit]}, "Event": {"records": [event]}}
    tasks = _tasks(outcomes, visit_date, c["key"], "WhatId", VISIT_REF)
    if tasks:
        trees["Task"] = {"records": tasks}
    return _envelope(SCHEMA_VERSION, c["key"], trees, "AS-0070")


def build_payload_v02(*, rep: str, visit_date: str, system_id: str, system_name: str, notes: str,
                      outcomes: list, start_time: str = DEFAULT_START, duration: int = DEFAULT_DURATION) -> dict:
    """The legacy lb-sf-tree-0.2 shape (Event root, AS-0049), kept only to check a visit file saved before v0.2-f.
    New saves always use build_payload (0.3)."""
    c = _common(rep, visit_date, system_id, system_name, notes, start_time)
    account = {"attributes": {"type": "Account"}, ACCOUNT_EXT_ID: c["sid"]}
    event = {"attributes": {"type": "Event", "referenceId": "visit"},
             "Subject": c["subject"],
             "ActivityDate": str(visit_date),
             "StartDateTime": c["start"],
             "DurationInMinutes": int(duration),
             "Description": c["description"],
             "What": account,
             "LB_Rep_Key__c": c["rep_key"],
             "LB_Visit_Key__c": c["key"],
             "LB_Synthetic__c": True}
    if outcomes:
        event[CHILD_REL] = {"records": [_outcome_record(i, o) for i, o in enumerate(outcomes, 1)]}
    trees = {"Event": {"records": [event]}}
    tasks = _tasks(outcomes, visit_date, c["key"], "What", lambda: dict(account))
    if tasks:
        trees["Task"] = {"records": tasks}
    return _envelope(LEGACY_VERSION, c["key"], trees, "AS-0049")


BUILDERS = {SCHEMA_VERSION: build_payload, LEGACY_VERSION: build_payload_v02}


@lru_cache(maxsize=4)
def schema(version: str = SCHEMA_VERSION) -> dict:
    return json.loads(SCHEMA_PATHS[version].read_text())


class InvalidPayload(ValueError):
    pass


def validate(payload: dict) -> None:
    """Raise InvalidPayload unless the payload matches the schema of its own lb_schema_version: 0.3
    (schemas/visit_payload.schema.json) or the legacy 0.2 (schemas/visit_payload-0.2.schema.json). Any other version,
    or none, is invalid."""
    version = payload.get("lb_schema_version") if isinstance(payload, dict) else None
    if version not in SCHEMA_PATHS:
        raise InvalidPayload(f"lb_schema_version: {version!r} is not one of {sorted(SCHEMA_PATHS)}")
    try:
        jsonschema.validate(payload, schema(version), cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as e:
        where = "/".join(str(p) for p in e.absolute_path) or "(root)"
        raise InvalidPayload(f"{where}: {e.message}") from None


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256(payload: dict) -> str:
    return hashlib.sha256(canonical(payload).encode()).hexdigest()


def points_from_client_rows(rows: list, items=("R1", "R2", "R3", "R5", "R6")) -> list:
    """Fallback provider until PR 6 lands: one point per computed client ratio row (PR 5 table_rows), skipping a row
    whose system value is not a number. Plain text from computed values only."""
    out = []
    for r in rows:
        vals = list(r.values())
        metric, sys_v, state_v, nat_v = vals[0], vals[1], vals[2], vals[3]
        item = metric.split()[0]
        if item not in items or not re.match(r"^-?[\d.,$%]+", str(sys_v)):
            continue
        out.append(TalkingPoint(key=item, text=f"{metric}: system {sys_v}; state peers {state_v}; national {nat_v}",
                                metric_value=str(sys_v), bench_state=str(state_v), bench_national=str(nat_v)))
    return out
