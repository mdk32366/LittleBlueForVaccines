"""Spec registry: gen/config.json picks the version (§7.2). schema_v1 drop-in = add specs/schema_v1.py (class
SchemaV1Spec, see schema_v1_scaffold.py) and set config.json {"spec": "v1"}; `--spec module:Class` also works.
Check a candidate with `python tools/check_spec.py --spec v1` (specs/conformance.py) before regenerating."""
import importlib
import importlib.util

REGISTRY = {
    "stub-v0": "bia562gen.specs.schema_stub:StubV0Spec",
    "v1": "bia562gen.specs.schema_v1:SchemaV1Spec",  # the schema_v1 drop-in; absent until the GATE 2 order
}


class SpecNotDroppedIn(LookupError):
    pass


def load_spec(name_or_path: str):
    target = REGISTRY.get(name_or_path, name_or_path)
    if ":" not in target:
        raise KeyError(f"unknown spec {name_or_path!r}; known: {sorted(REGISTRY)} or module:Class")
    mod, cls = target.split(":", 1)
    if name_or_path in REGISTRY and importlib.util.find_spec(mod) is None:
        raise SpecNotDroppedIn(f"spec {name_or_path!r} is registered but {mod} is not present yet (drop-in pending)")
    spec = getattr(importlib.import_module(mod), cls)()
    from ..seam import ContractSpec
    if not isinstance(spec, ContractSpec):
        raise TypeError(f"{target} does not implement ContractSpec")
    return spec
