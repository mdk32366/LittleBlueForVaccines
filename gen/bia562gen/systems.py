"""System profiles: from the (fake, D-0022 (fake data)) synthetic sales CSV, or a seeded fixture for tests."""
import csv
import random
from collections import defaultdict

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
    out = []
    for sid in sorted(sysinfo):
        name, st, org = sysinfo[sid]
        cd = tuple(sorted(((c, d) for c, d in doses[sid].items() if d > 0), key=lambda x: (-x[1], x[0])))
        out.append(SystemProfile(sid, name, st, org, cd))
    return out


FIXTURE_CLASSES = ("Pneumococcal", "Meningococcal", "Influenza", "HPV", "Tdap", "Hepatitis")


def fixture_systems(n: int = 12, seed: int = 7) -> list:
    rng = random.Random(f"fixture|{seed}")
    out = []
    for i in range(1, n + 1):
        sid = f"SYNCP9{i:05d}"
        classes = rng.sample(FIXTURE_CLASSES, 3)
        cd = tuple(sorted(((c, rng.randrange(200, 4000, 10)) for c in classes), key=lambda x: (-x[1], x[0])))
        out.append(SystemProfile(sid, f"Fixture Health System {i:02d}", rng.choice(["CA", "FL", "TX"]),
                                 rng.choice(["IDN", "Corporate Owner"]), cd))
    return out
