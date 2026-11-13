"""Hand-built fixture for the client metrics (T-0042, T-0043, T-0044); never a slice of the real files.

- SYNCP900001 (CA): the hand-computed system. 1,330 doses, $13,300 (dollars = doses x 10).
  R1 = (60 + 20) / (100 + 20); R2 = 90 / 120; R3 = 400 / 100; R5 = 60 / 300; R6 = 30 / 300;
  babies total 200 / 2 = 100, private 250 / 5 = 50; R7 (Women's Health, 202511): Boostrix 20, flu 20, RSV 10.
  Outlets 11, 12, 13 (outlet 11 also has a Pediatric Medicine row, so A9 sums to more than A8); subsidiaries 2.
- SYNCP900002..SYNCP900006 (CA): five identical peers, so SYNCP900001 has exactly five in-state peers.
- SYNCP900007 (TX, alone): edge cases: COVID net -80 (R3 undefined), HPV net -5 (R2 net returns), adult flu 40
  (R5 insufficient volume), private babies above total (inconsistent), no in-state peers.
- SYNCP900008 (NV, alone): the client email 2026-11-13 items: R4 HepB Ped 20 / DTaP 100; R6 = all RSV Vaccine
  products (ABRYSVO 25 + AREXVY 15) / adult flu 140; Women's Health season Influenza 100 and RSV Vaccine 25 over
  Tdap 50 (a 202606 Tdap row and a Primary Care flu row are outside the window); babies private 20 / total 50.
- national_rows(): a twelve-column national-shaped file: R1 400 / 800, R2 400 / 800, R3 1000 / 250, R5 120 / 600,
  R6 60 / 600, babies 200 / 120, R7 Boostrix 30 / RSV 20, 3,960 doses, IDN $31,600 of $39,600."""
import pandas as pd

from brief.benchmark import NATIONAL_COLUMNS
from brief.load import REQUIRED_COLUMNS


def _row(sid, state, cls, sub, doses, age, spec="Primary Care", outlet="", subs="", prod=None, mth="202501",
         typ="IDN"):
    r = {c: "" for c in REQUIRED_COLUMNS}
    r.update(MTH_ID=mth, PROD_NM=prod or f"FIXTURE {sub}".upper(), MFR_NM="FIXTURE MFR", VAC_PROD_CLAS_NM=cls,
             VAC_PROD_SUBCLAS_NM=sub, VAC_AGE_GRP_NM=age, VAC_FRZ_IND="0", BAC_CHNL_SPEC_DESC=spec,
             BAC_IMS_ORG_ID=f"SYNORG{sid[-4:]}", DDD_OTLT_NBR=outlet, BAC_OWN_SUBS_IMS_ORG_ID=subs,
             BAC_CORP_PAR_IMS_ORG_ID=sid, BAC_CORP_PAR_NM=f"Fixture {sid[-3:]}", BAC_CORP_PAR_ORG_TYP_DESC=typ,
             BAC_CORP_PAR_ST_CD=state, DDD_OUTLET_STATE=state, DOSES=doses, DOLLARS=float(doses * 10))
    return r


