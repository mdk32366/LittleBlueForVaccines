"""T-0022 (generator slice): a toy 3-field spec runs through the unchanged generator via module path only."""
from bia562gen import checks
from bia562gen.generate import generate
from bia562gen.seam import ContractSpec
from bia562gen.specs import load_spec


def test_stub_implements_protocol(spec):
    assert isinstance(spec, ContractSpec) and spec.spec_version == "stub-v0"
    assert {c["name"] for c in spec.field_catalog()} >= {"expiration_date", "tier_min_doses", "admin_fee_pct"}


def test_toy_spec_end_to_end(tmp_path, systems):
    toy = load_spec("tests.toy_spec:ToySpec")
    d = tmp_path / "toy"
    m = generate(toy, systems, d, 562)
    assert m["spec_version"] == "toy-3"
    assert checks.spans_verbatim(d) == [] and checks.systems_disjoint(d) == []
    assert checks.family_b_leak(d, toy) == [] and checks.manifest_ok(d) == []
    assert checks.answers_digit_free(d) == []


def test_unknown_spec_rejected():
    import pytest
    with pytest.raises(KeyError):
        load_spec("schema_v1")
