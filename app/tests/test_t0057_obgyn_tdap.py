"""T-0057 OBGYN ratios (client email 2026-11-13, AS-0055): within Women's Health in the Oct-Mar season window
(202510-202603, AS-0046 (season windows)): Influenza / Tdap and RSV Vaccine / Tdap, under AS-0044 (ratio rule).
Mutation: obgyn_spec (the specialty filter moves off Women's Health)."""
from pytest import approx


def test_fixture_hand_values(metrics_facts):
    fs = metrics_facts["SYNCP900008"]
    assert fs.v("F13.r7_flu_tdap") == approx(100 / 50)      # the 202606 Tdap and the Primary Care flu are excluded
    assert fs.v("F13.r7_rsv_tdap") == approx(25 / 50)
    assert fs.facts["F13.r7_flu_tdap"].period == "202510-202603"


def test_national_pins(real_client):
    fs = real_client["SYNCP000025"]
    assert round(fs.v("F13.r7_flu_tdap_nat"), 4) == 0.3452    # 102,450 / 296,785
    assert round(fs.v("F13.r7_rsv_tdap_nat"), 4) == 0.2629    # 78,036 / 296,785


def test_synthetic_statuses(real_client):
    st = [f.v("F13.r7_flu_tdap_st") for f in real_client.values()]
    assert (st.count("ok"), st.count("insufficient volume"), st.count("undefined")) == (5, 14, 161)
