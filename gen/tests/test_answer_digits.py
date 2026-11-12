"""T-0030 no digits in answer text (D-0020 rule 1; slot tokens {S1}.. excepted, see gap G-03)."""
import json
import shutil

import pytest

from bia562gen import checks
from bia562gen.generate import GenerationError, answer_has_digit, generate
from bia562gen.specs import templates_stub

from .conftest import SEED


def test_no_digits_in_any_answer(out):
    assert checks.answers_digit_free(out) == []


def test_rule_itself():
    assert answer_has_digit("expires in 2027")
    assert answer_has_digit("Tier 2 at {S1}")
    assert not answer_has_digit("The MSA expires on {S1}; that tier starts at {S2} doses.")


def test_checker_flags_injected_digit(tmp_path, out):
    d = tmp_path / "c"
    shutil.copytree(out, d)
    qa = (d / "test" / "qa.jsonl").read_text().splitlines()
    rec = json.loads(qa[0])
    rec["answer"] = "expires in 2027"
    qa[0] = json.dumps(rec)
    (d / "test" / "qa.jsonl").write_text("\n".join(qa) + "\n")
    assert checks.answers_digit_free(d)


def test_generator_refuses_digit_answer(tmp_path, spec, systems, monkeypatch):
    monkeypatch.setitem(templates_stub.FAMILIES["A"]["answers"], "effective_date", "Starts in 2025 on {S1}.")
    with pytest.raises(GenerationError, match="digit"):
        generate(spec, systems, tmp_path / "x", SEED)
