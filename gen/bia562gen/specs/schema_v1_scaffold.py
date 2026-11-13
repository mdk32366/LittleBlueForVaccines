"""schema_v1 scaffold (not registered; copy to specs/schema_v1.py at the GATE 2 drop-in order and fill in).

Path 1, catalog and/or template text change only: subclass StubV0Spec, set spec_version, CATALOG and TEMPLATES.
Path 2, structural change (new doc types, sections or Q&A shapes): implement seam.ContractSpec directly.
Either way: register it as "v1" in specs/__init__.py (already there), set gen/config.json {"spec": "v1"}, and run
`python tools/check_spec.py --spec v1` before regenerating. Field names the app reads (APP_REQUIRED in conformance.py)
and AS-0041 (schema_v1 keeps auto_renew boolean in term section) are hard gates; a rename goes to the Architect.

Mapping table (fill from the incoming fake-data spec; one row per catalog field):
    v1 field name        -> catalog name used here      type   unit   clause_type     notes
    ...
"""
from __future__ import annotations

from .schema_stub import CATALOG_V0, StubV0Spec
from .templates_stub import FAMILIES


class SchemaV1Scaffold(StubV0Spec):
    spec_version = "schema-v1-scaffold"  # the real module uses its own version string; it keys the per-system RNG
    families = ("A", "B")
    CATALOG = CATALOG_V0  # replace with the schema_v1 catalog rows
    TEMPLATES = FAMILIES  # replace with schema_v1 template families (A train, B test; disjoint text, T-0031)
