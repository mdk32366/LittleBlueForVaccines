"""contracts.py: read-only view of gen/out (never written). LLM off: answers are TermSet lookups only, each with its
cited span, anchor (<doc_id>#<section>) and clause text. Lookups are pre-filtered to one system (system isolation)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from . import config

REFUSAL = "not in the contracts"  # D-0027 (refusal string)
EXPIRED_MARKER = "[EXPIRED]"  # shown when a contract's end date is before the as-of date
AUTO_RENEW_MARKER = "[TERM ENDED · auto-renews]"  # expired, but auto_renew is True in the same term section
SEC_RE = re.compile(r"^## (\d+(?:\.\d+)*[a-z]?)\. (.+)$", re.M)

KEYWORDS = [  # (pattern, field base) for free-text questions; order matters
    (r"\b(expire|expiry|expiration|lapse|end date|term end)", "expiration_date"),
    (r"\b(effective|commence|start|begin)", "effective_date"),
    (r"\b(auto[- ]?renew|renew automatically|roll ?over)", "auto_renew"),
    (r"\brenewal notice|notice .*renew|non-extension", "renewal_notice_days"),
    (r"\bterminat\w* .*convenience|without cause|walk away", "termination_for_convenience"),
    (r"\bterminat\w* .*notice|notice .*terminat", "termination_notice_days"),
    (r"\b(admin\w* fee|service charge)", "admin_fee_pct"),
    (r"\bshare floor|minimum share|preferred.position minimum", "share_floor_pct"),
    (r"\bexclusiv", "exclusivity_class"),
    (r"\bcommit|minimum take", "commitment_doses_per_year"),
    (r"\b(rebate|percent|%)", "tier_rebate_pct"),
    (r"\b(tier|band|threshold|doses)", "tier_min_doses"),
]


def parse_doc(text: str):
    fm = text.split("---\n", 2)[1]
    meta = {ln.split(": ", 1)[0]: json.loads(ln.split(": ", 1)[1]) for ln in fm.strip().split("\n")}
    ms = list(SEC_RE.finditer(text))
    secs = {}
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        secs[m.group(1)] = {"heading": m.group(2), "text": text[m.end():end].strip("\n")}
    return meta, secs


def gen_out() -> Path:
    return Path(config.GEN_OUT)


@lru_cache(maxsize=None)
def _all_doc_paths(root: str):
    return tuple(sorted(Path(root).glob("*/docs/SYN-*.md")))


def system_docs(system_id: str) -> dict:
    """doc_id -> (meta, sections) for ONE system only."""
    out = {}
    for p in _all_doc_paths(str(gen_out())):
        if f"-{system_id}-" not in p.name:
            continue
        meta, secs = parse_doc(p.read_text())
        if meta["system_id"] != system_id:
            continue
        out[meta["doc_id"]] = (meta, secs, p)
    return out


def system_terms(system_id: str) -> list:
    """[(doc_id, field_key, field)] for one system's TermSets."""
    rows = []
    for did, (_m, _s, p) in sorted(system_docs(system_id).items()):
        tp = p.with_name(did + ".terms.json")
        if tp.exists():
            for k, f in sorted(json.loads(tp.read_text())["fields"].items()):
                rows.append((did, k, f))
    return rows


def system_questions(system_id: str) -> list:
    qs = []
    for split in ("train", "test"):
        p = gen_out() / split / "qa.jsonl"
        if p.exists():
            for line in p.read_text().splitlines():
                if f'"system_id": "{system_id}"' in line:
                    qs.append(json.loads(line))
    return qs


def _base(key: str) -> str:
    return re.sub(r"-\d+$", "", key)


def is_expired(field_key: str, value, as_of: str | None = None) -> bool:
    """True when field_key is a contract end date (expiration_date) that falls before the as-of date."""
    return _base(field_key) == "expiration_date" and str(value) < (as_of or config.AS_OF_DATE)


