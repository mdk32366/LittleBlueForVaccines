"""T-0042 client formulas (spec §3.1-§3.2): A1-A4, A10-A11 and R1-R3, R5-R7 at system / in-state peers / national,
hand-computed on tests/metrics_fixture.py, plus the file pins from the metrics probe. Mutations: kr_abcwy, kr_swap."""
from pytest import approx

from brief import benchmark as bm

S = "SYNCP900001"


def test_ratios_hand_computed(metrics_facts):
    fs = metrics_facts[S]
    want = {"r1": (80 / 120, 500 / 1000, 400 / 800), "r2": (90 / 120, 500 / 1000, 400 / 800),
            "r3": (400 / 100, 2500 / 500, 1000 / 250), "r5": (60 / 300, 250 / 2500, 120 / 600),
            "r6": (30 / 300, 250 / 2500, 60 / 600)}
    for r, (sys_v, state_v, nat_v) in want.items():
        assert fs.v(f"F13.{r}") == approx(sys_v), r
        assert fs.v(f"F13.{r}_state") == approx(state_v), r
        assert fs.v(f"F13.{r}_nat") == approx(nat_v), r
        assert fs.v(f"F13.{r}_idx_state") == approx(sys_v / state_v * 100), r
        assert fs.v(f"F13.{r}_idx_nat") == approx(sys_v / nat_v * 100), r
        assert fs.facts[f"F13.{r}_state"].n == 5 and fs.facts[f"F13.{r}_state"].source_label == "synthetic peers"
        assert fs.facts[f"F13.{r}_nat"].source_label == "national"


def test_r7_women_health_season(metrics_facts):
    fs = metrics_facts[S]
    assert [fs.v(f"F13.r7_{k}") for k in ("boostrix", "flu", "rsv")] == approx([40.0, 40.0, 20.0])
    assert [fs.v(f"F13.r7_{k}_state") for k in ("boostrix", "flu", "rsv")] == approx([100.0, 0.0, 0.0])
    assert [fs.v(f"F13.r7_{k}_nat") for k in ("boostrix", "flu", "rsv")] == approx([60.0, 0.0, 40.0])
    assert fs.facts["F13.r7_boostrix"].period == "202510-202603"


def test_attributes_hand_computed(metrics_facts):
    fs = metrics_facts[S]
    assert fs.v("F1.dollars") == 13300
    assert fs.v("F9.share_state") == approx(13300 / (13300 + 65500))      # A1: share of the state total incl. system
    assert fs.v("F9.peer_median_dollars_state") == 13100                  # A1M: in-state peer median, for scale
    assert "F9.peer_median_dollars_nat" not in fs.facts
    assert fs.v("F9.share_nat") == approx(13300 / 39600 * 100)            # A1 vs national
    cls = {r["label"]: r for r in fs.v("F9.cls_pct")}                     # A2: top five + All other
    assert list(cls) == ["Influenza", "DTaP", "Varicella", "Meningococcal", "Coronavirus", "All other"]
    assert cls["Influenza"]["system"] == approx(4000 / 13300 * 100)
    assert cls["Influenza"]["state"] == approx(25000 / 65500 * 100)
    assert cls["Influenza"]["national"] == approx(10000 / 39600 * 100)
    assert cls["All other"]["system"] == approx(2000 / 13300 * 100)
    assert cls["All other"]["state"] == approx((65500 - 25000 - 5000 - 5000 - 15000 - 5000) / 65500 * 100)
    assert sum(r["system"] for r in cls.values()) == approx(100)
    assert sum(r["national"] for r in cls.values()) == approx(100)
    spec = {r["label"]: r for r in fs.v("F9.spec_pct")}                   # A3
    assert spec["Primary Care"]["system"] == approx(8300 / 13300 * 100)
    assert spec["Women's Health"]["system"] == approx(500 / 13300 * 100)
    assert spec["Pediatric Medicine"]["national"] == approx(10000 / 39600 * 100)
    cells = {r["label"]: r for r in fs.v("F9.cls_spec_dose_pct")}         # A4 (doses)
    assert next(iter(cells)) == "Influenza / Primary Care"
    assert cells["Influenza / Primary Care"]["system"] == approx(380 / 1330 * 100)
    assert cells["DTaP / Pediatric Medicine"]["system"] == approx(250 / 1330 * 100)
    # A10 babies (the client's heuristic) and A11 product age label
    assert (fs.v("F11.babies_total"), fs.v("F11.babies_private"), fs.v("F11.babies_public")) == (100, 50, 50)
    assert fs.v("F11.private_share") == approx(50.0)
    assert fs.v("F11.private_share_state") == approx(100 / 250 * 100)
    assert fs.v("F11.private_share_nat") == approx(120 / 200 * 100)
    assert (fs.v("F11.babies_total_nat"), fs.v("F11.babies_private_nat")) == (200, 120)
    assert (fs.v("F12.ped_share"), fs.v("F12.adult_share"), fs.v("F12.mixed_share")) == approx(
        (450 / 1330 * 100, 490 / 1330 * 100, 390 / 1330 * 100))
    assert fs.v("F12.adult_share_state") == approx(3500 / 6550 * 100)
    assert fs.v("F12.mixed_share_nat") == approx(1930 / 3960 * 100)
    # A5-A9
    assert fs.v("F10.parent_type") == "IDN" and fs.v("F10.parent_state") == "CA"
    assert fs.v("F10.parent_type_share_nat") == approx(31600 / 39600 * 100)
    assert (fs.v("F10.n_subs"), fs.v("F10.n_ddd")) == (2, 3)
    assert (fs.v("F10.n_subs_state"), fs.v("F10.n_ddd_state")) == (1, 2)
    by_spec = {r["label"]: r["system"] for r in fs.v("F10.n_ddd_by_spec")}
    assert by_spec == {"Pediatric Medicine": 2, "Primary Care": 1, "Women's Health": 1}
    assert sum(by_spec.values()) > fs.v("F10.n_ddd")  # the A9 caveat: specialty is per row, not per outlet


