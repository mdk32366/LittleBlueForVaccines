"""T-0056 R6 RSV = the full RSV Vaccine subclass, every product (client email 2026-11-13, AS-0054); the older-adult
proxy item is gone from the registry. Mutation: r6_proxy (numerator limited to AREXVY + MRESVIA)."""
from pytest import approx

from brief import availability as av


def test_fixture_counts_every_rsv_product(metrics_facts):
    assert metrics_facts["SYNCP900008"].v("F13.r6") == approx((25 + 15) / 140)


def test_national_pin_and_registry(real_client):
    assert round(real_client["SYNCP000025"].v("F13.r6_nat"), 4) == 0.0802
    assert "R6_OLDER" not in av.ITEMS and av.status("R6.national") == av.DERIVED
