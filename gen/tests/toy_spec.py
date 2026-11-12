"""T-0022 toy spec: 3 fields, lives only in tests/, loaded by module path. No generator code knows it exists."""
from bia562gen.ontology import contract_doc_id
from bia562gen.seam import Doc, DocSpec, Field, QAPair, Section, Source, SpanRef, TermSet, REFUSAL

T = {
    "A": {"h": "Toy Note Facts", "t": "Toy note dated {d} lists {n} widgets owned by {o}.",
          "q": ["How many widgets does the toy note list?"], "a": "The note lists {S1} widgets.",
          "u": ["What colour are the widgets in the toy note?"]},
    "B": {"h": "Gadget Memo Body", "t": "Memo of {d}: owner {o} reports {n} gadgets held.",
          "q": ["Gadget memo count, please?"], "a": "Count: {S1}.", "u": ["Gadget memo weather report?"]},
}


class ToySpec:
    spec_version = "toy-3"
    families = ("A", "B")

    def doc_types(self):
        return ("NOTE",)

    def field_catalog(self):
        return [dict(name="note_date", type="date", unit="date", clause_type="toy", qualifiers=[], cardinality="1"),
                dict(name="widget_count", type="int", unit="doses", clause_type="toy", qualifiers=[], cardinality="1"),
                dict(name="owner", type="text", unit="id", clause_type="toy", qualifiers=[], cardinality="1")]

    def template_text(self, family):
        import re
        f = T[family]
        return [p for s in [f["h"], f["t"], f["a"], *f["q"], *f["u"]] for p in re.split(r"\{[^}]*\}", s)]

    def plan(self, system, rng, family):
        d = dict(d=f"2025-0{rng.randint(1, 9)}-01", n=rng.randint(2, 99), o=system.name)
        return [DocSpec(contract_doc_id(system.system_id, "NOTE", 1), system.system_id, "NOTE", family, d)]

    def _text(self, ds):
        return T[ds.family]["t"].format(**ds.data)

    def render(self, ds):
        return Doc(ds.doc_id, ds.system_id, "NOTE", True, (Section("1", T[ds.family]["h"], self._text(ds)),))

    def terms(self, ds):
        s = Source(ds.doc_id, "1")
        return TermSet(ds.doc_id, {"note_date": Field(ds.data["d"], "date", s, ds.data["d"]),
                                   "widget_count": Field(ds.data["n"], "int", s, str(ds.data["n"])),
                                   "owner": Field(ds.data["o"], "text", s, ds.data["o"])})

    def proposals(self, ds):
        return []

    def qa(self, ds):
        f = T[ds.family]
        a = f"{ds.doc_id}#1"
        n = str(ds.data["n"])
        return [QAPair(f"{ds.doc_id}-Q01", ds.doc_id, ds.system_id, ds.family, f["q"][0], f["a"], "int", a,
                       {"S1": SpanRef(a, n)}, ds.data["n"], "widget_count", "count"),
                QAPair(f"{ds.doc_id}-Q02", ds.doc_id, ds.system_id, ds.family, f["u"][0], REFUSAL, "unanswerable",
                       None, {}, None, None, "unanswerable")]
