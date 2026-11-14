"""schema_v1 ContractSpec (GATE 2 path B, structural drop-in): SPEC-contract-data-v1.1 (owner-reviewed draft,
sha256 ccfc8993...). Registered as "v1" (specs/__init__.py); gen/config.json picks it.

What it adds to stub-v0 (the stub's MSA / AMD / proposal shapes and 13 catalog fields stay):
- EXH1 "Purchasing profile schedule" per system (§5.2): the system's figures, its in-state peer figures and the pooled
  national figures as clause text, so every metric answer is a verbatim span. A pure function of the two input files
  (no RNG; T-0075).
- The national file feeds the generator as pooled totals only, fail-closed on a missing file or a changed sha256
  (D-0041 (national file is generator and training input), national.py, T-0065).
- The counterparty is the real manufacturer with the highest FULL-window dollars in the system's primary class
  (D-0044 (real manufacturer as the contract party), T-0074); real brand and manufacturer names are allowed
  (D-0043 (real names in generated data)). The terms stay invented and stamped (D-0022 (fake data)).
- Every TermSet field carries qualifier.provenance in {source, national, invented} (§3, T-0070); invented fields are
  listed in INVENTED_FIELDS with their range and distribution.
- Q&A: the kept stub rows, 12 metric reads, 4 contract x sales rows and 4 refusals per system (§6).
Mapping from the spec's placeholders: D-XXX1..4 = D-0041..D-0044, T-XXX1 = T-0064, T-XX10 = T-0065, T-XX11 = T-0066,
T-XXX3..9 = T-0067..T-0072 and T-0075, T-XX12 = T-0073, T-XX13 = T-0074, AS-XXX1..10 = AS-0060..AS-0069.
"""
from __future__ import annotations

import datetime as dt

from .. import national as NAT
from .. import profile_metrics as PM
from ..ontology import contract_doc_id, proposal_doc_id, slug
from ..seam import Doc, DocSpec, Field, GiveGet, Proposal, QAPair, Section, Source, SpanRef, TermSet, REFUSAL
from .. import caps
from .schema_stub import CATALOG_V0, StubV0Spec, _add_months, _fmt_int, _r10
from .templates_v1 import FAMILIES as FAMILIES_V1

SPEC_VERSION = "schema-v1"
FULL = f"{PM.FULL[0]}-{PM.FULL[1]}"
SEASON = f"{PM.R7_SEASON[0]}-{PM.R7_SEASON[1]}"
SW = tuple(f"{a}-{b}" for a, b in PM.SEASONS)
TOP = 5
TOO_FEW = "too few in-state peers"  # the app's MISSING["state"]
NOT_SHOWN = "n/a"                   # the app shows "n/a" where an index is not computed (AS-0044)

# The client's own item names (app/brief/availability.ITEMS); shared data labels, not family template text.
ITEM_LABELS = {
    "A1": "Total System Vaccines Dollars", "A5": "Corporate_Parent_Type", "A6": "Corporate_Parent_State",
    "A7": "# of Subsidiary", "A8": "# of DDD_Number", "A9": "# of DDD_Number by Specialty",
    "R1": "MenB + MenABCWY to MenACWY + MenABCWY", "R2": "HPV to MenACWY + MenABCWY", "R3": "Influenza to COVID Vaccine",
    "R4": "HepB Ped to DTaP (the client's interim definition)", "R5": "Shingles to adult-labelled Influenza",
    "R6": "RSV Vaccine to adult-labelled Influenza",
    "R7_FLU_TDAP": "Women's Health in season: Influenza to Tdap",
    "R7_RSV_TDAP": "Women's Health in season: RSV Vaccine to Tdap",
}
R7_PARTS = (("boostrix", "r7_boostrix", "Boostrix"), ("flu", "r7_flu", "Influenza"), ("rsv", "r7_rsv", "RSV Vaccine"))


def r7_share(c: dict, comp: str):
    """The app's _r7 rule: comp over Boostrix + Influenza + RSV Vaccine doses in the R7 season, ratio rule, x100."""
    v, st = PM.ratio_rule(c[comp], c["r7_boostrix"] + c["r7_flu"] + c["r7_rsv"])
    return (None if v is None else v * 100), st


RATIO_ITEMS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7_FLU_TDAP", "R7_RSV_TDAP")
# National A6-A9 have no national column (F-0014): they stay "not available: <reason>", the app's exact text
# (availability.render_na), never an invented number (AS-0066 (national A6-A9 stay not available), T-0069).
NAT_NA = {
    "A6": "not available: the national file has no state column",
    "A7": "not available: the national file has no subsidiary column",
    "A8": "not available: the national file has no outlet column",
    "A9": "not available: the national file has no outlet column",
}

