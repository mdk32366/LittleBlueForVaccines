"""T-0037 benchmark modes (D-0034 (national file public-real)): default synthetic peers; national mode reads the
national file; a missing national file falls back to synthetic peers with a note; bad mode / schema fail closed."""
import pandas as pd
import pytest

from brief import benchmark as bm, facts


def test_default_is_synthetic(monkeypatch, real_df):
    monkeypatch.delenv("BENCHMARK", raising=False)
    b = bm.resolve(real_df)
    assert b.mode == "synthetic" and b.label == "synthetic peers" and b.note == ""


def test_national_mode(real_df):
    b = bm.resolve(real_df, "national")
    assert b.mode == "national" and b.label == "national" and b.path.endswith(bm.NATIONAL_FILE)
    raw = bm.load_national(b.path)
    assert b.total_dollars == float(raw["DOLLARS"].sum())
    fs = facts.compute_all(real_df, b)["SYNCP000025"]
    assert round(fs.v("F6.bench_ratio"), 2) == 0.54
    assert fs.facts["F1.bench_share"].source_label == "national"
    assert fs.facts["F1.rank"].source_label == "synthetic peers"  # national file has no systems


def test_missing_national_falls_back(tmp_path, real_df, monkeypatch):
    monkeypatch.setenv("NATIONAL_PATH", str(tmp_path / "nope.csv"))
    b = bm.resolve(real_df, "national")
    assert b.mode == "synthetic" and "fell back" in b.note
    fs = facts.compute_all(real_df, b)["SYNCP000025"]
    assert fs.benchmark == "synthetic" and fs.benchmark_note


def test_bad_mode_raises(monkeypatch):
    monkeypatch.setenv("BENCHMARK", "local")
    with pytest.raises(ValueError):
        bm.requested_mode()


def test_national_schema_fails_closed(tmp_path):
    p = tmp_path / "n.csv"
    pd.DataFrame({"MTH_ID": ["202410"], "DOSES": [1]}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="missing"):
        bm.national(p)
