"""Spec-agnostic generator: depends only on seam.ContractSpec. Emits docs, TermSet sidecars, qa.jsonl, leaves, manifest."""
from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
from pathlib import Path

from . import GENERATOR_VERSION, caps, leaves, vault_guard
from .ontology import CONTRACT_DOC_ID, PROPOSAL_DOC_ID, SYSTEM_ID, slug
from .seam import ANSWER_TYPES, FIELD_TYPES, REFUSAL, to_jsonable

DIGIT = re.compile(r"\d")
SLOT = re.compile(r"\{(S\d+)\}")
STAMP = "> SYNTHETIC DOCUMENT. Fictional test data generated for BIA 562 under D-0022 (fake data). Not a real agreement or proposal."
MIN_UNANSWERABLE = 0.15
TEST_FRACTION = 0.25
SPLITS = ("train", "test")
FAMILY_OF_SPLIT = {"train": "A", "test": "B"}  # §9.2: train = family A, eval = held-out systems in family B


class GenerationError(ValueError):
    pass


def answer_has_digit(answer: str) -> bool:
    """D-0020 rule 1. Slot tokens {S1}, {S2}.. are stripped first: §9.6's own example uses them (see report gap G-03)."""
    return bool(DIGIT.search(SLOT.sub("", answer)))


# ---------- split ----------
def split_systems(system_ids, seed: int, test_fraction: float = TEST_FRACTION) -> dict:
    ids = sorted(system_ids)
    rng = make_rng(f"{seed}|split")
    shuffled = ids[:]
    rng.shuffle(shuffled)
    n_test = max(1, round(len(ids) * test_fraction))
    test = sorted(shuffled[:n_test])
    train = sorted(shuffled[n_test:])
    return {"train": train, "test": test}


def assert_disjoint(split: dict) -> None:
    both = set(split["train"]) & set(split["test"])
    if both:
        raise GenerationError(f"T-0021: systems in both splits: {sorted(both)[:5]}")


def make_rng(key: str):
    return random.Random(key)  # str seeds hash via sha512: stable across processes


# ---------- doc rendering ----------
def render_doc_md(doc, meta: dict) -> str:
    head = "---\n" + "".join(f"{k}: {json.dumps(v)}\n" for k, v in meta.items()) + "---\n\n"
    out = [head, f"# SYNTHETIC — {doc.doc_id}\n\n", STAMP, "\n\n"]
    for s in doc.sections:
        out.append(f"## {s.anchor}. {s.heading}\n\n{s.text}\n\n")
    return "".join(out)


SEC_RE = re.compile(r"^## (\d+(?:\.\d+)*[a-z]?)\. (.+)$", re.M)


def parse_doc_md(text: str) -> tuple:
    fm_raw = text.split("---\n", 2)[1]
    meta = {ln.split(": ", 1)[0]: json.loads(ln.split(": ", 1)[1]) for ln in fm_raw.strip().split("\n")}
    secs = {}
    ms = list(SEC_RE.finditer(text))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        secs[m.group(1)] = {"heading": m.group(2), "text": text[m.end():end].strip("\n")}
    return meta, secs


