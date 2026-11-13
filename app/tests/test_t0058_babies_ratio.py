"""T-0058 babies ratio (client email 2026-11-13, AS-0056): private (DTaP / 5) over total (Varicella / 2), shown for
the system, synthetic in-state peers and national. Mutation: babies_swap (private and total swapped)."""
from pytest import approx


def test_fixture_hand_values(metrics_facts):
    assert metrics_facts["SYNCP900008"].v("F11.private_share") == approx((100 / 5) / (100 / 2) * 100)
    fs = metrics_facts["SYNCP900001"]
    assert (fs.v("F11.private_share"), fs.v("F11.private_share_state")) == approx((50.0, 40.0))


def test_national_pin_and_levels(real_client):
    fs = real_client["SYNCP000025"]
    assert round(fs.v("F11.private_share_nat") / 100, 3) == 0.641
    assert fs.v("F11.private_share") == approx(57.5) and round(fs.v("F11.private_share_state"), 2) == 63.13
