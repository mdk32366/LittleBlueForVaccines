"""ID grammars from ONTOLOGY §1 (ontology_version 1)."""
import re

ONTOLOGY_VERSION = 1

GRAMMARS = {
    "HealthSystem": r"HS-SYNCP\d{6}",
    "Outlet": r"OUT-\d+",
    "State": r"ST-[A-Z]{2}",
    "Product": r"PRD-[a-z0-9-]+",
    "TherapeuticClass": r"CLS-[a-z0-9-]+",
    "Manufacturer": r"MFR-[a-z0-9-]+",
    "Contract": r"K-SYN-SYNCP\d{6}-(MSA|EXH|AMD|NOTE)\d+",
    # CL-<contract-id-sans-K>-<anchor>[a-z]? ; anchor shape (e.g. 4.2) is not formally defined -> digits/dots
    "Clause": r"CL-SYN-SYNCP\d{6}-(MSA|EXH|AMD|NOTE)\d+-\d+(\.\d+)*[a-z]?",
    "Proposal": r"P-SYN-SYNCP\d{6}-P\d+",
    "Benchmark": r"BM-(synthetic-peers|local)",
    "FactSheet": r"FS-SYNCP\d{6}-\d{6}(-sales|-contract)?",
}
_COMPILED = {k: re.compile("^" + v + "$") for k, v in GRAMMARS.items()}

# Doc ids (no class prefix): §7.3 "SYN-SYNCP000025-MSA1", K-/P- leaf ids minus prefix.
CONTRACT_DOC_ID = re.compile(r"^SYN-SYNCP\d{6}-(MSA|EXH|AMD|NOTE)\d+$")
PROPOSAL_DOC_ID = re.compile(r"^SYN-SYNCP\d{6}-P\d+$")
SYSTEM_ID = re.compile(r"^SYNCP\d{6}$")


def match_class(leaf_id: str):
    for cls, rx in _COMPILED.items():
        if rx.match(leaf_id):
            return cls
    return None


def contract_doc_id(system_id: str, doc_type: str, n: int) -> str:
    did = f"SYN-{system_id}-{doc_type}{n}"
    assert CONTRACT_DOC_ID.match(did), did
    return did


def proposal_doc_id(system_id: str, n: int) -> str:
    did = f"SYN-{system_id}-P{n}"
    assert PROPOSAL_DOC_ID.match(did), did
    return did


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
