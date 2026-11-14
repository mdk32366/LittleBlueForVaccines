"""System profiles: from the (fake, D-0022 (fake data)) synthetic sales CSV, or a seeded fixture for tests.
schema_v1: load_csv also fills SystemProfile.metrics (profile_metrics, one more pass over the same file) and
fixture_systems fills a small hand-checkable set from fixture rows run through the same code path."""
import csv
import random
from collections import defaultdict

from . import profile_metrics as PM
from .seam import SystemProfile

T12_FROM, T12_TO = "202510", "202609"  # trailing 12 months to the data's last month (program-level as-of-month assumption: 202609)


def load_csv(path) -> list:
    sysinfo = {}
    doses = defaultdict(lambda: defaultdict(int))
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sid = r["BAC_CORP_PAR_IMS_ORG_ID"]
            sysinfo.setdefault(sid, (r["BAC_CORP_PAR_NM"], r["BAC_CORP_PAR_ST_CD"], r["BAC_CORP_PAR_ORG_TYP_DESC"]))
            if T12_FROM <= r["MTH_ID"] <= T12_TO:
                doses[sid][r["VAC_PROD_CLAS_NM"] or "Unclassified"] += int(float(r["DOSES"]))
    metrics = PM.load(path)
    out = []
    for sid in sorted(sysinfo):
        name, st, org = sysinfo[sid]
        cd = tuple(sorted(((c, d) for c, d in doses[sid].items() if d > 0), key=lambda x: (-x[1], x[0])))
        out.append(SystemProfile(sid, name, st, org, cd, metrics[sid]))
    return out


FIXTURE_CLASSES = ("Pneumococcal", "Meningococcal", "Influenza", "HPV", "Tdap", "Hepatitis")
# class -> (subclass, [(brand, manufacturer), ...]); real public names are allowed in generated data (D-0043)
FIXTURE_CATALOG = {
    "Pneumococcal": ("Pneumococcal", [("PREVNAR 20", "PFIZER"), ("VAXNEUVANCE", "MERCK")]),
    "Meningococcal": ("MenACWY", [("MENVEO", "GSK"), ("MENQUADFI", "SANOFI")]),
    "Influenza": ("Influenza", [("FLUZONE", "SANOFI"), ("FLUARIX", "GSK")]),
    "HPV": ("HPV", [("GARDASIL 9", "MERCK")]),
    "Tdap": ("Tdap", [("BOOSTRIX TDAP", "GSK"), ("ADACEL", "SANOFI")]),
    "Hepatitis": ("HepB", [("ENGERIX-B", "GSK"), ("HEPLISAV-B", "DYNAVAX")]),
}
FIXTURE_SPECS = ("General Acute", "Women's Health", "Pediatrics")


def fixture_rows(p: SystemProfile) -> list:
    """Hand-checkable rows for one fixture system: per class, its T12 doses (class_doses) in 202601 (T12, the later
    season, the R7 season) split 70/30 over the class's brands, and the same class in 202412 (the earlier season)
    split 30/70, so the leading brand gains 40 points between seasons. Dollars = doses x 50."""
    rows = []
    for i, (cls, d12) in enumerate(p.class_doses):
        sub, brands = FIXTURE_CATALOG[cls]
        spec = FIXTURE_SPECS[i % len(FIXTURE_SPECS)]
        splits = [(("202601", d12), (0.7, 0.3)), (("202412", d12), (0.3, 0.7))]
        for (mth, total), w in splits:
            parts = [round(total * x) for x in w[:len(brands)]] if len(brands) > 1 else [total]
            if len(brands) > 1:
                parts[-1] = total - sum(parts[:-1])
            for (brand, mfr), dz in zip(brands, parts):
                rows.append({"MTH_ID": mth, "PROD_NM": brand, "MFR_NM": mfr, "VAC_PROD_CLAS_NM": cls,
                             "VAC_PROD_SUBCLAS_NM": sub, "VAC_AGE_GRP_NM": "Adult", "BAC_CHNL_SPEC_DESC": spec,
                             "BAC_CORP_PAR_ORG_TYP_DESC": p.org_type, "DOSES": str(dz), "DOLLARS": f"{dz * 50}.00",
                             "BAC_CORP_PAR_IMS_ORG_ID": p.system_id, "BAC_CORP_PAR_NM": p.name,
                             "BAC_CORP_PAR_ST_CD": p.state_cd, "BAC_OWN_SUBS_IMS_ORG_ID": "",
                             "DDD_OTLT_NBR": f"9{p.system_id[-5:]}{i}"})
    return rows


def fixture_systems(n: int = 12, seed: int = 7) -> list:
    rng = random.Random(f"fixture|{seed}")
    base = []
    for i in range(1, n + 1):
        sid = f"SYNCP9{i:05d}"
        classes = rng.sample(FIXTURE_CLASSES, 3)
        cd = tuple(sorted(((c, rng.randrange(200, 4000, 10)) for c in classes), key=lambda x: (-x[1], x[0])))
        base.append(SystemProfile(sid, f"Fixture Health System {i:02d}", rng.choice(["CA", "FL", "TX"]),
                                  rng.choice(["IDN", "Corporate Owner"]), cd))
    raw = {}
    for p in base:
        acc, ddd, by_spec = PM.Acc(), set(), defaultdict(set)
        for r in fixture_rows(p):
            acc.add(PM.clean_row(r))
            ddd.add(r["DDD_OTLT_NBR"])
            by_spec[r["BAC_CHNL_SPEC_DESC"]].add(r["DDD_OTLT_NBR"])
        raw[p.system_id] = {"name": p.name, "state": p.state_cd, "type": p.org_type, "acc": acc, "subs": set(),
                            "ddd": ddd, "ddd_by_spec": by_spec}
    met = PM.system_metrics(raw)
    return [SystemProfile(p.system_id, p.name, p.state_cd, p.org_type, p.class_doses, met[p.system_id]) for p in base]
