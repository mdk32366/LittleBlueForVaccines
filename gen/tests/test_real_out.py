"""Same guards run against the committed-style run in gen/out (seed 562, synthetic CSV). Skips if absent."""
import hashlib
import json
from pathlib import Path

import pytest

from bia562gen import checks, systems as S
from bia562gen.generate import generate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
CSV = ROOT.parent / "data" / "BIA_562_Synthetic_Sales_Data.csv"
pytestmark = pytest.mark.skipif(not (OUT / "manifest.json").exists(), reason="gen/out not generated")


def test_real_manifest_and_hashes():
    assert checks.manifest_ok(OUT) == []


def test_real_regeneration_identical(tmp_path, spec):
    if not CSV.exists():
        pytest.skip("synthetic CSV absent")
    src = {"kind": "csv", "file": CSV.name, "sha256": hashlib.sha256(CSV.read_bytes()).hexdigest()}
    m = json.loads((OUT / "manifest.json").read_text())
    generate(spec, S.load_csv(CSV), tmp_path / "re", m["seed"], systems_source=src)
    regen, accepted = (tmp_path / "re" / "manifest.json").read_bytes(), (OUT / "manifest.json").read_bytes()
    # Compare digests, not raw bytes: pytest's full diff of two ~400 KB blobs never finishes under CI=true
    # (no assertion truncation on CI), which hung the redproof famsplit run in GitHub Actions.
    if regen != accepted:
        a, b = json.loads(regen).get("files", {}), json.loads(accepted).get("files", {})
        differing = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        pytest.fail(f"regeneration differs from gen/out: {len(differing)} files differ, e.g. {differing[:5]}", pytrace=False)
    assert hashlib.sha256(regen).hexdigest() == hashlib.sha256(accepted).hexdigest()


def test_real_guards(spec):
    assert checks.spans_verbatim(OUT) == []
    assert checks.answers_digit_free(OUT) == []
    assert checks.systems_disjoint(OUT) == []
    assert checks.families_by_split(OUT) == []
    assert checks.family_b_leak(OUT, spec) == []
    assert checks.caps_ok(OUT)[0] == []
    assert checks.synthetic_stamp(OUT) == []
    r = checks.unanswerable_rate(OUT)
    assert min(r.values()) >= 0.15
