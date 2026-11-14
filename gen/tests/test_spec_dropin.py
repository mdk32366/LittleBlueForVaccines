"""T-0063 (schema_v1 drop-in conformance): specs/conformance.py gates a candidate spec
on the seam, the app's field names and AS-0041 (schema_v1 keeps auto_renew boolean in term section). Bad candidates
are built here from the stub by subclassing; no production code knows them."""
import dataclasses

import pytest

from bia562gen import checks
from bia562gen.generate import generate
from bia562gen.seam import Field, Source
from bia562gen.specs import REGISTRY, SpecNotDroppedIn, load_spec, schema_stub
from bia562gen.specs.conformance import check_spec
from bia562gen.specs.schema_v1_scaffold import SchemaV1Scaffold


class _AutoRenewString(schema_stub.StubV0Spec):
    spec_version = "bad-str"

    def terms(self, ds):
        ts = super().terms(ds)
        f = dict(ts.fields)
        if "auto_renew" in f:
            f["auto_renew"] = dataclasses.replace(f["auto_renew"], value="yes" if f["auto_renew"].value else "no")
        return dataclasses.replace(ts, fields=f)


class _AutoRenewElsewhere(schema_stub.StubV0Spec):
    spec_version = "bad-sec"

    def terms(self, ds):
        ts = super().terms(ds)
        f = dict(ts.fields)
        if "auto_renew" in f and "termination_for_convenience" in f:
            t = f["termination_for_convenience"]
            f["auto_renew"] = Field(f["auto_renew"].value, "enum", Source(t.source.doc_id, t.source.anchor), t.span)
        return dataclasses.replace(ts, fields=f)


class _AutoRenewDropped(schema_stub.StubV0Spec):
    spec_version = "bad-drop"
    CATALOG = [r for r in schema_stub.CATALOG_V0 if r[0] != "auto_renew"]

    def terms(self, ds):
        ts = super().terms(ds)
        return dataclasses.replace(ts, fields={k: v for k, v in ts.fields.items() if k != "auto_renew"})


def test_stub_conforms(spec):
    errs, warns = check_spec(spec)
    assert errs == [] and warns == [], (errs, warns)


def test_scaffold_conforms_and_generates(tmp_path, systems):
    s = SchemaV1Scaffold()
    assert check_spec(s)[0] == []
    m = generate(s, systems, tmp_path / "v1", 562)
    assert m["spec_version"] == "schema-v1-scaffold"
    assert checks.manifest_ok(tmp_path / "v1") == [] and checks.spans_verbatim(tmp_path / "v1") == []


@pytest.mark.parametrize("bad,needle", [(_AutoRenewString, "not bool"), (_AutoRenewElsewhere, "not the expiration_date section"),
                                        (_AutoRenewDropped, "no auto_renew")], ids=["str", "section", "dropped"])
def test_as0041_violations_rejected(bad, needle):
    errs, _ = check_spec(bad())
    assert any(needle in e for e in errs), errs


def test_app_field_rename_rejected():
    class Renamed(schema_stub.StubV0Spec):
        spec_version = "bad-name"
        CATALOG = [("end_date",) + r[1:] if r[0] == "expiration_date" else r for r in schema_stub.CATALOG_V0]
    errs, _ = check_spec(Renamed())
    assert any("lacks expiration_date" in e for e in errs), errs


def test_toy_spec_is_not_a_contract_spec_for_the_app():
    errs, _ = check_spec(load_spec("tests.toy_spec:ToySpec"))
    assert any("lacks MSA" in e for e in errs) and any("lacks expiration_date" in e for e in errs), errs


def test_v1_registry_slot():
    assert REGISTRY["v1"] == "bia562gen.specs.schema_v1:SchemaV1Spec"
    try:
        v1 = load_spec("v1")
    except SpecNotDroppedIn:
        return  # pre-drop-in: registered, absent, clear error
    errs, _ = check_spec(v1)  # post-drop-in: the real module must pass the same gates
    assert errs == [], errs
