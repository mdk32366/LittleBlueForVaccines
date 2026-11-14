"""Stub v0 ContractSpec (ONTOLOGY §3 catalog v0). The owner's schema_v1 replaces this module, not the generator."""
from __future__ import annotations

import datetime as dt

from ..ontology import contract_doc_id, proposal_doc_id, slug
from ..seam import (Doc, DocSpec, Field, GiveGet, Proposal, QAPair, Section, Source, SpanRef, TermSet,
                    SystemProfile, REFUSAL)
from .templates_stub import FAMILIES, static_fragments

CATALOG_V0 = [
    # name, type, unit, clause_type, qualifiers, cardinality  (ONTOLOGY §3)
    ("covered_product", "enum", "id", "parties_scope", [], "*"),
    ("effective_date", "date", "date", "term_renewal", [], "1"),
    ("expiration_date", "date", "date", "term_renewal", [], "1"),
    ("auto_renew", "enum", "bool", "term_renewal", [], "1"),
    ("renewal_notice_days", "int", "days", "term_renewal", [], "1"),
    ("termination_for_convenience", "enum", "bool", "termination", [], "1"),
    ("termination_notice_days", "int", "days", "termination", [], "1"),
    ("tier_min_doses", "int", "doses", "tier_rebate", ["tier", "class"], "*"),
    ("tier_rebate_pct", "pct", "pct", "tier_rebate", ["tier", "class"], "*"),
    ("commitment_doses_per_year", "int", "doses", "volume_commitment", ["class"], "*"),
    ("exclusivity_class", "enum", "id", "exclusivity_share", [], "1"),
    ("share_floor_pct", "pct", "pct", "exclusivity_share", [], "1"),
    ("admin_fee_pct", "pct", "pct", "admin_fee", [], "1"),
]


def _r10(x: float) -> int:
    return max(10, int(round(x / 10.0)) * 10)


def _add_months(d: dt.date, m: int) -> dt.date:
    y, mo = divmod(d.month - 1 + m, 12)
    return dt.date(d.year + y, mo + 1, 1)


def _fmt_int(n: int) -> str:
    return f"{n:,}"


