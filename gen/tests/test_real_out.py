"""Same guards run against the committed run in gen/out (seed 562, synthetic CSV, the spec in config.json: schema_v1
since GATE 2). Skips if absent (CI fails on any skip)."""
import hashlib
import json
from pathlib import Path

import pytest

from bia562gen import checks

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
CSV = ROOT.parent / "data" / "BIA_562_Synthetic_Sales_Data.csv"
pytestmark = pytest.mark.skipif(not (OUT / "manifest.json").exists(), reason="gen/out not generated")


def test_real_manifest_and_hashes():
    assert checks.manifest_ok(OUT) == []


def test_real_regeneration_identical(v1_out):
    """T-0028 on the committed data: the in-process regeneration (conftest v1_out, the config.json spec, seed 562)
    is byte-identical to gen/out."""
    m = json.loads((OUT / "manifest.json").read_text())
    assert m["seed"] == 562 and json.loads((ROOT / "config.json").read_text())["spec"] == "v1"
    regen, accepted = (v1_out / "manifest.json").read_bytes(), (OUT / "manifest.json").read_bytes()
    # Compare digests, not raw bytes: pytest's full diff of two ~400 KB blobs never finishes under CI=true
    # (no assertion truncation on CI), which hung the redproof famsplit run in GitHub Actions.
    if regen != accepted:
        a, b = json.loads(regen).get("files", {}), json.loads(accepted).get("files", {})
        differing = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        pytest.fail(f"regeneration differs from gen/out: {len(differing)} files differ, e.g. {differing[:5]}", pytrace=False)
    assert hashlib.sha256(regen).hexdigest() == hashlib.sha256(accepted).hexdigest()


def test_real_guards(v1_spec):
    spec = v1_spec
    assert checks.spans_verbatim(OUT) == []
    assert checks.answers_digit_free(OUT) == []
    assert checks.systems_disjoint(OUT) == []
    assert checks.families_by_split(OUT) == []
    assert checks.family_b_leak(OUT, spec) == []
    assert checks.caps_ok(OUT)[0] == []
    assert checks.synthetic_stamp(OUT) == []
    r = checks.unanswerable_rate(OUT)
    assert min(r.values()) >= 0.15
