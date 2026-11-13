"""Drop-in conformance for a candidate ContractSpec (the schema_v1 seam). Read-only: plans, renders and builds TermSets
in memory for a seeded fixture; writes nothing. The generator still runs its own fail-closed validation at generation.

check_spec(spec) -> (errors, warnings). Errors block the GATE 2 regeneration; warnings go to the Architect.
- Seam: implements ContractSpec, has a spec_version, renders families A and B, doc_types inside the ONTOLOGY vocab
  and include MSA, catalog rows complete with Field types inside FIELD_TYPES.
- App contract: the catalog keeps the field names the app reads (APP_REQUIRED); renaming one is a spec change routed
  through the Architect, never a silent remap.
- AS-0041 (schema_v1 keeps auto_renew boolean in term section): every planned MSA has an expiration_date (ISO date) and
  an auto_renew whose value is a bool, citing the same doc and anchor as expiration_date, span verbatim there.
"""
from __future__ import annotations

import datetime as dt
import random

from ..seam import DOC_TYPES, FIELD_TYPES, ContractSpec
from ..systems import fixture_systems

APP_REQUIRED = ("effective_date", "expiration_date", "auto_renew")  # app/brief/contracts.py + AS-0041
APP_QA_FIELDS = ("renewal_notice_days", "termination_for_convenience", "termination_notice_days", "admin_fee_pct",
                 "share_floor_pct", "exclusivity_class", "commitment_doses_per_year", "tier_rebate_pct",
                 "tier_min_doses")  # app/brief/contracts.py KEYWORDS; a missing one loses a Q&A route (warning)
CATALOG_KEYS = ("name", "type", "unit", "clause_type", "qualifiers", "cardinality")


def _base(key: str) -> str:
    head, _, tail = key.rpartition("-")
    return head if head and tail.isdigit() else key


def check_seam(spec) -> list:
    errs = []
    if not isinstance(spec, ContractSpec):
        return [f"{type(spec).__name__} does not implement ContractSpec"]
    if not isinstance(getattr(spec, "spec_version", None), str) or not spec.spec_version:
        errs.append("spec_version missing or not a string")
    for fam in ("A", "B"):
        if fam not in spec.families:
            errs.append(f"family {fam} missing (train = A, test = B)")
    dts = tuple(spec.doc_types())
    if "MSA" not in dts:
        errs.append("doc_types() lacks MSA")
    errs += [f"doc_type {d} not in the ONTOLOGY vocab {DOC_TYPES}" for d in dts if d not in DOC_TYPES]
    for row in spec.field_catalog():
        miss = [k for k in CATALOG_KEYS if k not in row]
        if miss:
            errs.append(f"catalog row {row.get('name')!r} lacks {miss}")
        elif row["type"] not in FIELD_TYPES:
            errs.append(f"catalog field {row['name']} type {row['type']!r} not in {FIELD_TYPES}")
    return errs


def check_app_fields(spec) -> tuple:
    names = {r.get("name") for r in spec.field_catalog()}
    errs = [f"catalog lacks {n} (the app reads it; renaming is a spec change via the Architect)"
            for n in APP_REQUIRED if n not in names]
    warns = [f"catalog lacks {n} (app Q&A keyword route goes dark)" for n in APP_QA_FIELDS if n not in names]
    return errs, warns


def check_auto_renew(doc_id: str, fields: dict, sections: dict) -> list:
    """AS-0041 on one MSA TermSet. fields: name -> Field; sections: anchor -> text."""
    e, a = fields.get("expiration_date"), fields.get("auto_renew")
    if e is None:
        return [f"{doc_id}: MSA has no expiration_date"]
    errs = []
    try:
        dt.date.fromisoformat(str(e.value))
    except ValueError:
        errs.append(f"{doc_id}: expiration_date {e.value!r} is not an ISO date")
    if a is None:
        return errs + [f"{doc_id}: MSA has no auto_renew (AS-0041)"]
    if not isinstance(a.value, bool):
        errs.append(f"{doc_id}: auto_renew is {type(a.value).__name__}, not bool (AS-0041)")
    if (a.source.doc_id, a.source.anchor) != (e.source.doc_id, e.source.anchor):
        errs.append(f"{doc_id}: auto_renew cites {a.source.doc_id}#{a.source.anchor}, not the expiration_date section "
                    f"{e.source.doc_id}#{e.source.anchor} (AS-0041)")
    elif a.span not in sections.get(a.source.anchor, ""):
        errs.append(f"{doc_id}: auto_renew span not verbatim in its section (AS-0041)")
    return errs


def check_plans(spec, n_systems: int = 12, seed: int = 562) -> tuple:
    """Plan/render/terms for a seeded fixture in both families. Returns (errors, stats)."""
    errs, stats = [], {"msas": 0, "auto_renew_true": 0}
    for fam in ("A", "B"):
        for sysp in fixture_systems(n_systems):
            rng = random.Random(f"{seed}|{spec.spec_version}|{sysp.system_id}|conformance")
            for ds in spec.plan(sysp, rng, fam):
                if ds.doc_type != "MSA":
                    continue
                doc, ts = spec.render(ds), spec.terms(ds)
                fields = {_base(k): f for k, f in ts.fields.items()} if ts else {}
                errs += check_auto_renew(ds.doc_id, fields, {s.anchor: s.text for s in doc.sections})
                stats["msas"] += 1
                stats["auto_renew_true"] += bool(getattr(fields.get("auto_renew"), "value", False) is True)
    if stats["msas"] == 0:
        errs.append("the fixture plan produced no MSA")
    return errs, stats


def check_spec(spec, n_systems: int = 12) -> tuple:
    errs = check_seam(spec)
    if errs and "does not implement ContractSpec" in errs[0]:
        return errs, []
    e2, warns = check_app_fields(spec)
    errs += e2
    e3, stats = check_plans(spec, n_systems)
    errs += e3
    if stats["msas"] and stats["auto_renew_true"] in (0, stats["msas"]):
        warns.append(f"auto_renew is {bool(stats['auto_renew_true'])} on all {stats['msas']} fixture MSAs; "
                     "the T-0039 split would be one-sided")
    return errs, warns
