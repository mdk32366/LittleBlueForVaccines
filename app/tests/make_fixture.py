"""Tiny seeded fixture (§1: ~3 systems, ~400 rows; never a slice of the real file). Planted cases:
- SYNCP800001: planted switch (T-0003): Pneumococcal PFIZER 80% -> 30% at 400 doses per window; MenB 120 / MenACWY 200 (ratio ok)
- SYNCP800002: noise: Pneumococcal ~50/50 both windows (must not flag); MenB 30 / MenACWY 100 (insufficient volume)
- SYNCP800003: edge: MenACWY 0 (undefined), one return row, one null-class row."""
import random

import pandas as pd

from brief.load import REQUIRED_COLUMNS

MONTHS = [f"{y}{m:02d}" for y, m in [(2024, 10), (2024, 11), (2024, 12)] + [(2025, i) for i in range(1, 13)]
          + [(2026, i) for i in range(1, 10)]]
W1 = MONTHS[:6]
W2 = MONTHS[-6:]
SYSTEMS = {"SYNCP800001": ("Fixture Planted Switch 001", "CA"), "SYNCP800002": ("Fixture Noise 002", "CA"),
           "SYNCP800003": ("Fixture Edge 003", "TX")}


def _split(total, k):
    base = [total // k] * k
    for i in range(total % k):
        base[i] += 1
    return base


def build(seed: int = 562) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []

    def add(sid, mth, cls, sub, mfr, doses, dollars=None, chnl="Primary Care"):
        name, st = SYSTEMS[sid]
        r = {c: "" for c in REQUIRED_COLUMNS}
        r.update(MTH_ID=mth, PROD_NM=f"FIXTURE {sub or cls}".upper(), MFR_NM=mfr, VAC_PROD_CLAS_NM=cls,
                 VAC_PROD_SUBCLAS_NM=sub, VAC_AGE_GRP_NM="Adult", VAC_FRZ_IND="0", BAC_CHNL_SPEC_DESC=chnl,
                 BAC_IMS_ORG_ID=f"SYNORG{sid[-4:]}", DDD_OTLT_NBR=f"8{sid[-4:]}", BAC_CORP_PAR_IMS_ORG_ID=sid,
                 BAC_CORP_PAR_NM=name, BAC_CORP_PAR_ORG_TYP_DESC="IDN", BAC_CORP_PAR_ST_CD=st,
                 DDD_OUTLET_STATE=st, DOSES=doses, DOLLARS=round(doses * 50.0 if dollars is None else dollars, 2))
        rows.append(r)

    def window(sid, months, mfr, total, cls="Pneumococcal", sub="PCV20"):
        for m, d in zip(months, _split(total, len(months))):
            add(sid, m, cls, sub, mfr, d, d * 120.0, "General Acute")

    window("SYNCP800001", W1, "PFIZER", 320); window("SYNCP800001", W1, "MERCK & COMPANY", 80)
    window("SYNCP800001", W2, "PFIZER", 120); window("SYNCP800001", W2, "MERCK & COMPANY", 280)
    window("SYNCP800002", W1, "PFIZER", 200); window("SYNCP800002", W1, "MERCK & COMPANY", 200)
    window("SYNCP800002", W2, "PFIZER", 205); window("SYNCP800002", W2, "MERCK & COMPANY", 195)
    for sid, b, a in (("SYNCP800001", 120, 200), ("SYNCP800002", 30, 100), ("SYNCP800003", 80, 0)):
        for m, d in zip(MONTHS[::4], _split(b, 6)):
            add(sid, m, "Meningococcal", "MenB", "PFIZER", d, d * 150.0)
        if a:
            for m, d in zip(MONTHS[1::4], _split(a, 6)):
                add(sid, m, "Meningococcal", "MenACWY", "SANOFI", d, d * 140.0)
    for sid in SYSTEMS:
        for m in MONTHS:
            for cls, mfr in (("Influenza", "SANOFI"), ("Tdap", "GSK PHARM"), ("HPV", "MERCK & COMPANY")):
                add(sid, m, cls, cls, mfr, rng.randrange(1, 9) * 5, None, rng.choice(["Primary Care", "Other"]))
    add("SYNCP800003", "202606", "Influenza", "Influenza", "SANOFI", -10, -512.34)   # a return
    add("SYNCP800003", "202606", "", "", "SANOFI", 5, 250.0)                         # null class
    df = pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
    return df


def write(path, seed: int = 562):
    build(seed).to_csv(path, index=False)
    return path
