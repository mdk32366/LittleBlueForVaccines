"""T-0001 reconcile: per-system F1 sums to the file total to the cent; F2, F3, F4 each sum to F1. Schema fails closed."""
import pandas as pd
import pytest

from brief import config, load


def _check(raw, fsets):
    total = round(float(raw["DOLLARS"].sum()), 2)
    assert round(sum(f.v("F1.dollars") for f in fsets.values()), 2) == total
    assert sum(f.v("F1.doses") for f in fsets.values()) == int(raw["DOSES"].sum())
    for f in fsets.values():
        for sid in ("F2.by_class", "F3.by_facility", "F4.by_mfr"):
            assert round(sum(v for _, v in f.v(sid)), 2) == pytest.approx(f.v("F1.dollars"), abs=0.011), (f.system_id, sid)


def test_reconcile_synthetic_file(raw_df, real_facts):
    assert len(real_facts) == 180
    _check(raw_df, real_facts)


def test_reconcile_fixture(fixture_csv, fixture_facts):
    _check(load.load_csv(fixture_csv), fixture_facts)


def test_returns_netted_and_reported(raw_df, real_facts):
    neg = raw_df[raw_df["DOLLARS"] < 0]
    assert len(neg) == 299 and round(float(neg["DOLLARS"].sum()), 2) == -1285193.13  # §1 clean rules figures
    assert round(sum(f.v("F8.returns_dollars") for f in real_facts.values()), 2) == 1285193.13


def test_schema_fails_closed(tmp_path, fixture_csv):
    df = pd.read_csv(fixture_csv).drop(columns=["DOSES"])
    p = tmp_path / "bad.csv"
    df.to_csv(p, index=False)
    with pytest.raises(load.SchemaError):
        load.load_csv(p)


def test_input_matches_gen_manifest():
    assert load.sha256_file(config.DATA_PATH) == load.gen_manifest_input_sha(config.GEN_OUT)