def same_section(a_source: dict, b_source: dict) -> bool:
    """Two TermSet field sources cite the same section (same doc_id and anchor)."""
    return a_source["doc_id"] == b_source["doc_id"] and a_source["anchor"] == b_source["anchor"]


def term_ended_auto_renews(exp_field: dict, auto_fields: list, docs: dict) -> bool:
    """AS-0040 (expired rule), field-based: the TermSet auto_renew field is True, cites the same section as the
    expiration_date field, and its span is verbatim in that section. No phrase matching."""
    for f in auto_fields:
        if f.get("value") is True and same_section(f["source"], exp_field["source"]):
            sec = docs.get(f["source"]["doc_id"], (None, {}))[1].get(f["source"]["anchor"])
            if sec and f["span"] in sec["text"]:
                return True
    return False


def field_marker(field_key: str, field: dict, auto_fields: list, docs: dict) -> str:
    """'' for live fields; AUTO_RENEW_MARKER or EXPIRED_MARKER for an expiration_date before the as-of date."""
    if not is_expired(field_key, field["value"]):
        return ""
    return AUTO_RENEW_MARKER if term_ended_auto_renews(field, auto_fields, docs) else EXPIRED_MARKER


def system_markers(system_id: str) -> dict:
    """(doc_id, field_key) -> marker for one system's TermSet fields (the Q&A tab's status column)."""
    docs, terms = system_docs(system_id), system_terms(system_id)
    autos = [f for _d, k, f in terms if _base(k) == "auto_renew"]
    return {(d, k): field_marker(k, f, autos, docs) for d, k, f in terms}


def lookup(system_id: str, field_key: str | None = None, base: str | None = None, tier: int | None = None) -> list:
    """Cited answers: [{doc_id, field, value, span, anchor, heading, clause_text, verbatim}]."""
    docs = system_docs(system_id)
    terms = system_terms(system_id)
    autos = [f for _d, k, f in terms if _base(k) == "auto_renew"]
    out = []
    for did, k, f in terms:
        if field_key and k != field_key:
            continue
        if base and _base(k) != base:
            continue
        if tier and (f.get("qualifier") or {}).get("tier") != tier:
            continue
        sdoc, anc = f["source"]["doc_id"], f["source"]["anchor"]
        sec = docs[sdoc][1][anc]
        out.append({"doc_id": did, "field": k, "value": f["value"], "span": f["span"], "anchor": f"{sdoc}#{anc}",
                    "heading": sec["heading"], "clause_text": sec["text"], "verbatim": f["span"] in sec["text"],
                    "expired": is_expired(k, f["value"]), "marker": field_marker(k, f, autos, docs)})
    return out


def answer(system_id: str, question: str) -> dict:
    """Free-text or example question -> TermSet lookup. Unknown -> REFUSAL."""
    q = question.lower()
    known = {x["question"].lower(): x for x in system_questions(system_id)}
    if q in known:
        row = known[q]
        if row.get("field_name"):
            hits = [h for h in lookup(system_id, field_key=row["field_name"]) if h["doc_id"] == row["doc_id"]]
            if hits:
                return {"answer": hits[0]["span"], "citations": hits, "note": "TermSet lookup"}
        note = ("unanswerable" if row["answer_type"] == "unanswerable"
                else "needs retrieval over clause text; LLM off, TermSet lookup only")
        return {"answer": REFUSAL, "citations": [], "note": note}
    tier = re.search(r"\b(?:tier|band)\s*(\d)", q)
    for pat, base in KEYWORDS:
        if re.search(pat, q):
            hits = lookup(system_id, base=base, tier=int(tier.group(1)) if tier and base.startswith("tier_") else None)
            if hits:
                return {"answer": "; ".join(h["span"] for h in hits), "citations": hits, "note": "keyword TermSet lookup"}
    return {"answer": REFUSAL, "citations": [], "note": "no TermSet field matched"}
