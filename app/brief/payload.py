"""payload.py (v0.2-d, PR 8): a FAKE Salesforce-shaped visit record, built and validated locally, never sent.

The owner's rule, AS-0057 (sf payload is a database record, not a send): "No actual send. Just create the payload and
place it into a database record." This module only builds a dict and checks it against a JSON Schema. It has no
Salesforce client and imports no HTTP or socket library (T-0049 (no egress) guards that).

Shape, AS-0049 (sf payload field names): an sObject Tree (Composite Tree) request body per root type, kept side by side:
  trees.Event = {"records": [Event + nested Talking_Point_Outcomes__r child records]}
  trees.Task  = {"records": [one Task per non-empty follow-up]} (omitted when there are none)
Every field ending in __c is a proposal and has not been checked against any org.
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
SCHEMA_VERSION = "lb-sf-tree-0.2"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "visit_payload.schema.json"
ADDRESSED = ("Raised", "Partially", "Not raised")
RESPONSES = ("Positive", "Neutral", "Negative", "Objection")
DEFAULT_START = "09:00"
DEFAULT_DURATION = 30
CHILD_REL = "Talking_Point_Outcomes__r"
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


def build_payload(*, rep: str, visit_date: str, system_id: str, system_name: str, notes: str,
                  outcomes: list, start_time: str = DEFAULT_START, duration: int = DEFAULT_DURATION) -> dict:
    """The FAKE payload for one visit. Pure: same inputs give the same dict (no clock, no network)."""
    key = visit_key(rep, visit_date, system_id)
    sid = key.rsplit("|", 1)[1]
    hh, mm = (int(x) for x in str(start_time).split(":"))
    account = {"attributes": {"type": "Account"}, "LB_System_Id__c": sid}
    event = {"attributes": {"type": "Event", "referenceId": "visit"},
             "Subject": f"Vaccine rep visit – {system_name or sid}",
             "ActivityDate": str(visit_date),
             "StartDateTime": f"{visit_date}T{hh:02d}:{mm:02d}:00Z",
             "DurationInMinutes": int(duration),
             "Description": f"{FAKE_MARKER} demo record, synthetic data, never sent. Visit notes: {notes or ''}",
             "What": account,
             "LB_Rep_Key__c": key.split("|", 1)[0],
             "LB_Visit_Key__c": key,
             "LB_Synthetic__c": True}
    if outcomes:
        event[CHILD_REL] = {"records": [_outcome_record(i, o) for i, o in enumerate(outcomes, 1)]}
    trees = {"Event": {"records": [event]}}
    tasks = [{"attributes": {"type": "Task", "referenceId": f"followup{i}"},
              "Subject": f"Follow-up: {o.point.key}", "ActivityDate": str(visit_date), "Status": "Not Started",
              "Priority": "Normal", "Description": f"{FAKE_MARKER} follow-up from a demo visit: {o.follow_up}",
              "What": dict(account), "LB_Visit_Key__c": key, "LB_Synthetic__c": True}
             for i, o in enumerate(outcomes or [], 1) if (o.follow_up or "").strip()]
    if tasks:
        trees["Task"] = {"records": tasks}
    return {"lb_marker": FAKE_MARKER, "lb_schema_version": SCHEMA_VERSION, "lb_visit_key": key,
            "lb_note": "Synthetic demo payload stored as a database record. Nothing is sent to Salesforce. "
                       "Field names are proposals (AS-0049).",
            "trees": trees}


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


class InvalidPayload(ValueError):
    pass


def validate(payload: dict) -> None:
    """Raise InvalidPayload unless the payload matches schemas/visit_payload.schema.json."""
    try:
        jsonschema.validate(payload, schema(), cls=jsonschema.Draft202012Validator)
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