# ---------------- catalog (§5, §7) ----------------
CATALOG_MSA_V1 = [
    ("supplier_name", "enum", "id", "parties_scope", [], "1"),
    ("covered_specialty", "enum", "id", "parties_scope", [], "1"),
    ("participating_sites", "int", "count", "parties_scope", [], "1"),
    ("participating_subsidiaries", "int", "count", "parties_scope", [], "1"),
    ("member_org_type", "enum", "id", "parties_scope", [], "1"),
    ("governing_state", "enum", "id", "other", [], "1"),
]
_E = "exhibit"
CATALOG_EXH = [  # name, type, unit, clause_type, qualifiers, cardinality
    ("exh_total_dollars", "num", "usd", _E, [], "1"), ("exh_state_share", "num", "pct", _E, [], "1"),
    ("exh_state_peers", "int", "count", _E, [], "1"), ("exh_nat_share", "num", "pct", _E, [], "1"),
    ("exh_class_share", "num", "pct", _E, ["class"], "*"), ("exh_class_share_state", "num", "pct", _E, ["class"], "*"),
    ("exh_class_share_nat", "num", "pct", _E, ["class"], "*"), ("exh_t12_class_doses", "int", "doses", _E, ["class"], "*"),
    ("exh_spec_share", "num", "pct", _E, ["specialty"], "*"), ("exh_spec_share_state", "num", "pct", _E, ["specialty"], "*"),
    ("exh_spec_share_nat", "num", "pct", _E, ["specialty"], "*"),
    ("exh_cell_dose_share", "num", "pct", _E, ["class", "specialty"], "*"),
    ("exh_cell_dose_share_state", "num", "pct", _E, ["class", "specialty"], "*"),
    ("exh_cell_dose_share_nat", "num", "pct", _E, ["class", "specialty"], "*"),
    ("exh_org_type", "enum", "id", _E, [], "1"), ("exh_state", "enum", "id", _E, [], "1"),
    ("exh_type_share_nat", "num", "pct", _E, [], "1"),
    ("exh_n_subs", "int", "count", _E, [], "1"), ("exh_n_subs_state", "num", "median", _E, [], "1"),
    ("exh_n_sites", "int", "count", _E, [], "1"), ("exh_n_sites_state", "num", "median", _E, [], "1"),
    ("exh_sites_spec", "int", "count", _E, ["specialty"], "*"),
    ("exh_sites_spec_state", "num", "median", _E, ["specialty"], "*"),
    ("exh_babies_total", "num", "est", _E, [], "1"), ("exh_babies_private", "num", "est", _E, [], "1"),
    ("exh_babies_public", "num", "est", _E, [], "1"), ("exh_private_share", "num", "pct", _E, [], "1"),
    ("exh_private_share_state", "num", "pct", _E, [], "1"),
    ("exh_age_share", "num", "pct", _E, ["age"], "*"), ("exh_age_share_state", "num", "pct", _E, ["age"], "*"),
    ("exh_mfr_share", "num", "pct", _E, ["manufacturer"], "*"), ("exh_brand_dollars", "num", "usd", _E, ["brand"], "*"),
    ("exh_ratio", "num", "ratio", _E, ["ratio"], "*"), ("exh_ratio_state", "num", "ratio", _E, ["ratio"], "*"),
    ("exh_r7_share", "num", "pct", _E, ["part"], "*"), ("exh_r7_share_state", "num", "pct", _E, ["part"], "*"),
    ("nat_r7_share", "num", "pct", _E, ["part"], "*"),
    ("exh_idx_state", "num", "index", _E, ["ratio"], "*"), ("exh_idx_nat", "num", "index", _E, ["ratio"], "*"),
    ("nat_total_dollars", "num", "usd", _E, [], "1"), ("nat_class_share", "num", "pct", _E, ["class"], "*"),
    ("nat_spec_share", "num", "pct", _E, ["specialty"], "*"), ("nat_brand_share", "num", "pct", _E, ["brand"], "*"),
    ("nat_type_share", "num", "pct", _E, ["org_type"], "*"), ("nat_age_share", "num", "pct", _E, ["age"], "*"),
    ("nat_private_share", "num", "pct", _E, [], "1"), ("nat_ratio", "num", "ratio", _E, ["ratio"], "*"),
    ("nat_state", "enum", "id", _E, [], "1"), ("nat_subs", "int", "count", _E, [], "1"),
    ("nat_sites", "int", "count", _E, [], "1"), ("nat_sites_by_specialty", "text", "count", _E, [], "1"),
    ("exh_switch_gainer", "enum", "id", _E, ["class"], "*"), ("nat_switch_gainer", "enum", "id", _E, ["class"], "*"),
    ("exh_brand_share_w1", "num", "pct", _E, ["class", "brand"], "*"),
    ("exh_brand_share_w2", "num", "pct", _E, ["class", "brand"], "*"),
    ("nat_brand_share_w1", "num", "pct", _E, ["class", "brand"], "*"),
    ("nat_brand_share_w2", "num", "pct", _E, ["class", "brand"], "*"),
    ("exh_party_share_w1", "num", "pct", _E, ["class", "manufacturer"], "1"),
    ("exh_party_share_w2", "num", "pct", _E, ["class", "manufacturer"], "1"),
]
CATALOG_V1 = CATALOG_V0 + CATALOG_MSA_V1 + CATALOG_EXH

# §3: every invented field, its range and distribution (one registry). Drawn from the system RNG keyed
# "{seed}|schema-v1|{sid}" in the stub's order; covered_specialty and the metric-read pick are drawn after every
# stub draw, so they never shift another field.
INVENTED_FIELDS = {
    "effective_date": ("first of a month, year 2024 or 2025", "uniform year and month"),
    "expiration_date": ("effective date + 2, 3 or 4 years - 1 day", "uniform"),
    "auto_renew": ("True / False", "p = 0.5"),
    "renewal_notice_days": ("30, 60, 90, 120", "uniform"),
    "termination_for_convenience": ("True / False", "p = 0.5"),
    "termination_notice_days": ("60, 90, 180", "uniform"),
    "tier_min_doses": ("T12 primary-class doses x 0.6 / 0.9 / 1.2, to 10 (AS-0024)", "fixed multipliers"),
    "tier_rebate_pct": ("1.5-2.5, then +1.0 or +1.5 per tier", "uniform"),
    "commitment_doses_per_year": ("T12 class doses x U(0.7, 1.3), to 10", "uniform"),
    "share_floor_pct": ("50-85 step 5; an amendment moves it by -10..+10 within 40-95", "uniform"),
    "admin_fee_pct": ("1.0-3.0 step 0.25", "uniform"),
    "covered_specialty": ("one of the system's specialties (sorted)", "uniform"),
}
SOURCE_MSA = ("covered_product", "supplier_name", "participating_sites", "participating_subsidiaries",
              "member_org_type", "governing_state", "exclusivity_class")
NATIONAL_FIELDS = tuple(n for n, *_ in CATALOG_EXH if n.startswith("nat_") or n.endswith("_nat")) + ("exh_nat_share",)
SOURCE_FIELDS = SOURCE_MSA + tuple(n for n, *_ in CATALOG_EXH if n not in NATIONAL_FIELDS)


def provenance_of(name: str) -> str:
    if name in INVENTED_FIELDS:
        return "invented"
    if name in NATIONAL_FIELDS:
        return "national"
    if name in SOURCE_FIELDS:
        return "source"
    raise KeyError(f"field {name} has no provenance")


# ---------------- formats (brief/fmt.py rules: dollars whole, shares 1 dp, ratios 2 dp) ----------------
def f_usd(v):
    return f"${v:,.0f}"


def f_pct(v):
    return f"{v:.1f}%"


def f_fine(v):  # one system's share of national dollars (the app's pct_fine)
    return f"{v:.1f}%" if abs(v) >= 1 else f"{v:.4f}%"


def f_ratio(v):
    return f"{v:.2f}"


def f_idx(v):
    return f"{v:.0f}"


def f_est(v):
    return f"~{v:,.0f}"


def f_med(v):
    return f"{int(v):,}" if float(v).is_integer() else f"{v:,.1f}"


def f_int(v):
    return f"{int(v):,}"


# ---------------- the exhibit (pure function of the system's metrics and the national pool) ----------------
class _Lines:
    """Collects (template key, kwargs, fields) lines per section; fields are (key, base, type, value, span, qual)."""

    def __init__(self):
        self.sections = []  # [(base anchor, heading key, intro kwargs or None, [lines])]
        self.n = {}

    def section(self, anchor, heading, intro=None):
        self.sections.append((anchor, heading, intro, []))

    def key(self, base, multi):
        if not multi:
            return base
        self.n[base] = self.n.get(base, 0) + 1
        return f"{base}-{self.n[base]}"

    def line(self, tpl, kw, fields):
        self.sections[-1][3].append((tpl, kw, fields))


def _fld(L, base, typ, value, status, fmt, qual=None, multi=False):
    """One field: value + its span (the formatted value, or the status label when the status is not ok)."""
    ok = status == "ok" and value is not None
    span = fmt(value) if ok else status
    q = dict(qual or {}, provenance=provenance_of(base), status=status)
    key = L.key(base, multi)
    return (key, base, typ, value if ok else None, span, q), span


