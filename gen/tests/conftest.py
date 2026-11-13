"""Shared fixtures + REDPROOF mutations.

REDPROOF=<name> pytest ...  applies ONE deliberate defect at session start (test-side monkeypatch only; no
production code knows about it) so tools/redproof.py can prove each guard test goes red.
"""
import dataclasses
import os
import random

import pytest

from bia562gen import caps, generate as G, vault_guard
from bia562gen.specs import conformance, load_spec, schema_stub, templates_stub
from bia562gen.systems import fixture_systems

SEED = 562
B_FRAGMENT = "Products within its reach: "


def _noop(*a, **k):
    return None


def apply_mutation(name):
    if name == "nondet":
        G.make_rng = lambda key: random.Random(key + os.urandom(8).hex())
    elif name == "span":
        G.validate_bundle = _noop
        orig = schema_stub.StubV0Spec.qa

        def bad_qa(self, ds):
            out = []
            for q in orig(self, ds):
                if q.spans:
                    s1 = q.spans["S1"]
                    s1 = dataclasses.replace(s1, text=s1.text + "9")
                    q = dataclasses.replace(q, spans={"S1": s1})
                out.append(q)
            return out
        schema_stub.StubV0Spec.qa = bad_qa
    elif name == "digits":
        G.validate_bundle = _noop
        templates_stub.FAMILIES["A"]["answers"]["expiration_date"] = "It expires in 2027, on {S1}."
    elif name == "overlap":
        orig_split = G.split_systems

        def bad_split(ids, seed, frac=0.25):
            s = orig_split(ids, seed, frac)
            return {"train": sorted(set(s["train"]) | set(s["test"][:1])), "test": s["test"]}
        G.split_systems = bad_split
        G.assert_disjoint = _noop
    elif name == "famsplit":
        G.FAMILY_OF_SPLIT["test"] = "A"
    elif name == "leak":
        c = templates_stub.FAMILIES["A"]["clauses"]
        c["other"] = c["other"] + " " + B_FRAGMENT + "none."
    elif name == "cap":
        caps.check_leaf = lambda leaf_id, data: len(data)
        caps.check_section = lambda doc_id, anchor, text: len(text)
    elif name == "vault":
        for fn in ("check_path", "check_leaf_id", "check_body", "check_vendored_dir", "check_leaf"):
            setattr(vault_guard, fn, _noop)
    elif name == "unans":
        G.MIN_UNANSWERABLE = 0.0
        orig = schema_stub.StubV0Spec.qa
        schema_stub.StubV0Spec.qa = lambda self, ds: [q for q in orig(self, ds) if q.answer_type != "unanswerable"]
    elif name == "barestamp":  # the stamp goes back to a bare decision number
        G.STAMP = "> SYNTHETIC DOCUMENT. Fictional test data generated for BIA 562 (D-0022). Not a real agreement or proposal."
    elif name == "dropin_as0041":  # the schema_v1 drop-in gate stops checking AS-0041
        conformance.check_auto_renew = lambda doc_id, fields, sections: []
    elif name == "dropin_appfields":  # the drop-in gate stops checking the app's field names
        conformance.check_app_fields = lambda spec: ([], [])
    elif name:
        raise ValueError(f"unknown REDPROOF mutation {name}")


def pytest_configure(config):
    apply_mutation(os.environ.get("REDPROOF", ""))


@pytest.fixture(scope="session")
def spec():
    return load_spec("stub-v0")


@pytest.fixture(scope="session")
def systems():
    return fixture_systems(12)


@pytest.fixture(scope="session")
def out(tmp_path_factory, spec, systems):
    d = tmp_path_factory.mktemp("gen") / "out"
    G.generate(spec, systems, d, SEED, systems_source={"kind": "fixture", "n": 12})
    return d
