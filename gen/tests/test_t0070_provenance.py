"""T-0070 (provenance): every TermSet field has qualifier.provenance in {source, national, invented}; invented fields
are exactly the INVENTED_FIELDS registry's; no source field is invented. A7 (participating subsidiaries) and A8
(sites) are recomputed here from the synthetic file (a blank subsidiary is parent-owned, AS-0063)."""
import csv
from collections import defaultdict

from bia562gen.specs import schema_v1 as V1

from .conftest import CSV
from .v1_helpers import base, terms


def test_every_field_has_provenance(v1_out):
    for kind in ("MSA", "AMD", "EXH"):
        for sid, fields in terms(v1_out, kind).items():
            for k, f in fields.items():
                p = (f.get("qualifier") or {}).get("provenance")
                b = base(k)
                assert p in ("source", "national", "invented"), (sid, k)
                assert (p == "invented") == (b in V1.INVENTED_FIELDS), (sid, k, p)
                if b in V1.SOURCE_FIELDS:
                    assert p == "source", (sid, k)


def test_source_counts_recomputed(v1_out):
    subs, sites = defaultdict(set), defaultdict(set)
    with open(CSV, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["BAC_OWN_SUBS_IMS_ORG_ID"].strip():
                subs[r["BAC_CORP_PAR_IMS_ORG_ID"]].add(r["BAC_OWN_SUBS_IMS_ORG_ID"])
            sites[r["BAC_CORP_PAR_IMS_ORG_ID"]].add(r["DDD_OTLT_NBR"])
    msa = terms(v1_out, "MSA")
    assert len(msa) == 180
    for sid, f in msa.items():
        assert f["participating_subsidiaries"]["value"] == len(subs[sid]), sid
        assert f["participating_sites"]["value"] == len(sites[sid]), sid
