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
VISIT_REF "@{visit.id}" references the Id the Visit__c subrequest creates. The stored shape is unchanged in 6c: the
preview maps these trees to ONE Composite request (allOrNone), where the reference resolves (D-0046, AS-0072; F-0033
closed).
Every __c and __r name (Visit__c, Talking_Point_Outcome__c, Talking_Point_Outcomes__r, Account__r and every custom
field) is still a proposal and has not been checked against any org (AS-0070).
Rows saved before v0.2-f keep lb-sf-tree-0.2 (Event root, AS-0049 (sf payload field names)); `validate` checks each
payload against the schema of its own version and `build_payload_v02` rebuilds the old shape for an old visit file.

v0.2-g, D-0047 (missed talking-point follow-up), AS-0074 (lb-sf-tree-0.4): new saves are lb-sf-tree-0.4, the 0.3 shape
plus three fields on each outcome child: Not_Addressed_Reason__c (one of REASON_CODES, or null),
Not_Addressed_Reason_Text__c (at most 280 characters, or null) and Addendum__c. The 0.4 schema requires a reason on
every outcome that is not Raised and refuses one on a Raised outcome. `build_payload_v03` is the 0.3 builder, frozen
(byte-identical output), kept to check a visit file saved as 0.3; stored 0.2 and 0.3 rows are never rewritten.
AS-0073 (three-state hint): `hint_status` pre-fills Raised, Partially or Not raised (sentence window + template cues, and
template anchors for the size point); `mentioned_hint` is `hint_status(...) != "Not raised"`.
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
SCHEMA_VERSION = "lb-sf-tree-0.4"  # v0.2-g (AS-0074); 0.3 and 0.2 rows keep their own version
V03_VERSION = "lb-sf-tree-0.3"
LEGACY_VERSION = "lb-sf-tree-0.2"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "visit_payload.schema.json"  # the 0.3 file, byte-frozen
SCHEMA_PATHS = {SCHEMA_VERSION: SCHEMA_PATH.parent / "visit_payload-0.4.schema.json", V03_VERSION: SCHEMA_PATH,
                LEGACY_VERSION: SCHEMA_PATH.parent / "visit_payload-0.2.schema.json"}
ADDRESSED = ("Raised", "Partially", "Not raised")
RANK = {"Not raised": 0, "Partially": 1, "Raised": 2}  # an addendum only ever moves a point up (D-0047)
REASON_CODES = ("NOT_RELEVANT", "OUT_OF_TIME", "CONTACT_DECLINED", "COVERED_PREVIOUSLY", "OTHER")  # AS-0075
REASON_TEXT_MAX = 280
RESPONSES = ("Positive", "Neutral", "Negative", "Objection")
DEFAULT_START = "09:00"
DEFAULT_DURATION = 30
CHILD_REL = "Talking_Point_Outcomes__r"
ROOT_OBJECT = "Visit__c"
ACCOUNT_REL = "Account__r"
ACCOUNT_EXT_ID = "LB_System_Id__c"
VISIT_REF = "@{visit.id}"  # the Visit__c subrequest's Id in the one Composite request (D-0046); never sent
TREE_ORDER = (ROOT_OBJECT, "Event", "Task")  # subrequest order: the Visit__c (then its outcomes) first
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
    """The rep's record for one talking point. The keyword hint pre-fills `addressed`; the rep confirms.
    v0.2-g: a point that is not Raised carries a reason (reason_code, plus reason_text for OTHER); addendum is True
    when the point went through at least one 'Address now' round (D-0047). The new fields default, so the positional
    constructors keep working. v0.2-h1: `auto` is {"evidence": src, "follow_up": src} with src auto-rule, edited or
    none (AS-0080 (provenance is app-side)); it is stored in visits.outcomes_json and the visit file only."""
    point: TalkingPoint
    addressed: str = "Not raised"
    response: str = "Neutral"
    quality: int = 3
    evidence: str = ""
    follow_up: str = ""
    reason_code: str | None = None
    reason_text: str | None = None
    addendum: bool = False
    auto: dict | None = None  # v0.2-h1 (AS-0080): app-side provenance only; never read by any payload builder


STOP = frozenset("""a about above against all also an and any are as at be below between by for from has have in incl
into is it its of on or over per share than that the their this to under vs was were with without system systems state
states national peers peer synthetic ratio index total value values point points season dollars doses
must cover question ask what which next size net in-state dollar file pooled rows top leads nationally move moved
windows two class company against programs planned driving purchasing""".split())  # template words never count
WORD = re.compile(r"[a-z][a-z0-9+\-]*")


