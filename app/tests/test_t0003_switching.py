"""T-0003 switching red-first: the planted switch flags, the noise system does not; synthetic flag rate < 50%."""
from brief import switching


def test_planted_switch_flags(fixture_facts):
    fl = fixture_facts["SYNCP800001"].v("F5.flags")
    assert fl and {(f["class"], f["mfr"]) for f in fl} >= {("Pneumococcal", "PFIZER")}
    pf = [f for f in fl if f["mfr"] == "PFIZER"][0]
    assert round(pf["share_w1"]) == 80 and round(pf["share_w2"]) == 30


def test_noise_does_not_flag(fixture_facts):
    assert fixture_facts["SYNCP800002"].v("F5.status") == "no material switching"
    assert fixture_facts["SYNCP800003"].v("F5.n_flags") == 0


def test_flag_rate_synthetic_under_half(real_facts):
    flagged = sum(1 for f in real_facts.values() if f.v("F5.n_flags") > 0)
    rate = flagged / len(real_facts)
    print(f"T-0003 flag rate: {flagged}/{len(real_facts)} = {rate:.1%}")
    assert rate < 0.50
    assert all(f.v("F5.n_flags") <= switching.MAX_FLAGS for f in real_facts.values())