class StubV0Spec:
    """Also the base for a schema_v1 drop-in that only changes the catalog and/or template text: subclass, set
    spec_version, CATALOG and TEMPLATES (see specs/schema_v1_scaffold.py). Structural changes implement ContractSpec."""
    spec_version = "stub-v0"
    families = ("A", "B")
    CATALOG = CATALOG_V0   # [(name, type, unit, clause_type, qualifiers, cardinality)], ONTOLOGY §3
    TEMPLATES = FAMILIES   # {"A": {...}, "B": {...}} with the keys templates_stub.FAMILIES uses

    # ---- catalog ----
    def doc_types(self):
        return ("MSA", "AMD")

    def field_catalog(self):
        return [dict(name=n, type=t, unit=u, clause_type=c, qualifiers=q, cardinality=k)
                for n, t, u, c, q, k in self.CATALOG]

    def template_text(self, family):
        return static_fragments(family, self.TEMPLATES)

    # ---- plan: all values are family-independent; family only changes phrasing ----
    def plan(self, system: SystemProfile, rng, family: str):
        cd = list(system.class_doses) or [("Pneumococcal", 500)]
        prim_cls, prim_doses = cd[0]
        eff = dt.date(rng.choice([2024, 2025]), rng.randint(1, 12), 1)
        years = rng.choice([2, 3, 4])
        exp = dt.date(eff.year + years, eff.month, 1) - dt.timedelta(days=1)
        r1 = rng.choice([1.5, 2.0, 2.5])
        r2 = r1 + rng.choice([1.0, 1.5])
        r3 = r2 + rng.choice([1.0, 1.5])
        t1 = _r10(prim_doses * 0.6)
        t2 = max(t1 + 10, _r10(prim_doses * 0.9))
        t3 = max(t2 + 10, _r10(prim_doses * 1.2))
        commits = [(c, _r10(d * rng.uniform(0.7, 1.3))) for c, d in cd[:2]]
        floor = rng.choice(range(50, 90, 5))
        msa = dict(
            name=system.name, sid=system.system_id, state=system.state_cd,
            products=[f"PRD-syn-{slug(c)}" for c, _ in cd[:3]],
            eff=eff, exp=exp, auto_renew=rng.random() < 0.5, renew_n=rng.choice([30, 60, 90, 120]),
            tfc=rng.random() < 0.5, term_n=rng.choice([60, 90, 180]),
            cls=prim_cls, tiers=[(1, t1, r1), (2, t2, r2), (3, t3, r3)], commits=commits,
            floor=floor, fee=rng.choice([1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]),
        )
        msa_id = contract_doc_id(system.system_id, "MSA", 1)
        amd = None
        if rng.random() < 0.5:
            amd_date = _add_months(eff, rng.randint(6, 18))
            if amd_date < exp:
                new_floor = floor + rng.choice([-10, -5, 5, 10])
                new_floor = min(95, max(40, new_floor))
                if new_floor == floor:
                    new_floor = floor + 5
                amd = dict(amd_id=contract_doc_id(system.system_id, "AMD", 1), date=amd_date, floor=new_floor)
        # one proposal: it led to the amendment (won/countered) or went nowhere (lost/pending)
        p_date = _add_months(amd["date"], -2) if amd else _add_months(eff, rng.randint(3, 12))
        p_date = p_date + dt.timedelta(days=rng.randint(0, 20))
        k = rng.choice([1, 2, 3])
        give_kind = rng.choice(["rebate_change", "admin_fee_change"])
        get_kind = rng.choice(["exclusivity", "volume_commitment"])
        prop = dict(
            pid=proposal_doc_id(system.system_id, 1), date=p_date,
            outcome=rng.choice(["won", "countered"]) if amd else rng.choice(["lost", "pending"]),
            give_kind=give_kind, give_vals=dict(k=k, pct=msa["tiers"][k - 1][2] + 0.5, fee_pct=msa["fee"] + 0.25),
            get_kind=get_kind, get_vals=dict(cls=prim_cls, pct=(amd["floor"] if amd else floor + 5),
                                             doses=_r10(prim_doses * 1.1)),
            resulted_in=amd["amd_id"] if amd else None,
        )
        unans = rng.sample(range(6), 5)
        msa["unans"] = unans
        msa["qpick"] = rng.random()  # phrasing selector seed
        specs = [DocSpec(msa_id, system.system_id, "MSA", family, dict(msa=msa, amd=amd, prop=prop, msa_id=msa_id))]
        if amd:
            specs.append(DocSpec(amd["amd_id"], system.system_id, "AMD", family,
                                 dict(msa=msa, amd=amd, prop=prop, msa_id=msa_id)))
        return specs

    # ---- render ----
    def _sections(self, ds: DocSpec):
        """Return [(anchor, heading, text, [(field_key, Field-args...)])]"""
        F = self.TEMPLATES[ds.family]
        H, C, SP = F["headings"], F["clauses"], F["spans"]
        fd, fp = F["date"], F["pct"]
        m, amd = ds.data["msa"], ds.data["amd"]
        did = ds.doc_id
        out = []
        if ds.doc_type == "MSA":
            prods = ", ".join(m["products"])
            t = C["parties"].format(name=m["name"], sid=m["sid"], products=prods)
            out.append(("1", H["parties"], t, [(f"covered_product-{i+1}", "covered_product", p, "enum", p, None)
                                                for i, p in enumerate(m["products"])]))
            renew = C["renew_true"] if m["auto_renew"] else C["renew_false"]
            t = C["term"].format(eff=fd(m["eff"]), exp=fd(m["exp"]), renew=renew, n=m["renew_n"])
            out.append(("2", H["term"], t, [
                ("effective_date", "effective_date", m["eff"].isoformat(), "date", fd(m["eff"]), None),
                ("expiration_date", "expiration_date", m["exp"].isoformat(), "date", fd(m["exp"]), None),
                ("auto_renew", "auto_renew", m["auto_renew"], "enum",
                 SP["renew_true"] if m["auto_renew"] else SP["renew_false"], None),
                ("renewal_notice_days", "renewal_notice_days", m["renew_n"], "int", str(m["renew_n"]), None)]))
            tfc = C["tfc_true"] if m["tfc"] else C["tfc_false"]
            t = C["termination"].format(tfc=tfc, n=m["term_n"])
            out.append(("3", H["termination"], t, [
                ("termination_for_convenience", "termination_for_convenience", m["tfc"], "enum",
                 SP["tfc_true"] if m["tfc"] else SP["tfc_false"], None),
                ("termination_notice_days", "termination_notice_days", m["term_n"], "int", str(m["term_n"]), None)]))
            for k, doses, pct in m["tiers"]:
                t = C["tier"].format(k=k, doses=_fmt_int(doses), cls=m["cls"], pct=fp(pct))
                q = {"tier": k, "class": f"CLS-{slug(m['cls'])}"}
                out.append((f"4.{k}", H["tier"].format(k=k), t, [
                    (f"tier_min_doses-{k}", "tier_min_doses", doses, "int", _fmt_int(doses), q),
                    (f"tier_rebate_pct-{k}", "tier_rebate_pct", pct, "pct", fp(pct), q)]))
            for i, (cls, doses) in enumerate(m["commits"], 1):
                t = C["commit"].format(doses=_fmt_int(doses), cls=cls)
                out.append((f"5.{i}", H["commit"].format(cls=cls), t, [
                    (f"commitment_doses_per_year-{i}", "commitment_doses_per_year", doses, "int", _fmt_int(doses),
                     {"class": f"CLS-{slug(cls)}"})]))
            t = C["excl"].format(cls=m["cls"], pct=fp(m["floor"]))
            out.append(("6", H["excl"], t, [
                ("exclusivity_class", "exclusivity_class", f"CLS-{slug(m['cls'])}", "enum", m["cls"], None),
                ("share_floor_pct", "share_floor_pct", m["floor"], "pct", fp(m["floor"]), None)]))
            t = C["fee"].format(pct=fp(m["fee"]))
            out.append(("7", H["fee"], t, [("admin_fee_pct", "admin_fee_pct", m["fee"], "pct", fp(m["fee"]), None)]))
            out.append(("8", H["other"], C["other"].format(state=m["state"]), []))
        elif ds.doc_type == "AMD":
            t = C["amd_purpose"].format(amd_id=did, msa_id=ds.data["msa_id"], date=fd(amd["date"]))
            out.append(("1", H["amd_purpose"], t, [
                ("effective_date", "effective_date", amd["date"].isoformat(), "date", fd(amd["date"]), None)]))
            t = C["amd_share"].format(cls=m["cls"], pct=fp(amd["floor"]))
            out.append(("2", H["amd_share"], t, [
                ("share_floor_pct", "share_floor_pct", amd["floor"], "pct", fp(amd["floor"]), None)]))
        else:
            raise ValueError(ds.doc_type)
        return out

    def render(self, ds: DocSpec) -> Doc:
        return Doc(ds.doc_id, ds.system_id, ds.doc_type, True,
                   tuple(Section(a, h, t) for a, h, t, _ in self._sections(ds)))

    def terms(self, ds: DocSpec) -> TermSet:
        fields = {}
        for a, _h, _t, fl in self._sections(ds):
            for key, _name, value, typ, span, qual in fl:
                fields[key] = Field(value, typ, Source(ds.doc_id, a), span, qual)
        return TermSet(ds.doc_id, fields)

    # ---- proposals ----
    def _gg(self, fam, kind, vals, m):
        F = self.TEMPLATES[fam]
        fp = F["pct"]
        tpl = F["givegets"][kind]
        if kind == "rebate_change":
            return tpl.format(k=vals["k"], pct=fp(vals["pct"]))
        if kind == "admin_fee_change":
            return tpl.format(pct=fp(vals["fee_pct"]))
        if kind == "exclusivity":
            return tpl.format(cls=vals["cls"], pct=fp(vals["pct"]))
        if kind == "volume_commitment":
            return tpl.format(cls=vals["cls"], doses=_fmt_int(vals["doses"]))
        raise ValueError(kind)

    def proposals(self, ds: DocSpec):
        if ds.doc_type != "MSA":
            return []
        F = self.TEMPLATES[ds.family]
        H, C = F["headings"], F["clauses"]
        p, m = ds.data["prop"], ds.data["msa"]
        give = self._gg(ds.family, p["give_kind"], p["give_vals"], m)
        get = self._gg(ds.family, p["get_kind"], p["get_vals"], m)
        phrase = F["outcomes"][p["outcome"]]
        secs = (
            Section("1", H["p_summary"], C["p_summary"].format(pid=p["pid"], name=m["name"], date=F["date"](p["date"]))),
            Section("2", H["p_give"], C["p_give"].format(desc=give)),
            Section("3", H["p_get"], C["p_get"].format(desc=get)),
            Section("4", H["p_outcome"], C["p_outcome"].format(phrase=phrase)),
        )
        doc = Doc(p["pid"], ds.system_id, "PROPOSAL", True, secs)
        return [Proposal(p["pid"], ds.system_id, p["date"].isoformat(),
                         (GiveGet(p["give_kind"], give, give, f"{p['pid']}#2"),),
                         (GiveGet(p["get_kind"], get, get, f"{p['pid']}#3"),),
                         p["outcome"], p["resulted_in"], doc)]

    # ---- qa ----
    def qa(self, ds: DocSpec):
        F = self.TEMPLATES[ds.family]
        Q, A = F["questions"], F["answers"]
        m, amd, p = ds.data["msa"], ds.data["amd"], ds.data["prop"]
        ts = self.terms(ds)
        sel = m["qpick"]
        out = []

        def pick(qtype, i, **kw):
            opts = Q[qtype]
            return opts[(int(sel * 1000) + i) % len(opts)].format(**kw)

        def add(qtype, question, answer_tpl, atype, span_text, anchor_doc, anchor, value, fname):
            n = len(out) + 1
            if atype == "unanswerable":
                out.append(QAPair(f"{ds.doc_id}-Q{n:02d}", ds.doc_id, ds.system_id, ds.family, question, REFUSAL,
                                  "unanswerable", None, {}, None, fname, qtype))
                return
            sa = f"{anchor_doc}#{anchor}"
            out.append(QAPair(f"{ds.doc_id}-Q{n:02d}", ds.doc_id, ds.system_id, ds.family, question, answer_tpl,
                              atype, sa, {"S1": SpanRef(sa, span_text)}, value, fname, qtype))

        def field_q(qtype, key, atype, answer_key=None, **kw):
            f = ts.fields[key]
            add(qtype, pick(qtype, len(out), **kw), A[answer_key or qtype], atype, f.span,
                f.source.doc_id, f.source.anchor, f.value, key)

        if ds.doc_type == "MSA":
            field_q("effective_date", "effective_date", "date")
            field_q("expiration_date", "expiration_date", "date")
            field_q("renewal_notice_days", "renewal_notice_days", "int")
            field_q("auto_renew", "auto_renew", "enum", f"auto_renew_{str(m['auto_renew']).lower()}")
            field_q("termination_notice_days", "termination_notice_days", "int")
            field_q("termination_for_convenience", "termination_for_convenience", "enum",
                    f"termination_for_convenience_{str(m['tfc']).lower()}")
            for k, _d, _p in m["tiers"]:
                field_q("tier_min_doses", f"tier_min_doses-{k}", "int", k=k)
                field_q("tier_rebate_pct", f"tier_rebate_pct-{k}", "pct", k=k)
            for i, (cls, _d) in enumerate(m["commits"], 1):
                field_q("commitment_doses_per_year", f"commitment_doses_per_year-{i}", "int", cls=cls)
            field_q("share_floor_pct", "share_floor_pct", "pct")
            field_q("exclusivity_class", "exclusivity_class", "enum")
            field_q("admin_fee_pct", "admin_fee_pct", "pct")
            # cross-doc: which amendment changed exclusivity
            q = pick("amendment_exclusivity", len(out))
            if amd:
                add("amendment_exclusivity", q, A["amendment_exclusivity"], "span", amd["amd_id"],
                    amd["amd_id"], "1", amd["amd_id"], None)
            else:
                add("amendment_exclusivity", q, None, "unanswerable", None, None, None, None, None)
            # proposal give/get + outcome
            pr = self.proposals(ds)[0]
            year = p["date"].year
            add("proposal_get", pick("proposal_get", len(out), year=year), A["proposal_get"], "span",
                pr.gets[0].span, pr.proposal_id, "3", pr.gets[0].description, None)
            add("proposal_give", pick("proposal_give", len(out), year=year), A["proposal_give"], "span",
                pr.gives[0].span, pr.proposal_id, "2", pr.gives[0].description, None)
            add("proposal_outcome", pick("proposal_outcome", len(out), year=year), A["proposal_outcome"], "enum",
                F["outcomes"][p["outcome"]], pr.proposal_id, "4", p["outcome"], None)
            for i in m["unans"]:
                add("unanswerable", Q["unanswerable"][i], None, "unanswerable", None, None, None, None, None)
        elif ds.doc_type == "AMD":
            field_q("amended_share_floor", "share_floor_pct", "pct")
        return out
