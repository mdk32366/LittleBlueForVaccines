"""T-0004 validator trips (§4) + T-0013 commercial guardrail cases (§7.6, D-0009 (advisory verb + commercial term))."""
from brief import narrative, render, validator

KNOWN = ["F4.pfizer_share", "F1.dollars", "C3.tier2_min"]


def bad(t):
    return not validator.validate(t, KNOWN).ok


def test_t0004_trips():
    assert bad("Pfizer share is 54%.")
    assert bad("Share is {F9.x}.")
    assert bad("Prevnar is safer.")
    assert bad("offer a 5% discount")
    assert bad("You should charge more.")


def test_t0013_trips():
    assert bad("Pfizer should offer a higher rebate tier")
    assert bad("Recommend lowering the admin fee")


def test_clean_text_passes():
    assert validator.validate("Pfizer holds {F4.pfizer_share} of {F1.dollars}.", KNOWN).ok


def test_every_brief_passes_and_stays_clean(real_facts):
    for fs in real_facts.values():
        n = narrative.compose(fs)
        assert n.source == "templated"
        text = " ".join(n.rendered) + " " + render.footer_text(fs)
        assert not validator.CLINICAL.search(text), fs.system_id
        for s in validator.SENT.split(text):
            assert not (validator.ADVISORY.search(s) and validator.COMMERCIAL.search(s)), (fs.system_id, s)