def synthetic_rows() -> pd.DataFrame:
    s, st = "SYNCP900001", "CA"
    rows = [
        _row(s, st, "Meningococcal", "MenB", 60, "Mixed", outlet="9000011", subs="SUB1"),
        _row(s, st, "Meningococcal", "MenABCWY", 20, "Mixed", outlet="9000011", subs="SUB1"),
        _row(s, st, "Meningococcal", "MenACWY", 100, "Mixed", outlet="9000011", subs="SUB2"),
        _row(s, st, "HPV", "HPV9", 90, "Mixed", outlet="9000011"),
        _row(s, st, "Influenza", "Influenza", 300, "Adult", outlet="9000011"),
        _row(s, st, "Influenza", "Influenza", 80, "Mixed", outlet="9000011"),
        _row(s, st, "Influenza", "Influenza", 20, "Mixed", spec="Women's Health", outlet="9000012", mth="202511"),
        _row(s, st, "Coronavirus", "COVID Vaccine", 100, "Adult", outlet="9000011"),
        _row(s, st, "Shingles", "RZV", 60, "Adult", outlet="9000011"),
        _row(s, st, "RSV", "RSV Vaccine", 20, "Adult", outlet="9000011"),
        _row(s, st, "RSV", "RSV Vaccine", 10, "Adult", spec="Women's Health", outlet="9000012", mth="202511"),
        _row(s, st, "Tdap", "Tdap", 20, "Mixed", spec="Women's Health", outlet="9000012", prod="BOOSTRIX TDAP",
             mth="202511"),
        _row(s, st, "Varicella", "Varicella", 200, "Ped", spec="Pediatric Medicine", outlet="9000013"),
        _row(s, st, "DTaP", "DTaP", 200, "Ped", spec="Pediatric Medicine", outlet="9000013"),
        _row(s, st, "DTaP", "DTaP", 50, "Ped", spec="Pediatric Medicine", outlet="9000011"),
    ]
    for i in range(2, 7):
        p = f"SYNCP90000{i}"
        o1, o2 = f"900{i}001", f"900{i}002"
        rows += [
            _row(p, st, "Meningococcal", "MenB", 100, "Mixed", outlet=o1, subs=f"SUBP{i}"),
            _row(p, st, "Meningococcal", "MenACWY", 200, "Mixed", outlet=o1),
            _row(p, st, "HPV", "HPV9", 100, "Mixed", outlet=o1),
            _row(p, st, "Influenza", "Influenza", 500, "Adult", outlet=o2),
            _row(p, st, "Coronavirus", "COVID Vaccine", 100, "Adult", outlet=o2),
            _row(p, st, "Shingles", "RZV", 50, "Adult", outlet=o2),
            _row(p, st, "RSV", "RSV Vaccine", 50, "Adult", outlet=o2),
            _row(p, st, "Varicella", "Varicella", 100, "Ped", spec="Pediatric Medicine", outlet=o2),
            _row(p, st, "DTaP", "DTaP", 100, "Ped", spec="Pediatric Medicine", outlet=o2),
            _row(p, st, "Tdap", "Tdap", 10, "Mixed", spec="Women's Health", outlet=o2, prod="BOOSTRIX TDAP",
                 mth="202511"),
        ]
    e, tx = "SYNCP900007", "TX"
    rows += [
        _row(e, tx, "Meningococcal", "MenB", 10, "Mixed", outlet="9007001"),
        _row(e, tx, "Meningococcal", "MenACWY", 60, "Mixed", outlet="9007001"),
        _row(e, tx, "HPV", "HPV9", 10, "Mixed", outlet="9007001"),
        _row(e, tx, "HPV", "HPV9", -15, "Mixed", outlet="9007001"),
        _row(e, tx, "Coronavirus", "COVID Vaccine", 20, "Adult", outlet="9007001"),
        _row(e, tx, "Coronavirus", "COVID Vaccine", -100, "Adult", outlet="9007001"),
        _row(e, tx, "Influenza", "Influenza", 40, "Adult", outlet="9007001"),
        _row(e, tx, "Shingles", "RZV", 10, "Adult", outlet="9007001"),
        _row(e, tx, "Varicella", "Varicella", 20, "Ped", outlet="9007001"),
        _row(e, tx, "DTaP", "DTaP", 100, "Ped", outlet="9007001"),
    ]
    o, nv = "SYNCP900008", "NV"   # the client email 2026-11-13 items (T-0055..T-0058)
    rows += [
        _row(o, nv, "Tdap", "Tdap", 50, "Mixed", spec="Women's Health", outlet="9008001", prod="BOOSTRIX TDAP",
             mth="202511"),
        _row(o, nv, "Influenza", "Influenza", 100, "Adult", spec="Women's Health", outlet="9008001", mth="202511"),
        _row(o, nv, "RSV", "RSV Vaccine", 25, "Adult", spec="Women's Health", outlet="9008001", prod="ABRYSVO",
             mth="202512"),
        _row(o, nv, "Tdap", "Tdap", 30, "Mixed", spec="Women's Health", outlet="9008001", prod="ADACEL TDAP",
             mth="202606"),  # out of season: excluded from the OBGYN ratios
        _row(o, nv, "Influenza", "Influenza", 40, "Adult", outlet="9008002", mth="202511"),  # not Women's Health
        _row(o, nv, "RSV", "RSV Vaccine", 15, "Adult", outlet="9008002", prod="AREXVY"),
        _row(o, nv, "Hepatitis", "HepB", 20, "Ped", outlet="9008002"),
        _row(o, nv, "Hepatitis", "HepB", 30, "Adult", outlet="9008002"),
        _row(o, nv, "DTaP", "DTaP", 100, "Ped", outlet="9008002"),
        _row(o, nv, "Varicella", "Varicella", 100, "Ped", outlet="9008002"),
    ]
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)


def national_rows() -> pd.DataFrame:
    def n(cls, sub, doses, age, spec="Primary Care", typ="IDN", prod=None, mth="202501"):
        return {"MTH_ID": mth, "PROD_NM": prod or f"FIXTURE {sub}".upper(), "MFR_NM": "FIXTURE MFR",
                "VAC_PROD_CLAS_NM": cls, "VAC_PROD_SUBCLAS_NM": sub, "VAC_AGE_GRP_NM": age, "VAC_FRZ_IND": "0",
                "SEASON_DESC": "", "BAC_CHNL_SPEC_DESC": spec, "BAC_CORP_PAR_ORG_TYP_DESC": typ, "DOSES": doses,
                "DOLLARS": float(doses * 10)}
    rows = [n("Meningococcal", "MenB", 300, "Mixed"), n("Meningococcal", "MenABCWY", 100, "Mixed"),
            n("Meningococcal", "MenACWY", 700, "Mixed"), n("HPV", "HPV9", 400, "Mixed", typ="Corporate Owner"),
            n("Influenza", "Influenza", 600, "Adult"), n("Influenza", "Influenza", 400, "Mixed", typ="Corporate Owner"),
            n("Coronavirus", "COVID Vaccine", 250, "Adult"), n("Shingles", "RZV", 120, "Adult"),
            n("RSV", "RSV Vaccine", 40, "Adult"),
            n("RSV", "RSV Vaccine", 20, "Adult", spec="Women's Health", mth="202512"),
            n("Varicella", "Varicella", 400, "Ped", spec="Pediatric Medicine"),
            n("DTaP", "DTaP", 600, "Ped", spec="Pediatric Medicine"),
            n("Tdap", "Tdap", 30, "Mixed", spec="Women's Health", prod="BOOSTRIX TDAP", mth="202512")]
    return pd.DataFrame(rows, columns=NATIONAL_COLUMNS)
