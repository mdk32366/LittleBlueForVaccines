"""T-0073 (synthetic marker; mitigation for D-0044 (real manufacturer as the contract party), AS-0069): every gen/out
document has MARKER as the header line and as the footer line after the rule; every Contract and Proposal leaf body
has it; MARKER is in no section's text; the manifest says contract_terms "invented"; every QA row citing an MSA,
AMD or proposal anchor carries terms_invented: true."""
import json
import re

from .v1_helpers import SPLITS, docs, qa

MARKER = "SYNTHETIC TRAINING DOCUMENT. NOT A REAL AGREEMENT. Terms are invented."  # spec §5.3, verbatim
TERMS_DOC = re.compile(r"-(MSA|AMD)\d+$|-P\d+$")


def test_marker_header_and_footer(v1_out):
    n = 0
    for sp in SPLITS:
        for p in sorted((v1_out / sp / "docs").glob("*.md")):
            lines = p.read_text().split("\n")
            title = [i for i, ln in enumerate(lines) if ln.startswith("# SYNTHETIC")][0]
            body = [ln for ln in lines[title + 1:] if ln.strip()]
            assert body[0] == MARKER, f"{p.name}: header"
            tail = [ln for ln in lines if ln.strip()]
            assert tail[-1] == MARKER and tail[-2] == "---", f"{p.name}: footer"
            n += 1
    assert n >= 600


def test_marker_never_inside_a_section(v1_out):
    for did, (_m, secs) in docs(v1_out).items():
        for a, s in secs.items():
            assert MARKER not in s["text"] and "Terms are invented" not in s["text"], (did, a)


def test_marker_in_contract_and_proposal_leaves(v1_out):
    n = 0
    for sp in SPLITS:
        for p in (v1_out / sp / "leaves").glob("*.md"):
            if p.name.startswith(("K-", "P-")):
                assert MARKER in p.read_text().split("---\n", 2)[2], p.name
                n += 1
    assert n >= 600


def test_manifest_flag_and_row_flag(v1_out):
    m = json.loads((v1_out / "manifest.json").read_text())
    assert m["contract_terms"] == "invented" and m["counterparty"].startswith("real-manufacturer")
    n = 0
    for q in qa(v1_out):
        cites = any(TERMS_DOC.search(r["anchor"].split("#")[0]) for r in q["spans"].values())
        assert q.get("terms_invented") is True, q["qa_id"]
        n += cites
    assert n > 1000
