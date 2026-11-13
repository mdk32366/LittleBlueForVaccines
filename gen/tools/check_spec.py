#!/usr/bin/env python3
"""python tools/check_spec.py [--spec stub-v0|v1|module:Class]  -> schema_v1 drop-in conformance (writes nothing).
Exit 0 = no errors (warnings are printed for the Architect); exit 1 = errors, do not regenerate."""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bia562gen.specs import SpecNotDroppedIn, load_spec  # noqa: E402
from bia562gen.specs.conformance import check_spec  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--spec", default=None, help="registry name or module:Class; default from config.json")
ap.add_argument("--systems", type=int, default=12, help="fixture systems per family")
a = ap.parse_args()
name = a.spec or json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())["spec"]
try:
    spec = load_spec(name)
except SpecNotDroppedIn as e:
    print(f"CONFORMANCE: NOT DROPPED IN: {e}")
    sys.exit(2)
errs, warns = check_spec(spec, a.systems)
print(f"spec: {name} -> {type(spec).__module__}.{type(spec).__name__} (spec_version {spec.spec_version!r})")
for w in warns:
    print("WARN ", w)
for e in errs:
    print("ERROR", e)
print(f"CONFORMANCE: {'PASS' if not errs else 'FAIL'} ({len(errs)} errors, {len(warns)} warnings)")
sys.exit(1 if errs else 0)
