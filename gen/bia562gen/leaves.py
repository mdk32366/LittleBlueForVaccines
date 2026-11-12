"""Contract / Clause / Proposal leaves (ONTOLOGY §1-2) with the §8.4 cap guard: measure before write, split or fail."""
from __future__ import annotations

import json

from . import caps, vault_guard
from .ontology import ONTOLOGY_VERSION, match_class


def _fm(d: dict) -> str:
    # JSON flow values are valid YAML; keys emitted in fixed order for byte determinism
    return "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False, sort_keys=True)}\n" for k, v in d.items()) + "---\n"


def leaf_text(meta: dict, body: str) -> str:
    return _fm(meta) + "\n" + body + "\n"


def make_leaf(leaf_id: str, cls: str, source: dict, edges: list, fields: dict, body: str) -> tuple:
    if match_class(leaf_id) != cls:
        raise ValueError(f"O001: id {leaf_id!r} does not match the {cls} grammar")
    meta = {"id": leaf_id, "type": cls, "ontology_version": ONTOLOGY_VERSION, "synthetic": True,
            "source": source, "edges": edges}
    meta.update(fields)
    return leaf_id, leaf_text(meta, body)


def guard(path, leaf_id: str, text: str) -> bytes:
    """Fail-closed pre-write guard: vault rules V1-V3 + L001 cap."""
    vault_guard.check_leaf(path, leaf_id, text)
    data = text.encode("utf-8")
    caps.check_leaf(leaf_id, data)
    return data


def clause_leaves(clause_id: str, source: dict, fields: dict, body: str) -> list:
    """One leaf per section; a body over SPLIT_BODY bytes becomes <id>a, <id>b, ... joined by `continues`."""
    if caps.nbytes(body) <= caps.SPLIT_BODY:
        return [make_leaf(clause_id, "Clause", source, [], fields, body)]
    parts = caps.split_paragraphs(body)
    ids = [f"{clause_id}{chr(ord('a') + i)}" for i in range(len(parts))]
    out = []
    for i, (lid, part) in enumerate(zip(ids, parts)):
        edges = [{"rel": "continues", "to": ids[i + 1]}] if i + 1 < len(ids) else []
        f = dict(fields)
        if i > 0:
            f["terms"] = []  # terms stay on the first sub-leaf whose text carries the span
        out.append(make_leaf(lid, "Clause", source, edges, f, part))
    # terms must be verbatim in the sub-leaf that holds them: move each term to the part containing its span
    return _rehome_terms(out, fields.get("terms", []))


def _rehome_terms(leaves: list, terms: list) -> list:
    if not terms:
        return leaves
    parsed = []
    for lid, text in leaves:
        fm, body = text.split("---\n", 2)[1], text.split("---\n", 2)[2]
        parsed.append([lid, fm, body])
    buckets = {lid: [] for lid, _, _ in parsed}
    for t in terms:
        for lid, _fmx, body in parsed:
            if t["span"] in body:
                buckets[lid].append(t)
                break
        else:
            raise ValueError(f"I002: term span {t['span']!r} not found in any sub-leaf")
    out = []
    for lid, fm, body in parsed:
        lines = [ln if not ln.startswith("terms: ") else "terms: " + json.dumps(buckets[lid], ensure_ascii=False, sort_keys=True)
                 for ln in fm.split("\n")]
        out.append((lid, "---\n" + "\n".join(lines) + "---\n" + body))
    return out
