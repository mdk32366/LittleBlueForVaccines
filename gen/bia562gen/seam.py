"""Frozen seam types (TRINITY-ARCH §7.2, ONTOLOGY §6) and the ContractSpec protocol.

Downstream code (generator, leaves, checks) depends ONLY on this module.
A spec module (stub v0, the owner's schema_v1, the test toy spec) implements ContractSpec.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional, Protocol, runtime_checkable

FIELD_TYPES = ("date", "int", "pct", "enum", "text", "num")  # TermSet Field.type, §7.2; "num" added by schema_v1 (Q8 default)
ANSWER_TYPES = ("date", "int", "pct", "enum", "span", "unanswerable", "num")  # QAPair, §7.7; "num" added by schema_v1 (Q8)
DOC_TYPES = ("MSA", "EXH", "AMD", "NOTE")  # ONTOLOGY §4 doc_type vocab
REFUSAL = "not in the contracts"  # §9.2 task A refusal output


@dataclass(frozen=True)
class Section:
    anchor: str
    heading: str
    text: str


@dataclass(frozen=True)
class Doc:
    doc_id: str
    system_id: str
    doc_type: str
    synthetic: bool
    sections: tuple  # tuple[Section, ...]

    def section(self, anchor: str) -> Section:
        for s in self.sections:
            if s.anchor == anchor:
                return s
        raise KeyError(f"{self.doc_id} has no section {anchor}")


@dataclass(frozen=True)
class Source:
    doc_id: str
    anchor: str


@dataclass(frozen=True)
class Field:
    value: Any
    type: str
    source: Source
    span: str
    qualifier: Optional[dict] = None  # ONTOLOGY §1 Term.qualifier {class?, product?, tier?}


@dataclass(frozen=True)
class TermSet:
    doc_id: str
    fields: dict  # name -> Field  (multi-cardinality names carry a -<n> suffix, see docs/assumptions.md)


@dataclass(frozen=True)
class SpanRef:
    anchor: str  # "<doc_id>#<section anchor>", D-0020 / §9.6
    text: str


@dataclass(frozen=True)
class QAPair:
    """§7.7 record with D-0020 `spans` as the canonical answer form (G-04 ruling: no single `span`). `answer` carries slot tokens {S1}.. and never digits."""
    qa_id: str
    doc_id: str
    system_id: str
    family: str
    question: str
    answer: str
    answer_type: str
    source_anchor: Optional[str]  # = spans["S1"].anchor; kept for §7.7 retrieval eval (hit@k), None if unanswerable
    spans: dict = field(default_factory=dict)  # slot -> SpanRef
    value: Any = None  # normalized value for exact-match eval
    field_name: Optional[str] = None
    question_type: Optional[str] = None


@dataclass(frozen=True)
class GiveGet:
    kind: str
    description: str
    span: str
    anchor: str


@dataclass(frozen=True)
class Proposal:
    proposal_id: str  # doc id form SYN-SYNCP000025-P1
    system_id: str
    date: str  # ISO
    gives: tuple
    gets: tuple
    outcome: str
    resulted_in: Optional[str]  # contract doc_id
    doc: Doc


@dataclass(frozen=True)
class DocSpec:
    """Opaque per-document plan produced by ContractSpec.plan(); the generator reads only these attrs."""
    doc_id: str
    system_id: str
    doc_type: str
    family: str
    data: dict = field(default_factory=dict)  # spec-private


@dataclass(frozen=True)
class SystemProfile:
    system_id: str
    name: str
    state_cd: str
    org_type: str
    class_doses: tuple  # tuple[(class_name, doses_t12), ...] sorted desc
    metrics: dict = field(default_factory=dict, compare=False, hash=False)  # schema_v1 seam addition (D-0028-style):
    # profile_metrics.system_metrics() output; empty for stub-v0 fixtures. Ignored by stub-v0.


@runtime_checkable
class ContractSpec(Protocol):
    spec_version: str
    families: tuple  # template families this spec can render, e.g. ("A", "B")

    def doc_types(self) -> tuple: ...
    def field_catalog(self) -> list: ...  # [{name, type, unit, clause_type, qualifiers, cardinality}]
    def plan(self, system: SystemProfile, rng, family: str) -> list: ...  # -> [DocSpec]  (seam addition, see report)
    def render(self, doc_spec: DocSpec) -> Doc: ...
    def terms(self, doc_spec: DocSpec) -> TermSet: ...
    def proposals(self, doc_spec: DocSpec) -> list: ...  # -> [Proposal]
    def qa(self, doc_spec: DocSpec) -> list: ...  # -> [QAPair]
    def template_text(self, family: str) -> list: ...  # static template strings of a family (leak test)


def to_jsonable(obj):
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj
