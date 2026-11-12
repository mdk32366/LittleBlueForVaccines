"""T-0031 no family-B template text appears anywhere in train."""
import shutil

from bia562gen import checks

from .conftest import B_FRAGMENT


def test_no_family_b_text_in_train(out, spec):
    assert checks.family_b_leak(out, spec) == []


def test_b_fragments_exist(spec):
    # guard against a vacuous pass: the check must have real B text to look for
    assert len(checks.b_ngrams(spec)) >= 200


def test_checker_flags_planted_b_text(tmp_path, out, spec):
    d = tmp_path / "c"
    shutil.copytree(out, d)
    p = sorted((d / "train" / "docs").glob("*-MSA1.md"))[0]
    p.write_text(p.read_text() + B_FRAGMENT + "\n")
    assert checks.family_b_leak(d, spec)


def test_checker_flags_b_heading(tmp_path, out, spec):
    d = tmp_path / "h"
    shutil.copytree(out, d)
    p = sorted((d / "train" / "docs").glob("*-MSA1.md"))[0]
    p.write_text(p.read_text() + "## 9. Miscellany\n\nx\n")
    assert checks.family_b_leak(d, spec)


def test_template_families_disjoint(spec):
    assert checks.template_overlap(spec) == []
