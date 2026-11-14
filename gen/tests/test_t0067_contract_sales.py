"""T-0067 (contract x sales): band reached, commitment met, share floor met (the AMD floor when there is one) and the
switching answer are recomputed here from the TermSets + EXH1 and must equal each QA row's value."""
from bia562gen.ontology import slug
from bia562gen.specs import schema_v1 as V1

from .v1_helpers import base, qa, terms


def _band(doses, tiers):
    return max([t for t, mn in tiers if doses >= mn], default=0)  # independent of V1.band_reached


def test_rule_edges():
    tiers = [(1, 880), (2, 1310), (3, 1750)]
    assert V1.band_reached(880, tiers) == 1 and V1.band_reached(879, tiers) == 0 and V1.band_reached(1750, tiers) == 3
    assert V1.commitment_met(260, 260) is True and V1.commitment_met(259, 260) is False
    assert V1.effective_floor(55, 60) == 60 and V1.effective_floor(55, None) == 55
    assert V1.floor_met(60.0, 60) is True and V1.floor_met(None, 60) is None


def test_values_recomputed(v1_out):
    msa, exh, amd = terms(v1_out, "MSA"), terms(v1_out, "EXH"), terms(v1_out, "AMD")
    rows = [q for q in qa(v1_out) if q["question_type"].startswith("cxs.")]
    assert len(rows) == 4 * 180
    for q in rows:
        sid, t = q["system_id"], q["question_type"]
        m, e = msa[sid], exh[sid]
        prim = m["exclusivity_class"]["span"]
        t12 = {f["qualifier"]["class"]: f["value"] for k, f in e.items() if base(k) == "exh_t12_class_doses"}
        if t == "cxs.band":
            tiers = [(f["qualifier"]["tier"], f["value"]) for k, f in m.items() if base(k) == "tier_min_doses"]
            assert q["value"] == _band(t12[prim], tiers), q["qa_id"]
        elif t == "cxs.commit":
            c = m["commitment_doses_per_year-1"]
            cname = [k for k in t12 if f"CLS-{slug(k)}" == c["qualifier"]["class"]]
            assert len(cname) == 1, q["qa_id"]
            assert q["value"] == (t12[cname[0]] >= c["value"]), q["qa_id"]
        elif t == "cxs.floor":
            floor = amd[sid]["share_floor_pct"]["value"] if sid in amd else m["share_floor_pct"]["value"]
            share = e["exh_party_share_w2"]["value"]
            assert q["value"] == (None if share is None else share >= floor), q["qa_id"]
            assert q["spans"]["S1"]["anchor"].split("#")[0].endswith("AMD1" if sid in amd else "MSA1"), q["qa_id"]
        elif t == "cxs.switch":
            g = [f for k, f in e.items() if base(k) == "exh_switch_gainer" and f["qualifier"]["class"] == prim][0]
            assert q["value"] == g["value"] and q["spans"]["S1"]["text"] == g["span"], q["qa_id"]