def exhibit(system, nat: dict) -> dict:
    """Plan-time data of EXH1 for one system: sections/lines/fields, the metric-read pool and the figures the contract
    x sales rows need. No RNG anywhere (T-0075)."""
    met = system.metrics
    s, pool, med, cnt = met["system"], met["state"], met["state_median"], met["counts"]
    L = _Lines()
    qref = {}

    def q(qtype, field, label, kind, atype="num"):
        qref[qtype] = (field[0], label, kind, atype)

    # §1 basis
    L.section("1", "exh_1", dict(name=system.name, sid=system.system_id, full=FULL, season=SEASON, sw1=SW[0], sw2=SW[1]))
    # §2 A1
    L.section("2", "exh_2")
    f_tot, sp = _fld(L, "exh_total_dollars", "num", s["dollars"], "ok", f_usd, {"item": "A1", "level": "system"})
    L.line("exh_line", dict(label="A1 " + ITEM_LABELS["A1"], value=sp), [f_tot])
    q("metric.A1.system", f_tot, "total dollars (A1)", "system")
    if pool is None:
        v, st = None, TOO_FEW
    else:
        v, st = PM.state_share(s["dollars"], pool["dollars"])
    f_ss, sp = _fld(L, "exh_state_share", "num", None if v is None else v * 100, st, f_pct, {"item": "A1", "level": "state"})
    L.line("exh_line", dict(label="A1 share of the state total including this system", value=sp), [f_ss])
    q("metric.A1.state", f_ss, "the share of the state total including this system (A1)", "system")
    f_np, sp = _fld(L, "exh_state_peers", "int", len(met["peers"]), "ok", f_int, {"item": "A1", "level": "state"})
    L.line("exh_peers", dict(value=sp), [f_np])
    v, st = PM.share_rule(s["dollars"], nat["dollars"])
    f_ns, sp = _fld(L, "exh_nat_share", "num", v, st, f_fine, {"item": "A1", "level": "national"})
    L.line("exh_line", dict(label="A1 share of national dollars", value=sp), [f_ns])
    q("metric.A1.national", f_ns, "the share of national dollars (A1)", "system")

    def comps(mkey, tkey):
        return {"state": None if pool is None else (pool[mkey], pool[tkey]), "national": (nat[mkey], nat[tkey])}

    def series_section(anchor, hkey, item, mkey, tkey, base, qual_key, label_fmt, levels=("state", "national")):
        L.section(anchor, hkey)
        rows = PM.series(s[mkey], s[tkey], comps(mkey, tkey), TOP)
        first = None
        for r in rows:
            qual = {"item": item, qual_key: r["key"] if not isinstance(r["key"], tuple) else list(r["key"])}
            sv = r["system"]
            f1, s1 = _fld(L, base, "num", sv, "ok" if sv is not None else "undefined", f_pct, dict(qual, level="system"), True)
            fields, kw = [f1], dict(label=label_fmt(r["label"]), value=s1)
            if "state" in levels:
                stv = r["state"]
                st_st = TOO_FEW if pool is None else ("ok" if stv is not None else "undefined")
                f2, s2 = _fld(L, base + "_state", "num", stv, st_st, f_pct, dict(qual, level="state"), True)
                fields.append(f2)
                kw["state"] = s2
            nv = r["national"]
            f3, s3 = _fld(L, base + "_nat", "num", nv, "ok" if nv is not None else "undefined", f_pct, dict(qual, level="national"), True)
            fields.append(f3)
            kw["nat"] = s3
            L.line("exh_line3" if "state" in levels else "exh_line2n", kw, fields)
            if first is None:
                first = (r, fields)
        return first

    # §3 A2 + T12 doses for the primary class and the commitment classes
    r, fl = series_section("3", "exh_3", "A2", "cls_dollars", "dollars", "exh_class_share", "class", lambda x: f"{x} share of dollars")
    lab = f"the {r['label']} share of dollars (A2)"
    q("metric.A2.system", fl[0], lab, "system")
    q("metric.A2.state", fl[1], lab, "state")
    q("metric.A2.national", fl[2], lab, "national")
    prim = primary_class(system)
    t12 = dict(system.class_doses)
    t12_classes = []
    for c in [prim] + [c for c, _ in system.class_doses[:2]]:
        if c not in t12_classes:
            t12_classes.append(c)
    t12_fields = {}
    for c in t12_classes:
        f, sp = _fld(L, "exh_t12_class_doses", "int", t12.get(c, 0), "ok", f_int, {"item": "A2", "class": c, "level": "system",
                                                                               "window": "T12"}, True)
        L.line("exh_line", dict(label=f"{c} doses in the trailing twelve months", value=sp), [f])
        t12_fields[c] = f
    # §4 A3
    r, fl = series_section("4", "exh_4", "A3", "spec_dollars", "dollars", "exh_spec_share", "specialty", lambda x: f"{x} share of dollars")
    lab = f"the {r['label']} share of dollars (A3)"
    q("metric.A3.system", fl[0], lab, "system")
    q("metric.A3.state", fl[1], lab, "state")
    q("metric.A3.national", fl[2], lab, "national")
    # §5 A4
    r, fl = series_section("5", "exh_5", "A4", "cls_spec_doses", "doses", "exh_cell_dose_share", "cell",
                           lambda x: f"{x} share of doses")
    lab = f"the {r['label']} share of doses (A4)"
    q("metric.A4.system", fl[0], lab, "system")
    q("metric.A4.state", fl[1], lab, "state")
    q("metric.A4.national", fl[2], lab, "national")
    # §6 A5-A9
    L.section("6", "exh_6")
    f, sp = _fld(L, "exh_org_type", "enum", cnt["type"], "ok", str, {"item": "A5", "level": "system"})
    L.line("exh_line", dict(label="A5 " + ITEM_LABELS["A5"], value=sp), [f])
    q("metric.A5.system", f, "the parent organisation type (A5)", "system", "enum")
    v, st = PM.share_rule(nat["type_dollars"].get(cnt["type"], 0.0), nat["dollars"])
    f, sp = _fld(L, "exh_type_share_nat", "num", v, st, f_pct, {"item": "A5", "level": "national", "org_type": cnt["type"]})
    L.line("exh_line", dict(label=f"A5 national share of dollars for parent type {cnt['type']}", value=sp), [f])
    q("metric.A5.national", f, f"the national dollar share of the {cnt['type']} parent type (A5)", "national")
    f, sp = _fld(L, "exh_state", "enum", cnt["state"], "ok", str, {"item": "A6", "level": "system"})
    L.line("exh_line", dict(label="A6 " + ITEM_LABELS["A6"], value=sp), [f])
    q("metric.A6.system", f, "the parent state (A6)", "system", "enum")
    for item, base, ckey, label in (("A7", "exh_n_subs", "n_subs", "the number of subsidiaries (A7)"),
                                    ("A8", "exh_n_sites", "n_ddd", "the number of sites (A8)")):
        f1, s1 = _fld(L, base, "int", cnt[ckey], "ok", f_int, {"item": item, "level": "system"})
        mv = None if med is None else med[ckey]
        f2, s2 = _fld(L, base + "_state", "num", mv, TOO_FEW if med is None else "ok", f_med, {"item": item, "level": "state"})
        L.line("exh_line2s", dict(label=f"{item} {ITEM_LABELS[item]}", value=s1, state=s2), [f1, f2])
        q(f"metric.{item}.system", f1, label, "system", "int")
        q(f"metric.{item}.state", f2, label, "state")
    specs = sorted(cnt["ddd_by_spec"], key=lambda k: (-cnt["ddd_by_spec"][k], k))
    for i, sname in enumerate(specs):
        f, sp = _fld(L, "exh_sites_spec", "int", cnt["ddd_by_spec"][sname], "ok", f_int,
                     {"item": "A9", "level": "system", "specialty": sname}, True)
        v2 = None if med is None else med["ddd_by_spec"][sname]
        f2, sp2 = _fld(L, "exh_sites_spec_state", "num", v2, TOO_FEW if med is None else "ok", f_med,
                      {"item": "A9", "level": "state", "specialty": sname}, True)
        L.line("exh_line2s", dict(label=f"A9 sites with {sname} rows", value=sp, state=sp2), [f, f2])
        if i == 0:
            q("metric.A9.system", f, f"the number of sites with {sname} rows (A9)", "system", "int")
            q("metric.A9.state", f2, f"the number of sites with {sname} rows (A9)", "state")
    # §7 A10, A11
    L.section("7", "exh_7")
    b = PM.babies(s)
    bs = PM.babies(pool) if pool is not None else None
    for k, base, label in (("total", "exh_babies_total", "A10 babies total (estimate)"),
                           ("private", "exh_babies_private", "A10 babies private (estimate)"),
                           ("public", "exh_babies_public", "A10 babies public (estimate)")):
        f, sp = _fld(L, base, "num", b[k][0], b[k][1], f_est, {"item": "A10", "level": "system"})
        L.line("exh_line", dict(label=label, value=sp), [f])
        if k == "total":
            q("metric.A10.total", f, "the babies total estimate (A10)", "system")
    f1, s1 = _fld(L, "exh_private_share", "num", b["share"][0], b["share"][1], f_pct, {"item": "A10", "level": "system"})
    v2, st2 = (None, TOO_FEW) if bs is None else bs["share"]
    f2, s2 = _fld(L, "exh_private_share_state", "num", v2, st2, f_pct, {"item": "A10", "level": "state"})
    L.line("exh_line2s", dict(label="A10 private share of babies (estimate)", value=s1, state=s2), [f1, f2])
    q("metric.A10.system", f1, "the private share of babies (A10)", "system")
    q("metric.A10.state", f2, "the private share of babies (A10)", "state")
    for i, (age, comp) in enumerate(PM.AGES):
        v1, st1 = PM.share_rule(s[comp], s["doses"])
        f1, s1 = _fld(L, "exh_age_share", "num", v1, st1, f_pct, {"item": "A11", "level": "system", "age": age}, True)
        v2, st2 = (None, TOO_FEW) if pool is None else PM.share_rule(pool[comp], pool["doses"])
        f2, s2 = _fld(L, "exh_age_share_state", "num", v2, st2, f_pct, {"item": "A11", "level": "state", "age": age}, True)
        L.line("exh_line2s", dict(label=f"A11 {age.capitalize()} share of doses", value=s1, state=s2), [f1, f2])
        if i == 0:
            q("metric.A11.system", f1, "the Ped share of doses (A11)", "system")
            q("metric.A11.state", f2, "the Ped share of doses (A11)", "state")
    # §8 highest dollars
    L.section("8", "exh_8")
    for i, r in enumerate(PM.series(s["mfr_dollars"], s["dollars"], {}, TOP)):
        f, sp = _fld(L, "exh_mfr_share", "num", r["system"], "ok" if r["system"] is not None else "undefined", f_pct,
                     {"item": "HD", "level": "system", "manufacturer": r["key"]}, True)
        L.line("exh_line", dict(label=f"{r['label']} share of dollars", value=sp), [f])
        if i == 0:
            q("metric.HD.system", f, f"the {r['label']} share of dollars (highest dollars by manufacturer)", "system")
    brands = sorted(s["brand_dollars"], key=lambda k: (-s["brand_dollars"][k], k))[:TOP]
    for i, br in enumerate(brands):
        f, sp = _fld(L, "exh_brand_dollars", "num", s["brand_dollars"][br], "ok", f_usd,
                     {"item": "HD", "level": "system", "brand": br}, True)
        L.line("exh_line", dict(label=f"{br} dollars", value=sp), [f])
        if i == 0:
            q("metric.HD.brand", f, f"{br} dollars (highest dollars by brand)", "system")
    # §9, §10 ratios: system + state
    ratio_vals = {}
    for anchor, hkey, items in (("9", "exh_9", RATIO_ITEMS[:6]), ("10", "exh_10", RATIO_ITEMS[6:])):
        L.section(anchor, hkey)
        for it in items:
            v1, st1 = PM.ratio(s, it)
            v2, st2 = (None, TOO_FEW) if pool is None else PM.ratio(pool, it)
            f1, s1 = _fld(L, "exh_ratio", "num", v1, st1, f_ratio, {"item": it, "level": "system"}, True)
            f2, s2 = _fld(L, "exh_ratio_state", "num", v2, st2, f_ratio, {"item": it, "level": "state"}, True)
            L.line("exh_line2s", dict(label=f"{it} {ITEM_LABELS[it]}", value=s1, state=s2), [f1, f2])
            lab = f"{it} ({ITEM_LABELS[it]})"
            q(f"metric.{it}.system", f1, lab, "system")
            q(f"metric.{it}.state", f2, lab, "state")
            ratio_vals[it] = (f1[3], f2[3])
        if anchor == "10":  # R7 three-share (Boostrix, Influenza, RSV Vaccine of their sum), pooled like the app's F13.r7_*
            for part, comp, plabel in R7_PARTS:
                vals = []
                for c, base, lvl in ((s, "exh_r7_share", "system"), (pool, "exh_r7_share_state", "state"),
                                     (nat, "nat_r7_share", "national")):
                    v, st = (None, TOO_FEW) if c is None else r7_share(c, comp)
                    vals.append(_fld(L, base, "num", v, st, f_pct, {"item": "R7", "level": lvl, "part": part}, True))
                (f1, s1), (f2, s2), (f3, s3) = vals
                L.line("exh_line3", dict(label=f"R7 {plabel} share of the Women's Health season three", value=s1,
                                         state=s2, nat=s3), [f1, f2, f3])
    # §11 national (same for every system)
    L.section("11", "exh_11")
    f, sp = _fld(L, "nat_total_dollars", "num", nat["dollars"], "ok", f_usd, {"item": "A1", "level": "national"})
    L.line("exh_line", dict(label="National total dollars", value=sp), [f])
    for base, mkey, tkey, qual_key, item, tail in (("nat_class_share", "cls_dollars", "dollars", "class", "A2", "share of national dollars"),
                                                   ("nat_spec_share", "spec_dollars", "dollars", "specialty", "A3", "share of national dollars"),
                                                   ("nat_brand_share", "brand_dollars", "dollars", "brand", "HD", "share of national dollars")):
        for r in PM.series(nat[mkey], nat[tkey], {}, TOP):
            f, sp = _fld(L, base, "num", r["system"], "ok" if r["system"] is not None else "undefined", f_pct,
                         {"item": item, "level": "national", qual_key: r["key"]}, True)
            L.line("exh_line", dict(label=f"{r['label']} {tail}", value=sp), [f])
    for t in sorted(nat["type_dollars"], key=lambda k: (-nat["type_dollars"][k], k)):
        v, st = PM.share_rule(nat["type_dollars"][t], nat["dollars"])
        f, sp = _fld(L, "nat_type_share", "num", v, st, f_pct, {"item": "A5", "level": "national", "org_type": t}, True)
        L.line("exh_line", dict(label=f"Parent type {t} share of national dollars", value=sp), [f])
    for i, (age, comp) in enumerate(PM.AGES):
        v, st = PM.share_rule(nat[comp], nat["doses"])
        f, sp = _fld(L, "nat_age_share", "num", v, st, f_pct, {"item": "A11", "level": "national", "age": age}, True)
        L.line("exh_line", dict(label=f"National {age.capitalize()} share of doses", value=sp), [f])
        if i == 0:
            q("metric.A11.national", f, "the Ped share of doses (A11)", "national")
    nb = PM.babies(nat)
    f, sp = _fld(L, "nat_private_share", "num", nb["share"][0], nb["share"][1], f_pct, {"item": "A10", "level": "national"})
    L.line("exh_line", dict(label="National private share of babies (estimate)", value=sp), [f])
    q("metric.A10.national", f, "the private share of babies (A10)", "national")
    nat_ratio = {}
    for it in RATIO_ITEMS:
        v, st = PM.ratio(nat, it)
        f, sp = _fld(L, "nat_ratio", "num", v, st, f_ratio, {"item": it, "level": "national"}, True)
        L.line("exh_line", dict(label=f"National {it} {ITEM_LABELS[it]}", value=sp), [f])
        q(f"metric.{it}.national", f, f"{it} ({ITEM_LABELS[it]})", "national")
        nat_ratio[it] = f[3]
    for item, base, typ in (("A6", "nat_state", "enum"), ("A7", "nat_subs", "int"), ("A8", "nat_sites", "int"),
                            ("A9", "nat_sites_by_specialty", "text")):
        f, sp = _fld(L, base, typ, None, NAT_NA[item], str, {"item": item, "level": "national"})
        L.line("exh_line", dict(label=f"National {item} {ITEM_LABELS[item]}", value=sp), [f])
        q(f"metric.{item}.national", f, {"A6": "the parent state (A6)", "A7": "the number of subsidiaries (A7)",
                                         "A8": "the number of sites (A8)", "A9": "the number of sites by specialty (A9)"}[item],
          "national", typ if typ != "text" else "span")
    # §12 indices (shown only when both values are ok and the comparator is above zero, AS-0044)
    L.section("12", "exh_12")
    for it in RATIO_ITEMS:
        sv, stv = ratio_vals[it]
        nv = nat_ratio[it]
        iv_s = sv / stv * 100 if sv is not None and stv is not None and stv > 0 else None
        iv_n = sv / nv * 100 if sv is not None and nv is not None and nv > 0 else None
        f1, s1 = _fld(L, "exh_idx_state", "num", iv_s, "ok" if iv_s is not None else NOT_SHOWN, f_idx, {"item": it, "level": "state"}, True)
        f2, s2 = _fld(L, "exh_idx_nat", "num", iv_n, "ok" if iv_n is not None else NOT_SHOWN, f_idx, {"item": it, "level": "national"}, True)
        L.line("exh_idx", dict(label=it, state=s1, nat=s2), [f1, f2])
        q(f"metric.{it}.idx_nat", f2, f"{it} ({ITEM_LABELS[it]})", "idx_nat")
    # §13 brand shares across the same-season windows (exclusivity class first, then the top-3 dollar classes)
    L.section("13", "exh_13")
    party = counterparty(system, prim)
    classes = [prim] + [c for c in top_classes(system, 3) if c != prim]
    gainers = {}
    for i, c in enumerate(classes):
        g, pts = PM.largest_gain(s, c)
        f, sp = _fld(L, "exh_switch_gainer", "enum", g if g != "no volume" else None, "ok" if g != "no volume" else g, str,
                     {"item": "HD", "level": "system", "class": c}, True)
        L.line("exh_switch", dict(cls=c, value=sp), [f])
        gainers[c] = f
        sh = PM.window_shares(s, c)
        top_b = sorted(sh, key=lambda n: (-(sh[n][1] or 0.0), n))
        for br in top_b:
            w1, w2 = sh[br]
            fa, sa = _fld(L, "exh_brand_share_w1", "num", w1, "ok" if w1 is not None else "no volume", f_pct,
                          {"item": "HD", "level": "system", "class": c, "brand": br, "window": SW[0]}, True)
            fb, sb = _fld(L, "exh_brand_share_w2", "num", w2, "ok" if w2 is not None else "no volume", f_pct,
                          {"item": "HD", "level": "system", "class": c, "brand": br, "window": SW[1]}, True)
            L.line("exh_switch_brand", dict(cls=c, brand=br, w1=sa, w2=sb), [fa, fb])
        g2, _ = PM.largest_gain(nat, c)
        f, sp = _fld(L, "nat_switch_gainer", "enum", g2 if g2 != "no volume" else None, "ok" if g2 != "no volume" else g2, str,
                     {"item": "HD", "level": "national", "class": c}, True)
        L.line("exh_switch_nat", dict(cls=c, value=sp), [f])
        for br, (w1, w2) in sorted(PM.window_shares(nat, c).items()):
            fa, sa = _fld(L, "nat_brand_share_w1", "num", w1, "ok" if w1 is not None else "no volume", f_pct,
                          {"item": "HD", "level": "national", "class": c, "brand": br, "window": SW[0]}, True)
            fb, sb = _fld(L, "nat_brand_share_w2", "num", w2, "ok" if w2 is not None else "no volume", f_pct,
                          {"item": "HD", "level": "national", "class": c, "brand": br, "window": SW[1]}, True)
            L.line("exh_switch_brand_nat", dict(cls=c, brand=br, w1=sa, w2=sb), [fa, fb])
    msh = PM.window_shares(s, prim, kind="mfr").get(party, (None, None))
    fa, sa = _fld(L, "exh_party_share_w1", "num", msh[0], "ok" if msh[0] is not None else "no volume", f_pct,
                  {"item": "HD", "level": "system", "class": prim, "manufacturer": party, "window": SW[0]})
    fb, sb = _fld(L, "exh_party_share_w2", "num", msh[1], "ok" if msh[1] is not None else "no volume", f_pct,
                  {"item": "HD", "level": "system", "class": prim, "manufacturer": party, "window": SW[1]})
    L.line("exh_party", dict(party=party, cls=prim, w1=sa, w2=sb), [fa, fb])
    return {"sections": L.sections, "qref": qref, "t12": t12_fields, "gainers": gainers, "party_w2": fb,
            "prim": prim, "party": party}


