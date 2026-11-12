#!/usr/bin/env python3
"""python cli.py --system SYNCP000025 --out evidence/reports/   |   --all"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brief import benchmark as bm, clean, config, facts, load, report  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--system", action="append", default=[])
ap.add_argument("--all", action="store_true")
ap.add_argument("--out", required=True)
ap.add_argument("--benchmark", choices=["synthetic", "national"], default=None)
ap.add_argument("--factsheet", action="store_true", help="also write the FactSheet JSON")
a = ap.parse_args()
df = clean.clean(load.load_csv(config.DATA_PATH))
fsets = facts.compute_all(df, bm.resolve(df, a.benchmark))
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
for sid in (sorted(fsets) if a.all else a.system):
    _n, _r, pdf = report.build(fsets[sid])
    (out / f"little-blue-{sid}.pdf").write_bytes(pdf)
    if a.factsheet:
        (out / f"FS-{sid}-{config.AS_OF}.json").write_text(fsets[sid].to_json() + "\n")
    print(out / f"little-blue-{sid}.pdf")
