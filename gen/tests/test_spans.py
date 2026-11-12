"""T-0029 every answer span (and TermSet span) is verbatim in its anchor clause; anchors stay in-system."""
import dataclasses
import json

import pytest

from bia562gen import checks
from bia562gen.generate import GenerationError, generate
from bia562gen.specs.schema_stub import StubV0Spec

from .conftest import SEED


def test_all_spans_verbatim(out):
    assert checks.spans_verbatim(out) == []


def test_checker_flags_corrupted_span(tmp_path, out):
    import shutil
    d = tmp_path / "c"
    shutil.copytree(out, d)
    qa = (d / "train" / "qa.jsonl").read_text().splitlines()
    rec = json.loads(next(l for l in qa if '"int"' in l))
    rec["spans"]["S1"]["text"] = rec["spans"]["S1"]["text"].replace(",", "") + "5"  # "1,200" -> "12005"-style miss
    qa[0] = json.dumps(rec)
    (d / "train" / "qa.jsonl").write_text("\n".join(qa) + "\n")
    assert checks.spans_verbatim(d)


class WrongSpan(StubV0Spec):
    def qa(self, ds):
        out = []
        for q in super().qa(ds):
            if q.answer_type == "int" and q.spans:
                s1 = dataclasses.replace(q.spans["S1"], text="1,250")
                q = dataclasses.replace(q, spans={"S1": s1})
            out.append(q)
        return out


def test_generator_refuses_non_verbatim_span(tmp_path, systems):
    with pytest.raises(GenerationError, match="not verbatim"):
        generate(WrongSpan(), systems, tmp_path / "x", SEED)


class CrossSystem(StubV0Spec):
    def qa(self, ds):
        qs = super().qa(ds)
        q = next(x for x in qs if x.spans)
        other = q.spans["S1"].anchor.replace(ds.system_id, "SYNCP999999")
        s1 = dataclasses.replace(q.spans["S1"], anchor=other)
        return [dataclasses.replace(q, spans={"S1": s1}, source_anchor=other)] + qs[1:]


def test_generator_refuses_cross_system_anchor(tmp_path, systems):
    with pytest.raises(GenerationError, match="not this system"):
        generate(CrossSystem(), systems, tmp_path / "x", SEED)


def test_checker_flags_legacy_single_span_field(tmp_path, out):
    import shutil
    d = tmp_path / "legacy"
    shutil.copytree(out, d)
    qa = (d / "train" / "qa.jsonl").read_text().splitlines()
    rec = json.loads(qa[0])
    rec["span"] = rec["spans"]["S1"]["text"]  # G-04: the dropped §7.7 single-span form must not come back
    qa[0] = json.dumps(rec)
    (d / "train" / "qa.jsonl").write_text("\n".join(qa) + "\n")
    assert any("non-canonical" in v for v in checks.spans_verbatim(d))
