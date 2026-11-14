"""T-0074 (counterparty, D-0044 (real manufacturer as the contract party)): supplier_name is the manufacturer with the
highest FULL-window dollars in the primary class (the class with the highest FULL-window dollars), ties by name;
every covered_product is a brand of that manufacturer; the AMD and the proposal name the same party. Recomputed here
from the synthetic file with csv + Decimal only."""
import csv
from collections import defaultdict
from decimal import Decimal

from .conftest import CSV
from .v1_helpers import base, docs, terms


def _top(d):
    return sorted(((k, v) for k, v in d.items() if v > 0), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _recompute():
    cls, cm, brand_mfr = defaultdict(lambda: defaultdict(Decimal)), defaultdict(lambda: defaultdict(Decimal)), {}
    with open(CSV, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sid, c = r["BAC_CORP_PAR_IMS_ORG_ID"], r["VAC_PROD_CLAS_NM"].strip() or "Unclassified"
            m = r["MFR_NM"].strip() or "Unclassified"
            d = Decimal(r["DOLLARS"])
            cls[sid][c] += d
            cm[sid][(c, m)] += d
            brand_mfr.setdefault(r["PROD_NM"], set()).add(m)
    party = {}
    for sid in cls:
        prim = _top(cls[sid])
        party[sid] = _top({m: v for (c, m), v in cm[sid].items() if c == prim})
    return party, brand_mfr


def test_party_and_brands(v1_out):
    party, brand_mfr = _recompute()
    assert all(len(v) == 1 for v in brand_mfr.values()), "a brand has one manufacturer in the file"
    msa = terms(v1_out, "MSA")
    assert len(msa) == 180
    for sid, f in msa.items():
        assert f["supplier_name"]["value"] == party[sid], sid
        prods = [x["value"] for k, x in f.items() if base(k) == "covered_product"]
        assert prods and all(brand_mfr[p] == {party[sid]} for p in prods), (sid, prods)


def test_same_party_in_amd_and_proposal(v1_out):
    msa = terms(v1_out, "MSA")
    for did, (_m, secs) in docs(v1_out).items():
        if did.endswith(("AMD1", "-P1")):
            sid = did.split("-")[1]
            assert msa[sid]["supplier_name"]["value"] in secs["1"]["text"], did