def keywords(point: TalkingPoint) -> set:
    """Content words of the point text (casefolded, 3+ letters, stop words dropped). Digits never count."""
    return {w for w in WORD.findall(point.text.casefold()) if len(w) >= 3 and w not in STOP}


# AS-0073 (three-state hint). FUNC: the function words of STOP (its first run, "a" .. "without"); every other STOP word
# is a template cue. C = the point's own cue words; a cue next to the point's name makes it Raised.
FUNC = frozenset("""a about above against all also an and any are as at be below between by for from has have in incl
into is it its of on or over per share than that the their this to under vs was were with without""".split())
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
# The size point (talking._size_text) is all STOP words, so it is matched on its literal template phrases (F-0035).
ANCHORS = ("net dollars", "in-state total", "national dollars", "in-state comparison")


def cues(point: TalkingPoint) -> set:
    """C: the point's own template cue words (in STOP but not a function word)."""
    return {w for w in WORD.findall(point.text.casefold()) if w in STOP and w not in FUNC}


# AS-0077 (evidence quote rule, v0.2-h1): extra cue words used ONLY to rank the evidence sentence (brief/autofill.py).
# `share` stays a FUNC word above, so it never reaches `cues` or `hint_status`: AS-0073's status rule holds (T-0089).
RANK_CUES_EXTRA = frozenset({"share"})


def _has_phrase(phrase: str, text: str) -> bool:
    return re.search(r"(?<![a-z0-9+\-])" + re.escape(phrase) + r"(?![a-z0-9+\-])", text) is not None


# AS-0086 (hint fixes, bug 1): a sentence (clause) that says the point was NOT discussed never counts for it, and a
# ratio point ("X to Y doses") is Raised only when a sentence names both sides; the numerator alone is at most
# Partially, and the denominator alone (often shared between ratios) does not count.
NOT_DISCUSSED = re.compile(
    r"\b(?:did\s*n[o']t|didn't|never|could\s*n[o']t|couldn't|was\s*n[o']t|wasn't|were\s*n[o']t|weren't|not)\s+"
    r"(?:get\s+to|got\s+to|getting\s+to|discuss\w*|raise\w*|cover\w*|mention\w*|go\s+through|went\s+through|reach\w*|"
    r"talk\w*\s+about|come\s+up|came\s+up|touch\w*\s+on|address\w*|bring\s+up|brought\s+up)\b"
    r"|\bran\s+out\s+of\s+time\s+before\b|\bno\s+time\s+(?:for|to)\b|\bskipp(?:ed|ing)\b", re.I)
RATIO = re.compile(r"^must cover:\s*(.+?)\s+to\s+(.+?)\s+doses\s+is\b", re.I)


CLAUSE = re.compile(r";|,?\s+\bbut\b|,?\s+\bthough\b|,?\s+\balthough\b|,?\s+\bwhile\b", re.I)


def not_discussed(sentence: str) -> bool:
    """True for a sentence (or clause) that says something was not discussed ("we did not get to rotavirus", "ran out
    of time before the RSV point", "skipped the shingles ratio")."""
    return NOT_DISCUSSED.search(sentence) is not None


def discussed_part(sentence: str) -> str:
    """The sentence without its "not discussed" clauses: "I mentioned MenB briefly, but we ran out of time before going
    through it" keeps "I mentioned MenB briefly"."""
    return " ".join(c for c in CLAUSE.split(sentence) if not not_discussed(c))


def ratio_sides(point: TalkingPoint):
    """(K of the numerator, K of the denominator) for an "X to Y doses" ratio point, else None."""
    m = RATIO.match(point.text.strip())
    if not m:
        return None
    side = lambda s: {w for w in WORD.findall(s.casefold()) if len(w) >= 3 and w not in STOP}  # noqa: E731
    return side(m.group(1)), side(m.group(2))