def test_national_file_pins(real_national, real_client):
    n = real_national
    fs = real_client["SYNCP000025"]  # the implementation's national column (same for every system)
    pins = {"r1": 0.5483, "r2": 1.2570, "r3": 5.6960, "r5": 0.1928, "r6": 0.0802}
    assert {r: round(fs.v(f"F13.{r}_nat"), 4) for r in pins} == pins
    assert round(fs.v("F11.private_share_nat") / 100, 3) == 0.641
    assert round(n["menb_abcwy"] / n["acwy_abcwy"], 4) == 0.5483                 # R1 (F6 is 0.541, MenB/MenACWY)
    assert round(n["hpv"] / n["acwy_abcwy"], 4) == 1.2570                        # R2
    assert round(n["flu"] / n["covid"], 4) == 5.6960                             # R3
    assert round(n["shingles"] / n["flu_adult"], 4) == 0.1928                    # R5
    assert round(n["rsv"] / n["flu_adult"], 4) == 0.0802                         # R6
    assert n["hepb_ped"] == 6711748 and round(n["hepb_ped"] / n["hepb"], 3) == 0.469
    assert n["varicella"] / 2 == 3514862.5 and round(n["dtap"] / 5, 1) == 2253839.8
    assert round(n["dtap"] / 5 / (n["varicella"] / 2), 3) == 0.641
    assert round(n["age_ped"] / n["doses"], 4) == 0.1546 and round(n["age_adult"] / n["doses"], 4) == 0.1927
    assert round(n["age_mixed"] / n["doses"], 4) == 0.6525   # blank age rows are in the total (F-0014 note)
    assert n["rows"] == 45462 and round(n["dollars"] / 1e9, 2) == 29.42


def test_syncp000025_pins(real_client, real_df):
    fs = real_client["SYNCP000025"]
    c = bm.pooled(real_df[real_df["BAC_CORP_PAR_IMS_ORG_ID"] == "SYNCP000025"])
    assert (c["menb_abcwy"], c["acwy_abcwy"]) == (150, 240) and fs.v("F13.r1") == 150 / 240
    assert fs.v("F13.r1_state") == 952 / 1144 and fs.facts["F13.r1_state"].n == 7
    assert round(fs.v("F13.r1_nat"), 4) == 0.5483
    assert fs.state == "FL" and fs.v("F10.parent_type") == "IDN"