# ---------- validation (fail-closed) ----------
def validate_bundle(spec, system_id, docs: dict, termsets: list, qas: list, catalog_names: set):
    if not SYSTEM_ID.match(system_id):
        raise GenerationError(f"bad system id {system_id}")
    for did, doc in docs.items():
        if not doc.synthetic:
            raise GenerationError(f"T-0014: {did} not stamped synthetic")
        if not (CONTRACT_DOC_ID.match(did) or PROPOSAL_DOC_ID.match(did)):
            raise GenerationError(f"doc id {did} matches no grammar")
        if doc.system_id != system_id or f"-{system_id}-" not in did:
            raise GenerationError(f"{did} belongs to another system")
        seen = set()
        for s in doc.sections:
            caps.check_section(did, s.anchor, s.text)
            if s.anchor in seen:
                raise GenerationError(f"{did} duplicate anchor {s.anchor}")
            seen.add(s.anchor)
            if s.text != s.text.strip() or not s.text or SEC_RE.search(s.text):
                raise GenerationError(f"{did}#{s.anchor} text not clean")
    for ts in termsets:
        for name, f in ts.fields.items():
            base = name.rsplit("-", 1)[0] if re.search(r"-\d+$", name) else name
            if base not in catalog_names:
                raise GenerationError(f"{ts.doc_id}: field {name} not in field_catalog")
            if f.type not in FIELD_TYPES:
                raise GenerationError(f"{ts.doc_id}: field {name} bad type {f.type}")
            src = docs.get(f.source.doc_id)
            if src is None:
                raise GenerationError(f"{ts.doc_id}: field {name} source doc missing")
            if f.span not in src.section(f.source.anchor).text:
                raise GenerationError(f"I002: {ts.doc_id} field {name} span {f.span!r} not verbatim in {f.source.doc_id}#{f.source.anchor}")
    for q in qas:
        if q.answer_type not in ANSWER_TYPES:
            raise GenerationError(f"{q.qa_id} bad answer_type")
        if answer_has_digit(q.answer):
            raise GenerationError(f"D-0020: {q.qa_id} answer has a digit: {q.answer!r}")
        if q.answer_type == "unanswerable":
            if q.answer != REFUSAL or q.spans or q.source_anchor:
                raise GenerationError(f"{q.qa_id} unanswerable must be the bare refusal")
            continue
        if set(SLOT.findall(q.answer)) != set(q.spans):
            raise GenerationError(f"{q.qa_id} slots {SLOT.findall(q.answer)} != spans {sorted(q.spans)}")
        for slot, ref in q.spans.items():
            did, anchor = ref.anchor.split("#", 1)
            if did not in docs:
                raise GenerationError(f"{q.qa_id} anchor {ref.anchor} is not this system's doc")
            if ref.text not in docs[did].section(anchor).text:
                raise GenerationError(f"{q.qa_id} span {ref.text!r} not verbatim in {ref.anchor}")
        if q.source_anchor != q.spans["S1"].anchor:
            raise GenerationError(f"{q.qa_id} source_anchor disagrees with spans.S1.anchor")


# ---------- leaves ----------
def build_leaves(spec, doc, termset, rel_file: str, seed: int, catalog: dict, amends: str | None):
    kid = "K-" + doc.doc_id
    src = {"file": rel_file, "generator_seed": seed}
    by_anchor = {}
    if termset:
        for name, f in termset.fields.items():
            by_anchor.setdefault(f.source.anchor, []).append((name, f))
    out, clause_ids = [], []
    for s in doc.sections:
        cid = f"CL-{doc.doc_id}-{s.anchor}"
        terms, ctype = [], "other"
        for name, f in by_anchor.get(s.anchor, []):
            base = name.rsplit("-", 1)[0] if re.search(r"-\d+$", name) else name
            ctype = catalog[base]["clause_type"]
            terms.append({"id": f"TM-{cid[3:]}-{name}", "field": base, "value": f.value, "unit": catalog[base]["unit"],
                          "span": f.span, "qualifier": f.qualifier})
        fields = {"anchor": s.anchor, "heading": s.heading, "clause_type": ctype, "terms": terms}
        cl = leaves.clause_leaves(cid, dict(src, anchor=s.anchor), fields, s.text)
        clause_ids.append(cl[0][0])
        out.extend(cl)
    edges = [{"rel": "has_clause", "to": c} for c in clause_ids]
    if amends:
        edges.append({"rel": "amends", "to": "K-" + amends})
    f = termset.fields if termset else {}
    kfields = {"doc_type": doc.doc_type, "title": f"SYNTHETIC {doc.doc_type} {doc.doc_id}",
               "effective_date": f["effective_date"].value if "effective_date" in f else None,
               "expiration_date": f["expiration_date"].value if "expiration_date" in f else None,
               "spec_version": spec.spec_version, "synthetic_stamp": True}
    out.insert(0, leaves.make_leaf(kid, "Contract", src, edges, kfields,
                                   f"SYNTHETIC contract {doc.doc_id}. {STAMP[2:]}"))
    return out


def proposal_leaf(pr, rel_file: str, seed: int):
    body = "\n\n".join(f"## {s.anchor}. {s.heading}\n\n{s.text}" for s in pr.doc.sections)
    edges = [{"rel": "resulted_in", "to": "K-" + pr.resulted_in}] if pr.resulted_in else []
    return leaves.make_leaf("P-" + pr.proposal_id, "Proposal", {"file": rel_file, "generator_seed": seed}, edges,
                            {"date": pr.date, "gives": to_jsonable(list(pr.gives)), "gets": to_jsonable(list(pr.gets)),
                             "outcome": pr.outcome}, body)


