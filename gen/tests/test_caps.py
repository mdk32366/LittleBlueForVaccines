"""T-0017 / T-0023 (generator side) / T-0033: 15,360-byte leaf cap enforced in code; sections <= 1,500 bytes."""
import pytest

from bia562gen import caps, checks, leaves
from bia562gen.caps import CAP, CapError
from bia562gen.generate import generate
from bia562gen.seam import Doc, Section
from bia562gen.specs.schema_stub import StubV0Spec

from .conftest import SEED


def test_output_within_caps(out):
    bad, max_sec, max_leaf = checks.caps_ok(out)
    assert bad == []
    assert max_sec <= caps.SECTION_MAX and max_leaf <= CAP


def test_oversize_leaf_raises(tmp_path):
    lid = "CL-SYN-SYNCP000001-MSA1-4.2"
    head = "---\nid: \"x\"\n---\n"
    text = head + "x" * (CAP + 1 - len(head))
    assert len(text.encode()) == 15361
    with pytest.raises(CapError):
        leaves.guard(tmp_path / "leaves" / f"{lid}.md", lid, text)


def test_leaf_at_cap_passes(tmp_path):
    lid = "CL-SYN-SYNCP000001-MSA1-4.2"
    text = "y" * CAP
    assert len(leaves.guard(tmp_path / f"{lid}.md", lid, text)) == CAP


def test_30kb_section_splits_into_linked_subleaves():
    para = ("Synthetic clause paragraph text. " * 30).strip()
    body = "\n\n".join([para] * 30)
    assert caps.nbytes(body) > 29000
    lv = leaves.clause_leaves("CL-SYN-SYNCP000001-MSA1-4.2", {"file": "f"}, {"anchor": "4.2", "terms": []}, body)
    assert len(lv) >= 3
    for i, (lid, text) in enumerate(lv):
        assert lid.endswith("abcdefghij"[i])
        assert len(text.encode()) <= CAP
        if i + 1 < len(lv):
            assert f'"to": "{lv[i + 1][0]}"' in text and '"rel": "continues"' in text


class BigSection(StubV0Spec):
    def render(self, ds):
        d = super().render(ds)
        s = d.sections[-1]
        return Doc(d.doc_id, d.system_id, d.doc_type, True, d.sections[:-1] + (Section(s.anchor, s.heading, "z" * 1501),))


def test_section_over_1500_raises(tmp_path, systems):
    with pytest.raises(CapError, match="1501 bytes > 1500"):
        generate(BigSection(), systems, tmp_path / "x", SEED)
