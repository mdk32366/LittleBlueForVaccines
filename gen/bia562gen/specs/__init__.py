"""Spec registry: config picks the version (§7.2). schema_v1 = one new module + one line here (or --spec module:Class)."""
import importlib

REGISTRY = {
    "stub-v0": "bia562gen.specs.schema_stub:StubV0Spec",
    # "v1": "bia562gen.specs.schema_v1:SchemaV1Spec",   # Matt's spec drops in here
}


def load_spec(name_or_path: str):
    target = REGISTRY.get(name_or_path, name_or_path)
    if ":" not in target:
        raise KeyError(f"unknown spec {name_or_path!r}; known: {sorted(REGISTRY)} or module:Class")
    mod, cls = target.split(":", 1)
    spec = getattr(importlib.import_module(mod), cls)()
    from ..seam import ContractSpec
    if not isinstance(spec, ContractSpec):
        raise TypeError(f"{target} does not implement ContractSpec")
    return spec
