"""Post-hoc checks over an output dir. Each returns a list of violations (empty = pass)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import caps
from .generate import SPLITS, answer_has_digit, parse_doc_md

LEAK_MIN = 20  # min chars for a family-B static fragment to count as "template text"


def load_qa(out, split):
    p = Path(out) / split / "qa.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def load_docs(out, split):
    d = {}
    for p in sorted((Path(out) / split / "docs").glob("*.md")):
        d[p.stem] = parse_doc_md(p.read_text())
    return d


def spans_verbatim(out) -> list:
    bad = []
    for sp in SPLITS:
        docs = load_docs(out, sp)
        for q in load_qa(out, sp):
            for slot, ref in (q.get("spans") or {}).items():
                did, anchor = ref["anchor"].split("#", 1)
                sec = docs.get(did, ({}, {}))[1].get(anchor)
                if sec is None or ref["text"] not in sec["text"]:
                    bad.append(f"{q['qa_id']} {slot} {ref['text']!r} not in {ref['anchor']}")
            if "span" in q:
                bad.append(f"{q['qa_id']} carries a non-canonical single `span` field (G-04)")
            for ref in (q.get("spans") or {}).values():
                if ref["anchor"].split("#", 1)[0].split("-")[1] != q["system_id"]:
                    bad.append(f"{q['qa_id']} anchor {ref['anchor']} from another system")
            if q["answer_type"] != "unanswerable":
                if not q.get("spans") or q.get("source_anchor") != q["spans"]["S1"]["anchor"]:
                    bad.append(f"{q['qa_id']} source_anchor != spans.S1.anchor")
        for p in sorted((Path(out) / sp / "docs").glob("*.terms.json")):
            ts = json.loads(p.read_text())
            for name, f in ts["fields"].items():
                sec = docs[f["source"]["doc_id"]][1].get(f["source"]["anchor"])
                if sec is None or f["span"] not in sec["text"]:
                    bad.append(f"{p.name} {name} span not verbatim")
    return bad


def answers_digit_free(out) -> list:
    return [f"{q['qa_id']}: {q['answer']!r}" for sp in SPLITS for q in load_qa(out, sp) if answer_has_digit(q["answer"])]


def systems_disjoint(out) -> list:
    out = Path(out)
    seen = {}
    m = json.loads((out / "manifest.json").read_text())
    for sp in SPLITS:
        s = set(m["split"][sp]["systems"])
        s |= {q["system_id"] for q in load_qa(out, sp)}
        s |= {meta["system_id"] for meta, _ in load_docs(out, sp).values()}
        s |= {p.stem.split("-")[2] for p in (out / sp / "leaves").glob("*.md")}
        seen[sp] = s
    both = sorted(seen["train"] & seen["test"])
    return [f"system {x} in train and test" for x in both]


def families_by_split(out) -> list:
    bad = []
    for sp, fam in (("train", "A"), ("test", "B")):
        for q in load_qa(out, sp):
            if q["family"] != fam:
                bad.append(f"{q['qa_id']} family {q['family']} in {sp}")
        for did, (meta, _) in load_docs(out, sp).items():
            if meta["family"] != fam:
                bad.append(f"{did} family {meta['family']} in {sp}")
    return bad


LEAK_NGRAM = 4  # words


def _ngrams(text: str, n: int = LEAK_NGRAM) -> set:
    w = text.split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def b_ngrams(spec) -> list:
    """Word 4-grams (>= 12 chars) of family-B static template text."""
    grams = set()
    for f in spec.template_text("B"):
        grams |= _ngrams(f)
    return sorted(g for g in grams if len(g) >= 12)


def template_overlap(spec) -> list:
    """Families must be disjoint: no B 4-gram may occur in A template text."""
    a_text = " ".join(" ".join(f.split()) for f in spec.template_text("A"))
    return [f"B 4-gram {g!r} also in family-A templates" for g in b_ngrams(spec) if g in a_text]


def family_b_leak(out, spec) -> list:
    """No family-B template text in any train file: B-only word 4-grams, whole B fragments (>= LEAK_MIN chars),
    and B-only heading text (>= 6 chars) in train headings."""
    a_frags = {f.strip() for f in spec.template_text("A")}
    frags = sorted({f.strip() for f in spec.template_text("B") if len(f.strip()) >= LEAK_MIN})
    bad = template_overlap(spec)
    corpus = []
    for p in sorted((Path(out) / "train").rglob("*")):
        if p.is_file():
            corpus.append((str(p), " ".join(p.read_text().split())))
    for f in frags + b_ngrams(spec):
        g = " ".join(f.split())
        for name, text in corpus:
            if g in text:
                bad.append(f"B text {g!r} in {name}")
                break
    b_short = sorted({f.strip() for f in spec.template_text("B") if len(f.strip()) >= 6}
                     - {x for x in (f.strip() for f in spec.template_text("B")) if any(x in a for a in a_frags)})
    for did, (_m, secs) in load_docs(out, "train").items():
        for a, s in secs.items():
            for f in b_short:
                if f in s["heading"]:
                    bad.append(f"B heading text {f!r} in train {did}#{a}")
    return bad


def caps_ok(out) -> tuple:
    """Returns (violations, max_section_bytes, max_leaf_bytes)."""
    bad, ms, ml = [], 0, 0
    for sp in SPLITS:
        for did, (_meta, secs) in load_docs(out, sp).items():
            for a, s in secs.items():
                n = caps.nbytes(s["text"])
                ms = max(ms, n)
                if n > caps.SECTION_MAX:
                    bad.append(f"{did}#{a} section {n} > {caps.SECTION_MAX}")
        for p in (Path(out) / sp / "leaves").glob("*.md"):
            n = p.stat().st_size
            ml = max(ml, n)
            if n > caps.CAP:
                bad.append(f"{p.name} leaf {n} > {caps.CAP}")
    return bad, ms, ml


def unanswerable_rate(out) -> dict:
    r = {}
    for sp in SPLITS:
        qa = load_qa(out, sp)
        r[sp] = sum(q["answer_type"] == "unanswerable" for q in qa) / max(1, len(qa))
    return r


def manifest_ok(out) -> list:
    out = Path(out)
    m = json.loads((out / "manifest.json").read_text())
    bad = []
    on_disk = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()} - {"manifest.json", "manifest.sha256"}
    if on_disk != set(m["files"]):
        bad.append(f"file set mismatch: extra={sorted(on_disk - set(m['files']))[:3]} missing={sorted(set(m['files']) - on_disk)[:3]}")
    for rel, h in m["files"].items():
        p = out / rel
        if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() != h:
            bad.append(f"sha mismatch {rel}")
    mh = hashlib.sha256((out / "manifest.json").read_bytes()).hexdigest()
    if (out / "manifest.sha256").read_text().split()[0] != mh:
        bad.append("manifest.sha256 mismatch")
    return bad


def synthetic_stamp(out) -> list:
    bad = []
    for sp in SPLITS:
        for p in sorted((Path(out) / sp / "docs").glob("*.md")):
            t = p.read_text()
            meta, _ = parse_doc_md(t)
            if meta.get("synthetic") is not True or "SYNTHETIC" not in t.split("## ", 1)[0] or not re.match(r"SYN-SYNCP\d{6}-", p.stem):
                bad.append(p.name)
        for p in sorted((Path(out) / sp / "leaves").glob("*.md")):
            if '\nsynthetic: true\n' not in p.read_text():
                bad.append(p.name)
    return bad