# ---------------- contract-party rules (D-0044; no RNG) ----------------
def _ranked(d: dict):
    return sorted(((k, v) for k, v in d.items() if v > 0), key=lambda kv: (-kv[1], kv[0]))


def top_classes(system, n=3) -> list:
    return [c for c, _ in _ranked(system.metrics["system"]["cls_dollars"])[:n]]


def primary_class(system) -> str:
    """The class with the highest FULL-window dollars (ties: name ascending)."""
    r = _ranked(system.metrics["system"]["cls_dollars"])
    return r[0][0] if r else (system.class_doses[0][0] if system.class_doses else "Pneumococcal")


def counterparty(system, prim=None) -> str:
    """The real manufacturer (MFR_NM as written) with the highest FULL-window dollars in the primary class; dollars
    descending, then name ascending. Provenance: source."""
    prim = prim or primary_class(system)
    by = {m: v for (c, m), v in system.metrics["system"]["cls_mfr_dollars"].items() if c == prim}
    r = _ranked(by)
    if not r:
        raise ValueError(f"{system.system_id}: no manufacturer with positive dollars in {prim}")
    return r[0][0]


def covered_products(system, party) -> list:
    """The party's top brand by dollars in each of the system's top-3 dollar classes where it sells; a class where it
    has no brand is skipped, so a contract never covers a rival's brand."""
    s = system.metrics["system"]
    out = []
    for c in top_classes(system, 3):
        by = {b: v for (cc, b), v in s["cls_brand_dollars"].items() if cc == c and s["brand_mfr"].get(b) == party}
        r = _ranked(by)
        if r and r[0][0] not in out:
            out.append(r[0][0])
    return out


