"""T-0021 (extended): split by system AND family; no system in both train and test."""
import shutil

from bia562gen import checks

import json


def test_no_system_in_both_splits(out):
    assert checks.systems_disjoint(out) == []
    m = json.loads((out / "manifest.json").read_text())
    assert m["split"]["train"]["systems"] and m["split"]["test"]["systems"]


def test_split_by_family(out):
    assert checks.families_by_split(out) == []


def test_checker_flags_planted_overlap(tmp_path, out):
    d = tmp_path / "c"
    shutil.copytree(out, d)
    src = sorted((d / "test" / "docs").glob("*-MSA1.md"))[0]
    shutil.copy(src, d / "train" / "docs" / src.name)
    assert checks.systems_disjoint(d)
