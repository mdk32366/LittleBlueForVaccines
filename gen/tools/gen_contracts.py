#!/usr/bin/env python3
"""python tools/gen_contracts.py --seed 562 --out out/ [--spec stub-v0|module:Class] [--systems-csv PATH | --fixture N]"""
import argparse, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bia562gen import systems as S  # noqa: E402
from bia562gen.generate import generate  # noqa: E402
from bia562gen.specs import load_spec  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=562)
ap.add_argument("--out", required=True)
ap.add_argument("--spec", default=None, help="registry name or module:Class; default from config.json")
ap.add_argument("--systems-csv", default=None)
ap.add_argument("--fixture", type=int, default=0)
ap.add_argument("--overwrite", action="store_true")
a = ap.parse_args()
root = Path(__file__).resolve().parents[1]
spec_name = a.spec or json.loads((root / "config.json").read_text())["spec"]
spec = load_spec(spec_name)
if a.fixture:
    systems, src = S.fixture_systems(a.fixture), {"kind": "fixture", "n": a.fixture}
else:
    csv = Path(a.systems_csv or root.parent / "data" / "BIA_562_Synthetic_Sales_Data.csv")
    systems = S.load_csv(csv)
    src = {"kind": "csv", "file": csv.name, "sha256": hashlib.sha256(csv.read_bytes()).hexdigest()}
m = generate(spec, systems, a.out, a.seed, overwrite=a.overwrite, systems_source=src)
print(json.dumps({"seed": m["seed"], "spec_version": m["spec_version"], "counts": m["counts"],
                  "files": len(m["files"])}, indent=1))
print("manifest.sha256:", (Path(a.out) / "manifest.sha256").read_text().strip())
