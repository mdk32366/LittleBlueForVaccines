"""T-0044 ratio guards, AS-0044 (ratio rule): denominator <= 0 -> undefined; under fifty -> insufficient volume;
negative numerator -> net returns; never inf or negative. Mutation: ratio_neg."""
import math

from brief import client_metrics as cm


def test_rule_unit_cases():
    assert cm.ratio_rule(80, 0) == (None, "undefined")
    assert cm.ratio_rule(5, -80) == (None, "undefined")
    assert cm.ratio_rule(0, 0) == (None, "undefined")
    assert cm.ratio_rule(10, 49) == (None, "insufficient volume")
    assert cm.ratio_rule(-1, 50) == (None, "net returns")
    assert cm.ratio_rule(25, 50) == (0.5, "ok")
    assert cm.ratio_rule(0, 50) == (0.0, "ok")


def test_fixture_edges(metrics_facts):
    fs = metrics_facts["SYNCP900007"]
    assert fs.v("F13.r1") == 10 / 60
    assert fs.v("F13.r3_st") == "undefined" and "F13.r3" not in fs.facts            # COVID net -80
    assert fs.v("F13.r2_st") == "net returns" and "F13.r2" not in fs.facts          # HPV net -5
    assert fs.v("F13.r5_st") == "insufficient volume" and "F13.r5" not in fs.facts  # adult flu 40
    assert fs.v("F13.r7_boostrix_st") == "undefined"
    assert fs.v("F13.r1_state_st") == "too few in-state peers" and "F13.r1_state" not in fs.facts
    assert fs.v("F11.babies_total") == 10 and fs.v("F11.babies_private") == 20
    assert fs.v("F11.babies_public_st") == cm.INCONSISTENT and "F11.babies_public" not in fs.facts
    assert fs.v("F11.private_share_st") == cm.INCONSISTENT and "F11.private_share" not in fs.facts


def test_real_file_guards(real_client):
    F = list(real_client.values())
    assert real_client["SYNCP000036"].v("F13.r3_st") == "undefined"                  # COVID net -80
    assert sum(f.v("F13.r1_state_st") != "too few in-state peers" for f in F) == 140   # F-0021
    assert sum(f.v("F13.r3_st") == "undefined" for f in F) == 11
    assert sum(f.v("F13.r5_st") == "undefined" for f in F) == 21
    st = [f.v("F11.babies_public_st") for f in F]                                       # F-0017: private > total in 62
    assert st.count(cm.INCONSISTENT) == 61 and real_client["SYNCP000162"].v("F11.babies_total_st") == "undefined"
    for f in F:
        for k, x in f.facts.items():
            if x.unit in ("ratio", "index") and k.startswith("F13."):
                assert x.value is not None and math.isfinite(x.value) and x.value >= 0, (f.system_id, k)
