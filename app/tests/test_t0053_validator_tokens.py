"""T-0053 validator token widening (spec §2): fact tokens F1..F14 are accepted; F0, F15 and above stay malformed.
Mutation: tok_wide (any F-number accepted)."""
from brief import validator


def test_accepts_f1_to_f14():
    for fid in ("F1.dollars", "F8.returns_rows", "F9.share_nat", "F10.n_ddd", "F13.r1", "F14.x"):
        assert validator.validate(f"Value {{{fid}}}.", [fid]).ok, fid


def test_rejects_f0_f15_and_above():
    for fid in ("F0.x", "F15.x", "F19.x", "F99.r1", "F140.x"):
        r = validator.validate(f"Value {{{fid}}}.", [fid])
        assert not r.ok and any("malformed" in x for x in r.reasons), fid


def test_unknown_widened_id_still_rejected():
    assert not validator.validate("Value {F13.r1}.", ["F13.r2"]).ok
