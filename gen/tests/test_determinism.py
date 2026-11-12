"""T-0028 determinism: same seed -> identical bytes (manifest sha256 over every file)."""
import hashlib

from bia562gen import checks
from bia562gen.generate import generate

from .conftest import SEED


def _run(spec, systems, d, seed):
    generate(spec, systems, d, seed)
    return (d / "manifest.json").read_bytes()


def test_same_seed_identical_bytes(tmp_path, spec, systems):
    m1 = _run(spec, systems, tmp_path / "r1", SEED)
    m2 = _run(spec, systems, tmp_path / "r2", SEED)
    assert hashlib.sha256(m1).hexdigest() == hashlib.sha256(m2).hexdigest()
    assert checks.manifest_ok(tmp_path / "r1") == [] and checks.manifest_ok(tmp_path / "r2") == []


def test_comparison_can_fail_different_seed(tmp_path, spec, systems):
    # negative control: the comparison above is not vacuous
    assert _run(spec, systems, tmp_path / "a", SEED) != _run(spec, systems, tmp_path / "b", SEED + 1)


def test_manifest_detects_tamper(tmp_path, spec, systems):
    d = tmp_path / "t"
    generate(spec, systems, d, SEED)
    p = sorted((d / "train" / "docs").glob("*.md"))[0]
    p.write_bytes(p.read_bytes() + b" ")
    assert checks.manifest_ok(d)