# ---------- main ----------
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def generate(spec, systems, out_dir, seed: int, overwrite: bool = False, test_fraction: float = TEST_FRACTION,
             systems_source: dict | None = None) -> dict:
    out = Path(out_dir)
    vault_guard.check_path(out)
    if out.exists() and any(out.iterdir()):
        if not overwrite:
            raise GenerationError(f"{out} is not empty")
        shutil.rmtree(out)
    files = {}  # relpath -> bytes

    def put(rel: str, data: bytes):
        if rel in files:
            raise GenerationError(f"duplicate output {rel}")
        files[rel] = data

    catalog = {c["name"]: c for c in spec.field_catalog()}
    by_id = {s.system_id: s for s in systems}
    if len(by_id) != len(systems):
        raise GenerationError("duplicate system ids")
    split = split_systems(by_id, seed, test_fraction)
    assert_disjoint(split)
    counts = {}
    for sp in SPLITS:
        fam = FAMILY_OF_SPLIT[sp]
        if fam not in spec.families:
            raise GenerationError(f"spec {spec.spec_version} lacks family {fam}")
        qa_lines, n_docs, n_unans, n_leaves = [], 0, 0, 0
        for sid in split[sp]:
            rng = make_rng(f"{seed}|{spec.spec_version}|{sid}")
            dspecs = spec.plan(by_id[sid], rng, fam)
            docs, termsets, qas, props = {}, [], [], []
            for ds in dspecs:
                if ds.doc_type not in spec.doc_types():
                    raise GenerationError(f"{ds.doc_id}: doc_type {ds.doc_type} not in spec.doc_types()")
                docs[ds.doc_id] = spec.render(ds)
                termsets.append(spec.terms(ds))
                for pr in spec.proposals(ds):
                    props.append(pr)
                    docs[pr.proposal_id] = pr.doc
            for ds in dspecs:
                qas.extend(spec.qa(ds))
            validate_bundle(spec, sid, docs, termsets, qas, set(catalog))
            ts_by_doc = {t.doc_id: t for t in termsets}
            amd_of = {}
            for ds in dspecs:
                if ds.doc_type == "AMD":
                    amd_of[ds.doc_id] = [d.doc_id for d in dspecs if d.doc_type == "MSA"][0]
            for did in sorted(docs):
                doc = docs[did]
                meta = {"doc_id": did, "system_id": sid, "doc_type": doc.doc_type, "synthetic": True,
                        "spec_version": spec.spec_version, "family": fam, "generator_seed": seed}
                rel = f"{sp}/docs/{did}.md"
                put(rel, render_doc_md(doc, meta).encode("utf-8"))
                n_docs += 1
                if did in ts_by_doc:
                    put(f"{sp}/docs/{did}.terms.json",
                        (json.dumps(to_jsonable(ts_by_doc[did]), indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode())
                    lv = build_leaves(spec, doc, ts_by_doc[did], rel, seed, catalog, amd_of.get(did))
                else:
                    pr = [p for p in props if p.proposal_id == did][0]
                    put(f"{sp}/docs/{did}.proposal.json",
                        (json.dumps(to_jsonable(pr), indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode())
                    lv = [proposal_leaf(pr, rel, seed)]
                for lid, text in lv:
                    lrel = f"{sp}/leaves/{lid}.md"
                    put(lrel, leaves.guard(out / lrel, lid, text))
                    n_leaves += 1
            for q in qas:
                rec = to_jsonable(q)
                rec["synthetic"] = True
                rec["spec_version"] = spec.spec_version
                qa_lines.append(json.dumps(rec, sort_keys=True, ensure_ascii=False))
                n_unans += q.answer_type == "unanswerable"
        rate = n_unans / max(1, len(qa_lines))
        if rate < MIN_UNANSWERABLE:
            raise GenerationError(f"{sp}: unanswerable rate {rate:.3f} < {MIN_UNANSWERABLE}")
        put(f"{sp}/qa.jsonl", ("\n".join(qa_lines) + "\n").encode("utf-8"))
        counts[sp] = {"systems": len(split[sp]), "families": [fam], "docs": n_docs, "leaves": n_leaves,
                      "qa_rows": len(qa_lines), "unanswerable": n_unans, "unanswerable_rate": round(rate, 4)}
    assert_disjoint(split)
    manifest = {
        "generator_version": GENERATOR_VERSION, "spec_version": spec.spec_version, "seed": seed,
        "synthetic": True, "test_fraction": test_fraction, "systems_source": systems_source,
        "split": {sp: {"family": FAMILY_OF_SPLIT[sp], "systems": split[sp]} for sp in SPLITS},
        "counts": counts,
        "files": {rel: sha256_bytes(b) for rel, b in sorted(files.items())},
    }
    mbytes = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode()
    out.mkdir(parents=True, exist_ok=True)
    for rel, b in sorted(files.items()):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    (out / "manifest.json").write_bytes(mbytes)
    (out / "manifest.sha256").write_text(f"{sha256_bytes(mbytes)}  manifest.json\n")
    return manifest
