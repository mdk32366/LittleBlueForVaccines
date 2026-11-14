"""Readers over a schema_v1 output tree (tests only)."""
import json
import re
from pathlib import Path

from bia562gen import checks

SPLITS = ("train", "test")


def terms(out, kind):
    """{system_id: {field_key: field}} for every <doc>-<KIND>1.terms.json."""
    res = {}
    for sp in SPLITS:
        for p in sorted((Path(out) / sp / "docs").glob(f"*-{kind}1.terms.json")):
            res[p.name.split("-")[1]] = json.loads(p.read_text())["fields"]
    return res


def docs(out, kind=None):
    res = {}
    for sp in SPLITS:
        for did, v in checks.load_docs(out, sp).items():
            if kind is None or re.search(rf"-{kind}\d+$", did):
                res[did] = v
    return res


def qa(out):
    return [q for sp in SPLITS for q in checks.load_qa(out, sp)]


def base(key):
    return re.sub(r"-\d+$", "", key)
