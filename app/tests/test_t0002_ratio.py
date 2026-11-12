"""T-0002 ratio edge: MenACWY=0 -> "undefined" (never inf or a crash); below 50 doses -> "insufficient volume"."""
import math

from brief import facts


def test_rule():
    assert facts.ratio_status(80, 0) == (None, "undefined")
    assert facts.ratio_status(0, 0) == (None, "undefined")
    assert facts.ratio_status(30, 100) == (None, "insufficient volume")
    r, s = facts.ratio_status(120, 200)
    assert s == "ok" and r == 0.6


def test_fixture_cases(fixture_facts):
    assert fixture_facts["SYNCP800003"].v("F6.status") == "undefined"
    assert "F6.ratio" not in fixture_facts["SYNCP800003"].facts
    assert fixture_facts["SYNCP800002"].v("F6.status") == "insufficient volume"
    assert fixture_facts["SYNCP800001"].v("F6.status") == "ok"
    assert fixture_facts["SYNCP800001"].v("F6.state_status") == "too few in-state peers"


def test_synthetic_file_counts(real_facts):
    st = [f.v("F6.status") for f in real_facts.values()]
    assert st.count("undefined") == 4 and st.count("ok") == 102  # §1 F6 figures
    for f in real_facts.values():
        for k in ("F6.ratio", "F6.index_vs_bench", "F6.index_vs_state", "F6.bench_ratio"):
            if k in f.facts:
                assert f.v(k) is not None and math.isfinite(f.v(k))
    assert round(next(iter(real_facts.values())).v("F6.bench_ratio"), 3) == 0.661  # 16,302 / 24,674
