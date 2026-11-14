"""Shared fixtures + REDPROOF mutations.

REDPROOF=<name> pytest ...  applies ONE deliberate defect at session start (test-side monkeypatch only; no
production code knows about it) so tools/redproof.py can prove each guard test goes red.
"""
import dataclasses
import hashlib
import os
import random
from pathlib import Path

import pytest

from bia562gen import caps, generate as G, national as NAT, profile_metrics as PM, systems as S, vault_guard
from bia562gen.specs import conformance, load_spec, schema_stub, schema_v1 as V1, templates_stub
from bia562gen.systems import fixture_systems

SEED = 562
B_FRAGMENT = "Products within its reach: "
ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT.parent / "data" / "BIA_562_Synthetic_Sales_Data.csv"


def _noop(*a, **k):
    return None


def apply_mutation(name):
    if name == "nondet":
        G.make_rng = lambda key: random.Random(key + os.urandom(8).hex())
    elif name == "span":
        G.validate_bundle = _noop
        orig = schema_stub.StubV0Spec.qa

        def bad_qa(self, ds):
            out = []
            for q in orig(self, ds):
                if q.spans:
                    s1 = q.spans["S1"]
                    s1 = dataclasses.replace(s1, text=s1.text + "9")
                    q = dataclasses.replace(q, spans={"S1": s1})
                out.append(q)
            return out
        schema_stub.StubV0Spec.qa = bad_qa
    elif name == "digits":
        G.validate_bundle = _noop
        templates_stub.FAMILIES["A"]["answers"]["expiration_date"] = "It expires in 2027, on {S1}."
    elif name == "overlap":
        orig_split = G.split_systems

        def bad_split(ids, seed, frac=0.25):
            s = orig_split(ids, seed, frac)
            return {"train": sorted(set(s["train"]) | set(s["test"][:1])), "test": s["test"]}
        G.split_systems = bad_split
        G.assert_disjoint = _noop
    elif name == "famsplit":
        G.FAMILY_OF_SPLIT["test"] = "A"
    elif name == "leak":
        c = templates_stub.FAMILIES["A"]["clauses"]
        c["other"] = c["other"] + " " + B_FRAGMENT + "none."
    elif name == "cap":
        caps.check_leaf = lambda leaf_id, data: len(data)
        caps.check_section = lambda doc_id, anchor, text: len(text)
    elif name == "vault":
        for fn in ("check_path", "check_leaf_id", "check_body", "check_vendored_dir", "check_leaf"):
            setattr(vault_guard, fn, _noop)
    elif name == "unans":
        G.MIN_UNANSWERABLE = 0.0
        orig = schema_stub.StubV0Spec.qa
        schema_stub.StubV0Spec.qa = lambda self, ds: [q for q in orig(self, ds) if q.answer_type != "unanswerable"]
    elif name == "barestamp":  # the stamp goes back to a bare decision number
        G.STAMP = "> SYNTHETIC DOCUMENT. Fictional test data generated for BIA 562 (D-0022). Not a real agreement or proposal."
    elif name == "dropin_as0041":  # the schema_v1 drop-in gate stops checking AS-0041
        conformance.check_auto_renew = lambda doc_id, fields, sections: []
    elif name == "dropin_appfields":  # the drop-in gate stops checking the app's field names
        conformance.check_app_fields = lambda spec: ([], [])
    # ---- schema_v1 (GATE 2 path B) mutations; each must turn its T test red ----
    elif name == "nat_fallback":  # T-0065: a missing or altered national file silently falls back to synthetic peers
        orig_load = NAT.load

        def fallback(path=None, expected_sha256=NAT.RECORDED_SHA256):
            try:
                return orig_load(path, expected_sha256)
            except NAT.NationalInputError:
                acc = PM.Acc()
                for v in PM.read_systems(CSV).values():
                    acc += v["acc"]
                return {"pooled": acc.pooled(), "source": {"file": CSV.name, "sha256": "", "rows": acc.rows}}
        NAT.load = fallback
    elif name == "nat_drop":  # T-0065: EXH1 omits the national section §11
        orig_exh = V1.exhibit

        def no_nat(system, nat):
            e = orig_exh(system, nat)
            e["sections"] = [x for x in e["sections"] if x[0] != "11"]
            e["qref"] = {k: v for k, v in e["qref"].items() if not v[0].startswith("nat_")}
            return e
        V1.exhibit = no_nat
    elif name == "nat_window":  # T-0065: the national pool uses T12 instead of the FULL window
        orig_add = PM.Acc.add

        def t12_only(self, r):
            if "BAC_CORP_PAR_IMS_ORG_ID" not in r and not (PM.T12[0] <= r["MTH_ID"] <= PM.T12[1]):
                return None
            return orig_add(self, r)
        PM.Acc.add = t12_only
    elif name == "nat_sha":  # T-0065: the manifest omits the national file's hash
        orig_extra = V1.SchemaV1Spec.manifest_extra

        def no_sha(self):
            e = orig_extra(self)
            e["benchmark_source"] = {k: v for k, v in e["benchmark_source"].items() if k != "sha256"}
            return e
        V1.SchemaV1Spec.manifest_extra = no_sha
    elif name == "nat_cols":  # T-0065: the loader also reads SEASON_DESC
        NAT.USED_COLUMNS = NAT.USED_COLUMNS + ("SEASON_DESC",)
    elif name == "band_gt":  # T-0067: band reached uses > instead of >=
        V1.band_reached = lambda doses, tiers: max([t for t, mn in tiers if doses > mn], default=0)
    elif name == "floor_ignore_amd":  # T-0067: the share-floor check ignores the amended floor
        V1.effective_floor = lambda msa_floor, amd_floor: msa_floor
    elif name == "refuse_leak":  # T-0068: a refusal row carries more than the refusal string
        G.validate_bundle = _noop
        orig_ref = V1.SchemaV1Spec._qa_refusals

        def leaky(self, ds, start):
            return [dataclasses.replace(q, answer=q.answer + " Ask the Supplier.") if q.question_type == "refuse.pricing"
                    else q for q in orig_ref(self, ds, start)]
        V1.SchemaV1Spec._qa_refusals = leaky
    elif name == "status_number":  # T-0069: a not-ok metric gets a number instead of its status label
        orig_fld = V1._fld

        def numbered(L, base, typ, value, status, fmt, qual=None, multi=False):
            if status != "ok" and base.startswith("exh_ratio"):
                f, _ = orig_fld(L, base, typ, value, status, fmt, qual, multi)
                f = (f[0], f[1], f[2], 0.0, "0.00", f[5])
                return f, "0.00"
            return orig_fld(L, base, typ, value, status, fmt, qual, multi)
        V1._fld = numbered
    elif name == "nat_invent":  # T-0069: national A8 (sites) is given a number
        orig_fld2 = V1._fld

        def invent(L, base, typ, value, status, fmt, qual=None, multi=False):
            if base == "nat_sites":
                return orig_fld2(L, base, "int", 12, "ok", V1.f_int, qual, multi)
            return orig_fld2(L, base, typ, value, status, fmt, qual, multi)
        V1._fld = invent
    elif name == "inv_source":  # T-0070: A7 (participating subsidiaries) is drawn from the RNG
        orig_plan = V1.SchemaV1Spec.plan

        def rng_subs(self, system, rng, family):
            out = orig_plan(self, system, rng, family)
            out[0].data["msa"]["subs"] = rng.randint(1, 60)
            return out
        V1.SchemaV1Spec.plan = rng_subs
    elif name == "drop_r5":  # T-0071: R5 disappears from the question pool
        V1.POOL = tuple(q for q in V1.POOL if not q.startswith("metric.R5."))
    elif name == "exh_skip_one":  # T-0072: one system gets no EXH1
        G.validate_bundle = _noop
        orig_plan2 = V1.SchemaV1Spec.plan

        def skip(self, system, rng, family):
            out = orig_plan2(self, system, rng, family)
            return [d for d in out if not (d.doc_type == "EXH" and system.system_id == "SYNCP000025")]
        V1.SchemaV1Spec.plan = skip
    elif name == "nomarker":  # T-0073: MARKER removed from the header and the footer
        orig_render = G.render_doc_md
        G.render_doc_md = lambda doc, meta: orig_render(doc, meta).replace(G.MARKER + "\n", "")
    elif name == "nofooter":  # T-0073: the footer marker only
        orig_render2 = G.render_doc_md

        def no_footer(doc, meta):
            t = orig_render2(doc, meta)
            return t[: t.rindex(G.FOOTER_RULE + "\n")]
        G.render_doc_md = no_footer
    elif name == "marker_typo":  # T-0073: one word of the MARKER changed
        G.MARKER = "SYNTHETIC TRAINING DOCUMENT. NOT A REAL AGREEMENT. Terms are imagined."
    elif name == "noflag":  # T-0073: the manifest's contract_terms flag dropped
        G.CONTRACT_TERMS = None
    elif name == "party_rng":  # T-0074: the counterparty is drawn at random among the class's manufacturers
        def rnd_party(system, prim=None):
            prim = prim or V1.primary_class(system)
            ms = sorted({m for (c, m), v in system.metrics["system"]["cls_mfr_dollars"].items() if c == prim and v > 0})
            return random.Random(system.system_id).choice(ms)
        V1.counterparty = rnd_party
    elif name == "rival_brand":  # T-0074: a rival manufacturer's brand is covered
        orig_cov = V1.covered_products

        def rival(system, party):
            out = orig_cov(system, party)
            s = system.metrics["system"]
            other = sorted(b for b, v in s["brand_dollars"].items() if v > 0 and s["brand_mfr"].get(b) != party)
            return out + other[:1]
        V1.covered_products = rival
    elif name == "exh_rng":  # T-0075: EXH1 text depends on the RNG
        orig_plan3 = V1.SchemaV1Spec.plan

        def rng_exh(self, system, rng, family):
            out = orig_plan3(self, system, rng, family)
            for d in out:
                if d.doc_type == "EXH":
                    d.data["exh"]["sections"][1][3].append(("exh_line", {"label": "Draw", "value": f"{rng.random():.4f}"}, []))
            return out
        V1.SchemaV1Spec.plan = rng_exh
    elif name:
        raise ValueError(f"unknown REDPROOF mutation {name}")


def pytest_configure(config):
    apply_mutation(os.environ.get("REDPROOF", ""))


@pytest.fixture(scope="session")
def spec():
    return load_spec("stub-v0")


@pytest.fixture(scope="session")
def systems():
    return fixture_systems(12)


@pytest.fixture(scope="session")
def out(tmp_path_factory, spec, systems):
    d = tmp_path_factory.mktemp("gen") / "out"
    G.generate(spec, systems, d, SEED, systems_source={"kind": "fixture", "n": 12})
    return d


# ---- schema_v1: the real regeneration, in process (so a mutation of the generator shows in it) ----
@pytest.fixture(scope="session")
def v1_spec():
    return load_spec("v1")


@pytest.fixture(scope="session")
def real_systems():
    return S.load_csv(CSV)


@pytest.fixture(scope="session")
def v1_out(tmp_path_factory, v1_spec, real_systems):
    d = tmp_path_factory.mktemp("v1") / "out"
    src = {"kind": "csv", "file": CSV.name, "sha256": hashlib.sha256(CSV.read_bytes()).hexdigest()}
    G.generate(v1_spec, real_systems, d, SEED, systems_source=src)
    return d
