"""T-0055 R4 HepB Ped, the client's interim definition (client email 2026-11-13, AS-0053): Doses(subclass HepB and
age group Ped) / Doses(class DTaP), under the AS-0044 (ratio rule). Synthetic HepB Ped is 0 in every system, so the
system value is a computed 0, never an estimate. Mutation: r4_def (numerator back to all HepB doses)."""
from pytest import approx

from brief import availability as av


def test_fixture_hand_value(metrics_facts):
    fs = metrics_facts["SYNCP900008"]
    assert fs.v("F13.r4") == approx(20 / 100)
    assert fs.v("F13.r4_st") == "ok" and fs.v("F13.r4_state_st") == "too few in-state peers"


def test_national_pin(real_client):
    fs = real_client["SYNCP000025"]
    assert round(fs.v("F13.r4_nat"), 4) == 0.5956          # 6,711,748 / 11,269,199
    assert av.status("R4.national") == av.DERIVED


def test_synthetic_system_level(real_client):
    st = [f.v("F13.r4_st") for f in real_client.values()]
    assert st.count("ok") == 179 and st.count("insufficient volume") == 1
    assert {f.v("F13.r4") for f in real_client.values() if "F13.r4" in f.facts} == {0.0}