# ---------------- the spec ----------------
class SchemaV1Spec(StubV0Spec):
    spec_version = SPEC_VERSION
    families = ("A", "B")
    CATALOG = CATALOG_V1
    TEMPLATES = FAMILIES_V1

    def __init__(self, national_path=None):
        self.nat = NAT.load(national_path)  # fail-closed: missing file or changed sha256 raises (T-0065)
        self.nat_pooled = self.nat["pooled"]

    def doc_types(self):
        return ("MSA", "AMD", "EXH")

    def field_catalog(self):
        return [dict(name=n, type=t, unit=u, clause_type=c, qualifiers=q, cardinality=k, provenance=provenance_of(n))
                for n, t, u, c, q, k in self.CATALOG]

    def manifest_extra(self):
        return {"benchmark_source": dict(self.nat["source"]), "counterparty": "real-manufacturer (D-0044)"}

    # ---- plan ----
    def plan(self, system, rng, family):
        if not system.metrics:
            raise ValueError(f"{system.system_id}: schema_v1 needs SystemProfile.metrics (systems.load_csv)")
        t12 = dict(system.class_doses)
        cd = list(system.class_doses) or [("Pneumococcal", 500)]
        prim_cls = primary_class(system)
        prim_doses = t12.get(prim_cls, 0)
        party = counterparty(system, prim_cls)
        cnt = system.metrics["counts"]
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
            name=system.name, sid=system.system_id, state=cnt["state"], party=party,
            products=covered_products(system, party), sites=cnt["n_ddd"], subs=cnt["n_subs"], otype=cnt["type"],
            eff=eff, exp=exp, auto_renew=rng.random() < 0.5, renew_n=rng.choice([30, 60, 90, 120]),
            tfc=rng.random() < 0.5, term_n=rng.choice([60, 90, 180]),
            cls=prim_cls, tiers=[(1, t1, r1), (2, t2, r2), (3, t3, r3)], commits=commits,
            floor=floor, fee=rng.choice([1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]),
        )
        msa_id = contract_doc_id(system.system_id, "MSA", 1)
        exh_id = contract_doc_id(system.system_id, "EXH", 1)
        amd = None
        if rng.random() < 0.5:
            amd_date = _add_months(eff, rng.randint(6, 18))
            if amd_date < exp:
                new_floor = floor + rng.choice([-10, -5, 5, 10])
                new_floor = min(95, max(40, new_floor))
                if new_floor == floor:
                    new_floor = floor + 5
                amd = dict(amd_id=contract_doc_id(system.system_id, "AMD", 1), date=amd_date, floor=new_floor)
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
        msa["qpick"] = rng.random()
        # --- schema_v1 draws, after every stub draw (they shift nothing above) ---
        specs = sorted(k for k, v in system.metrics["system"]["spec_dollars"].items())
        msa["cspec"] = rng.choice(specs) if specs else "General Acute"
        exh = self.exhibit(system)
        msa["metric_pick"] = pick_metrics(exh["qref"], rng)
        data = dict(msa=msa, amd=amd, prop=prop, msa_id=msa_id, exh_id=exh_id, exh=exh)
        out = [DocSpec(msa_id, system.system_id, "MSA", family, data)]
        if amd:
            out.append(DocSpec(amd["amd_id"], system.system_id, "AMD", family, data))
        out.append(DocSpec(exh_id, system.system_id, "EXH", family, data))
        return out

    def exhibit(self, system):
        return exhibit(system, self.nat_pooled)

    # ---- render ----
    def _sections(self, ds):
        if ds.doc_type == "EXH":
            return self._exh_sections(ds)
        F = self.TEMPLATES[ds.family]
        H, C, SP = F["headings"], F["clauses"], F["spans"]
        fd, fp = F["date"], F["pct"]
        m, amd = ds.data["msa"], ds.data["amd"]
        did = ds.doc_id
        P = provenance_of
        out = []

        def fl(key, name, value, typ, span, qual=None):
            return (key, name, value, typ, span, dict(qual or {}, provenance=P(name)))

        if ds.doc_type == "MSA":
            prods = ", ".join(m["products"])
            t = C["parties"].format(name=m["name"], sid=m["sid"], party=m["party"], products=prods, sites=_fmt_int(m["sites"]),
                                    subs=_fmt_int(m["subs"]), otype=m["otype"], cspec=m["cspec"])
            out.append(("1", H["parties"], t, [fl("supplier_name", "supplier_name", m["party"], "enum", m["party"])] +
                        [fl(f"covered_product-{i+1}", "covered_product", p, "enum", p) for i, p in enumerate(m["products"])] +
                        [fl("participating_sites", "participating_sites", m["sites"], "int", _fmt_int(m["sites"])),
                         fl("participating_subsidiaries", "participating_subsidiaries", m["subs"], "int", _fmt_int(m["subs"])),
                         fl("member_org_type", "member_org_type", m["otype"], "enum", m["otype"]),
                         fl("covered_specialty", "covered_specialty", m["cspec"], "enum", m["cspec"])]))
            renew = C["renew_true"] if m["auto_renew"] else C["renew_false"]
            t = C["term"].format(eff=fd(m["eff"]), exp=fd(m["exp"]), renew=renew, n=m["renew_n"])
            out.append(("2", H["term"], t, [
                fl("effective_date", "effective_date", m["eff"].isoformat(), "date", fd(m["eff"])),
                fl("expiration_date", "expiration_date", m["exp"].isoformat(), "date", fd(m["exp"])),
                fl("auto_renew", "auto_renew", m["auto_renew"], "enum", SP["renew_true"] if m["auto_renew"] else SP["renew_false"]),
                fl("renewal_notice_days", "renewal_notice_days", m["renew_n"], "int", str(m["renew_n"]))]))
            tfc = C["tfc_true"] if m["tfc"] else C["tfc_false"]
            t = C["termination"].format(tfc=tfc, n=m["term_n"])
            out.append(("3", H["termination"], t, [
                fl("termination_for_convenience", "termination_for_convenience", m["tfc"], "enum",
                   SP["tfc_true"] if m["tfc"] else SP["tfc_false"]),
                fl("termination_notice_days", "termination_notice_days", m["term_n"], "int", str(m["term_n"]))]))
            for k, doses, pct in m["tiers"]:
                t = C["tier"].format(k=k, doses=_fmt_int(doses), cls=m["cls"], pct=fp(pct))
                q = {"tier": k, "class": f"CLS-{slug(m['cls'])}"}
                out.append((f"4.{k}", H["tier"].format(k=k), t, [
                    fl(f"tier_min_doses-{k}", "tier_min_doses", doses, "int", _fmt_int(doses), q),
                    fl(f"tier_rebate_pct-{k}", "tier_rebate_pct", pct, "pct", fp(pct), q)]))
            for i, (cls, doses) in enumerate(m["commits"], 1):
                t = C["commit"].format(doses=_fmt_int(doses), cls=cls)
                out.append((f"5.{i}", H["commit"].format(cls=cls), t, [
                    fl(f"commitment_doses_per_year-{i}", "commitment_doses_per_year", doses, "int", _fmt_int(doses),
                       {"class": f"CLS-{slug(cls)}"})]))
            t = C["excl"].format(cls=m["cls"], pct=fp(m["floor"]))
            out.append(("6", H["excl"], t, [
                fl("exclusivity_class", "exclusivity_class", f"CLS-{slug(m['cls'])}", "enum", m["cls"]),
                fl("share_floor_pct", "share_floor_pct", m["floor"], "pct", fp(m["floor"]))]))
            t = C["fee"].format(pct=fp(m["fee"]))
            out.append(("7", H["fee"], t, [fl("admin_fee_pct", "admin_fee_pct", m["fee"], "pct", fp(m["fee"]))]))
            out.append(("8", H["other"], C["other"].format(state=m["state"]),
                        [fl("governing_state", "governing_state", m["state"], "enum", m["state"])]))
        elif ds.doc_type == "AMD":
            t = C["amd_purpose"].format(amd_id=did, msa_id=ds.data["msa_id"], date=fd(amd["date"]), party=m["party"])
            out.append(("1", H["amd_purpose"], t, [
                fl("effective_date", "effective_date", amd["date"].isoformat(), "date", fd(amd["date"]))]))
            t = C["amd_share"].format(cls=m["cls"], pct=fp(amd["floor"]))
            out.append(("2", H["amd_share"], t, [fl("share_floor_pct", "share_floor_pct", amd["floor"], "pct", fp(amd["floor"]))]))
        else:
            raise ValueError(ds.doc_type)
        return out

    def _exh_sections(self, ds):
        F = self.TEMPLATES[ds.family]
        H, C = F["headings"], F["clauses"]
        out = []
        for anchor, hkey, intro, lines in ds.data["exh"]["sections"]:
            if intro is not None:
                out.append((anchor, H[hkey], C[hkey].format(**intro), []))
                continue
            chunks, cur, cur_f = [], [], []
            for tpl, kw, fields in lines:
                txt = C[tpl].format(**kw)
                cand = "\n".join(cur + [txt])
                if cur and caps.nbytes(cand) > caps.SECTION_MAX:
                    chunks.append((cur, cur_f))
                    cur, cur_f = [], []
                cur.append(txt)
                cur_f.extend(fields)
            if cur:
                chunks.append((cur, cur_f))
            for i, (txts, fields) in enumerate(chunks):
                a = anchor if i == 0 else f"{anchor}.{i}"
                h = H[hkey] if i == 0 else H["exh_cont"].format(h=H[hkey])
                out.append((a, h, "\n".join(txts), [(k, b, v, t, sp, qq) for k, b, t, v, sp, qq in fields]))
        return out

    def proposals(self, ds):
        if ds.doc_type != "MSA":
            return []
        F = self.TEMPLATES[ds.family]
        H, C = F["headings"], F["clauses"]
        p, m = ds.data["prop"], ds.data["msa"]
        give = self._gg(ds.family, p["give_kind"], p["give_vals"], m)
        get = self._gg(ds.family, p["get_kind"], p["get_vals"], m)
        phrase = F["outcomes"][p["outcome"]]
        secs = (
            Section("1", H["p_summary"], C["p_summary"].format(pid=p["pid"], name=m["name"], date=F["date"](p["date"]),
                                                               party=m["party"])),
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
    def qa(self, ds):
        if ds.doc_type == "EXH":
            return self._qa_metrics(ds)
        out = list(super().qa(ds))
        if ds.doc_type == "MSA":
            out += self._qa_cxs(ds, len(out))
            out += self._qa_refusals(ds, len(out))
        return out

    def _pick(self, ds, qtype, i, **kw):
        opts = self.TEMPLATES[ds.family]["questions"][qtype]
        return opts[(int(ds.data["msa"]["qpick"] * 1000) + i) % len(opts)].format(**kw)

    def _qa_metrics(self, ds):
        F = self.TEMPLATES[ds.family]
        ts = self.terms(ds)
        out = []
        for qtype in ds.data["msa"]["metric_pick"]:
            key, label, kind, atype = ds.data["exh"]["qref"][qtype]
            f = ts.fields[key]
            n = len(out) + 1
            sa = f"{f.source.doc_id}#{f.source.anchor}"
            out.append(QAPair(f"{ds.doc_id}-Q{n:02d}", ds.doc_id, ds.system_id, ds.family,
                              self._pick(ds, f"metric.{kind}", n, label=label), F["answers"][f"metric.{kind}"], atype, sa,
                              {"S1": SpanRef(sa, f.span)}, f.value, key, qtype))
        return out

    def _qa_cxs(self, ds, start):
        """Contract x sales (§6 item 3): the MSA/AMD term span + the EXH1 figure span; value recomputed by the rules
        below (T-0067)."""
        F = self.TEMPLATES[ds.family]
        A = F["answers"]
        m, amd = ds.data["msa"], ds.data["amd"]
        msa_ts = self.terms(ds)
        exh_ds = DocSpec(ds.data["exh_id"], ds.system_id, "EXH", ds.family, ds.data)
        exh_ts = self.terms(exh_ds)
        exh = ds.data["exh"]
        out = []

        def ref(ts, key):
            f = ts.fields[key]
            return SpanRef(f"{f.source.doc_id}#{f.source.anchor}", f.span), f

        def add(qtype, question, answer, atype, spans, value):
            n = start + len(out) + 1
            out.append(QAPair(f"{ds.doc_id}-Q{n:02d}", ds.doc_id, ds.system_id, ds.family, question, answer, atype,
                              spans["S1"].anchor, spans, value, None, qtype))

        # band reached
        t12_key = exh["t12"][m["cls"]][0]
        s_t12, f_t12 = ref(exh_ts, t12_key)
        tiers = [(k, msa_ts.fields[f"tier_min_doses-{k}"].value) for k, _d, _p in m["tiers"]]
        k = band_reached(f_t12.value, tiers)
        s_tier, _ = ref(msa_ts, f"tier_min_doses-{max(k, 1)}")
        add("cxs.band", self._pick(ds, "cxs.band", start + len(out), cls=m["cls"]),
            A["cxs.band_yes"] if k else A["cxs.band_no"], "int", {"S1": s_tier, "S2": s_t12}, k)
        # commitment met (commitment 1, T12 doses of its class)
        c_cls = m["commits"][0][0]
        s_c, f_c = ref(msa_ts, "commitment_doses_per_year-1")
        s_d, f_d = ref(exh_ts, exh["t12"][c_cls][0])
        met = commitment_met(f_d.value, f_c.value)
        add("cxs.commit", self._pick(ds, "cxs.commit", start + len(out), cls=c_cls),
            A[f"cxs.commit_{str(met).lower()}"], "enum", {"S1": s_c, "S2": s_d}, met)
        # share floor met: the party's MANUFACTURER share of the exclusivity class, later season (§5.1), AMD floor first
        floor_ts = msa_ts
        floor_key = "share_floor_pct"
        if amd:
            floor_ts = self.terms(DocSpec(amd["amd_id"], ds.system_id, "AMD", ds.family, ds.data))
        s_f, f_f = ref(floor_ts, floor_key)
        s_s, f_s = ref(exh_ts, exh["party_w2"][0])
        fm = floor_met(f_s.value, effective_floor(msa_ts.fields["share_floor_pct"].value,
                                                  floor_ts.fields["share_floor_pct"].value if amd else None))
        akey = "cxs.floor_none" if fm is None else f"cxs.floor_{str(fm).lower()}"
        add("cxs.floor", self._pick(ds, "cxs.floor", start + len(out), cls=m["cls"], party=m["party"]), A[akey], "enum",
            {"S1": s_f, "S2": s_s}, fm)
        # switching, naming brands (exclusivity class)
        s_g, f_g = ref(exh_ts, exh["gainers"][m["cls"]][0])
        s_x, _ = ref(msa_ts, "exclusivity_class")
        add("cxs.switch", self._pick(ds, "cxs.switch", start + len(out), cls=m["cls"]), A["cxs.switch"], "span",
            {"S1": s_g, "S2": s_x}, f_g.value)
        return out

    def _qa_refusals(self, ds, start):
        """§6 item 4: pricing, clinical, real data, and one more stub off-topic item; each answer is exactly the
        refusal string (D-0027 (refusal string)) with no spans."""
        m = ds.data["msa"]
        s = ds.system_id
        brands = [b for b, _ in _ranked(_brand_dollars(ds))][:2]
        b1 = brands[0] if brands else m["cls"]
        b2 = brands[1] if len(brands) > 1 else m["party"]
        extra = [i for i in range(6) if i not in m["unans"]][0]
        rows = [("refuse.pricing", self._pick(ds, "refuse.pricing", start, party=m["party"], cls=m["cls"])),
                ("refuse.clinical", self._pick(ds, "refuse.clinical", start + 1, b1=b1, b2=b2)),
                ("refuse.real_data", self._pick(ds, "refuse.real_data", start + 2, name=m["name"])),
                ("unanswerable", self.TEMPLATES[ds.family]["questions"]["unanswerable"][extra])]
        return [QAPair(f"{ds.doc_id}-Q{start + i + 1:02d}", ds.doc_id, s, ds.family, qn, REFUSAL, "unanswerable",
                       None, {}, None, None, qt) for i, (qt, qn) in enumerate(rows)]


def _brand_dollars(ds):
    f = {}
    for _a, _h, _i, lines in ds.data["exh"]["sections"]:
        for _t, _kw, fields in lines:
            for key, base, _typ, v, _sp, q in fields:
                if base == "exh_brand_dollars" and v is not None:
                    f[q["brand"]] = v
    return f


# ---------------- contract x sales rules (T-0067) ----------------
def band_reached(t12_doses, tiers) -> int:
    """The largest k with T12 primary-class doses >= tier_min_doses-k; 0 when no tier is reached."""
    k = 0
    for tier, mn in tiers:
        if t12_doses >= mn:
            k = max(k, tier)
    return k


def commitment_met(t12_doses, commitment) -> bool:
    return t12_doses >= commitment


def effective_floor(msa_floor, amd_floor):
    return amd_floor if amd_floor is not None else msa_floor


def floor_met(share_w2, floor):
    return None if share_w2 is None else share_w2 >= floor


# ---------------- metric-read pick (§6 item 2) ----------------
N_METRIC = 12
ALWAYS = ("metric.A1.system", "metric.R1.system")
NATIONAL_KINDS = ("national", "idx_nat")
# The question pool: every client item at each available level (T-0071 coverage).
POOL = ("metric.A1.system", "metric.A1.state", "metric.A1.national",
        "metric.A2.system", "metric.A2.state", "metric.A2.national",
        "metric.A3.system", "metric.A3.state", "metric.A3.national",
        "metric.A4.system", "metric.A4.state", "metric.A4.national",
        "metric.A5.system", "metric.A5.national", "metric.A6.system", "metric.A6.national",
        "metric.A7.system", "metric.A7.state", "metric.A7.national",
        "metric.A8.system", "metric.A8.state", "metric.A8.national",
        "metric.A9.system", "metric.A9.state", "metric.A9.national",
        "metric.A10.total", "metric.A10.system", "metric.A10.state", "metric.A10.national",
        "metric.A11.system", "metric.A11.state", "metric.A11.national",
        "metric.HD.system", "metric.HD.brand") + tuple(
    f"metric.{r}.{lvl}" for r in RATIO_ITEMS for lvl in ("system", "state", "national", "idx_nat"))


def pick_metrics(qref: dict, rng) -> list:
    """12 of the pool per system, drawn with the system RNG: A1 and R1 (system) always, plus one national item."""
    pool = [q for q in POOL if q in qref]
    nat = [q for q in pool if qref[q][2] in NATIONAL_KINDS or q.endswith(".national")]
    first = list(ALWAYS) + [rng.choice(nat)]
    rest = [q for q in pool if q not in first]
    chosen = set(first) | set(rng.sample(rest, N_METRIC - len(first)))
    return [q for q in pool if q in chosen]