def hint_status(point: TalkingPoint, text: str) -> str:
    """Deterministic pre-fill, one of ADDRESSED (AS-0073, AS-0086). With content words K: a sentence holding 2+
    distinct K words, or 1 K word and one of the point's cue words, gives Raised; K words only alone in their sentences
    give Partially; no K word gives Not raised. A ratio point needs K words of both sides in one sentence for Raised.
    A sentence that says the point was not discussed is ignored. With no K (the size point): 2+ of its template
    anchors in the notes give Raised, 1 gives Partially, 0 gives Not raised. Only a hint; the rep confirms or changes
    it."""
    t = (text or "").casefold()
    k = keywords(point)
    if not k:
        t = " ".join(discussed_part(s) for s in SENTENCE.split(t))
        anchors = [a for a in ANCHORS if _has_phrase(a, point.text.casefold())]
        n = sum(_has_phrase(a, t) for a in anchors)
        return ADDRESSED[0] if n >= 2 else ADDRESSED[1] if n == 1 else ADDRESSED[2]
    c, hit, sides = cues(point), False, ratio_sides(point)
    for s in SENTENCE.split(t):
        words = set(WORD.findall(discussed_part(s)))
        found = k & words
        if not found:
            continue
        if sides is not None and not found & sides[0]:
            continue  # the denominator alone (shared, e.g. adult-labelled Influenza) does not name this ratio
        hit = True
        if sides is not None and not found & sides[1]:
            continue  # the numerator alone is at most Partially
        if len(found) >= 2 or c & words:
            return ADDRESSED[0]
    return ADDRESSED[1] if hit else ADDRESSED[2]


def mentioned_hint(point: TalkingPoint, transcript: str) -> bool:
    """True unless hint_status says Not raised (kept for T-0047 and older callers)."""
    return hint_status(point, transcript) != ADDRESSED[2]


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


def build_payload_v03(*, rep: str, visit_date: str, system_id: str, system_name: str, notes: str,
                      outcomes: list, start_time: str = DEFAULT_START, duration: int = DEFAULT_DURATION) -> dict:
    """The FAKE lb-sf-tree-0.3 payload for one visit, FROZEN in v0.2-g (byte-identical output; T-0087 pins it). Only
    used to check a visit file saved as 0.3. Pure: same inputs give the same dict (no clock, no network)."""
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
    return _envelope(V03_VERSION, c["key"], trees, "AS-0070")


def _reason_fields(o: Outcome) -> dict:
    return {"Not_Addressed_Reason__c": getattr(o, "reason_code", None),
            "Not_Addressed_Reason_Text__c": getattr(o, "reason_text", None),
            "Addendum__c": bool(getattr(o, "addendum", False))}


def build_payload(*, rep: str, visit_date: str, system_id: str, system_name: str, notes: str,
                  outcomes: list, start_time: str = DEFAULT_START, duration: int = DEFAULT_DURATION) -> dict:
    """The FAKE lb-sf-tree-0.4 payload (AS-0074): the 0.3 tree, plus the reason and addendum fields on each outcome
    child. Pure: same inputs give the same dict (no clock, no network)."""
    p = build_payload_v03(rep=rep, visit_date=visit_date, system_id=system_id, system_name=system_name, notes=notes,
                          outcomes=outcomes, start_time=start_time, duration=duration)
    p["lb_schema_version"] = SCHEMA_VERSION
    p["lb_note"] = p["lb_note"].replace("(AS-0070)", "(AS-0070, AS-0074)")
    kids = p["trees"][ROOT_OBJECT]["records"][0].get(CHILD_REL, {"records": []})["records"]
    for rec, o in zip(kids, outcomes or []):
        rec.update(_reason_fields(o))
    return p


def build_payload_v02(*, rep: str, visit_date: str, system_id: str, system_name: str, notes: str,
                      outcomes: list, start_time: str = DEFAULT_START, duration: int = DEFAULT_DURATION) -> dict:
    """The legacy lb-sf-tree-0.2 shape (Event root, AS-0049), kept only to check a visit file saved before v0.2-f.
    New saves always use build_payload (0.4)."""
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


BUILDERS = {SCHEMA_VERSION: build_payload, V03_VERSION: build_payload_v03, LEGACY_VERSION: build_payload_v02}


@lru_cache(maxsize=8)
def schema(version: str = SCHEMA_VERSION) -> dict:
    return json.loads(SCHEMA_PATHS[version].read_text())


class InvalidPayload(ValueError):
    pass


def validate(payload: dict) -> None:
    """Raise InvalidPayload unless the payload matches the schema of its own lb_schema_version: 0.4
    (schemas/visit_payload-0.4.schema.json), 0.3 (schemas/visit_payload.schema.json) or the legacy 0.2
    (schemas/visit_payload-0.2.schema.json). Any other version, or none, is invalid."""
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
