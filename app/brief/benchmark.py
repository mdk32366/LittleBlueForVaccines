"""benchmark.py (§0 item 1: pluggable benchmark). Modes:
- "synthetic" (DEFAULT and fallback): the synthetic peer set, computed from the loaded sales file.
- "national": 'BIA 562 National System Data.csv', public-real per D-0034 (national file public-real).
  It has no system or state columns, so only national totals and the national MenB:MenACWY ratio come from it;
  rank and in-state peers always stay on synthetic peers (and say so in their source_label).
If national is requested but the file is missing, the brief falls back to synthetic peers and records why.
The national file is never a training or generator input (T-0025, see brief/train_guard.py)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config

NATIONAL_FILE = "BIA 562 National System Data.csv"
NATIONAL_COLUMNS = ["MTH_ID", "PROD_NM", "MFR_NM", "VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "VAC_AGE_GRP_NM",
                    "VAC_FRZ_IND", "SEASON_DESC", "BAC_CHNL_SPEC_DESC", "BAC_CORP_PAR_ORG_TYP_DESC", "DOSES", "DOLLARS"]
SYNTHETIC_LABEL = config.BENCH_LABEL      # "synthetic peers"
NATIONAL_LABEL = "national"


@dataclass(frozen=True)
class Benchmark:
    mode: str            # "synthetic" | "national"
    label: str           # source_label written on benchmark-derived facts
    total_dollars: float
    menb_doses: float
    menacwy_doses: float
    path: str | None
    note: str            # e.g. fallback reason


def national_path() -> Path:
    env = os.environ.get("NATIONAL_PATH")
    if env:
        return Path(env)
    return config._default_data(NATIONAL_FILE)  # <repo>/data/, else legacy <repo>/ fallback


def requested_mode() -> str:
    m = os.environ.get("BENCHMARK", config.BENCHMARK)
    if m not in ("synthetic", "national"):
        raise ValueError(f"BENCHMARK must be synthetic or national, got {m!r}")
    return m


def synthetic(df: pd.DataFrame, note: str = "") -> Benchmark:
    s = df.groupby("VAC_PROD_SUBCLAS_NM")["DOSES"].sum()
    return Benchmark("synthetic", SYNTHETIC_LABEL, float(df["DOLLARS"].sum()), float(s.get("MenB", 0)),
                     float(s.get("MenACWY", 0)), None, note)


def load_national(path) -> pd.DataFrame:
    d = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = [c for c in NATIONAL_COLUMNS if c not in d.columns]
    if missing:
        raise ValueError(f"national file schema: missing {missing}")  # fails closed
    d["DOSES"] = pd.to_numeric(d["DOSES"], errors="raise")
    d["DOLLARS"] = pd.to_numeric(d["DOLLARS"], errors="raise")
    return d


def national(path) -> Benchmark:
    d = load_national(path)
    s = d.groupby("VAC_PROD_SUBCLAS_NM")["DOSES"].sum()
    return Benchmark("national", NATIONAL_LABEL, float(d["DOLLARS"].sum()), float(s.get("MenB", 0)),
                     float(s.get("MenACWY", 0)), str(path), "")


def resolve(df: pd.DataFrame, mode: str | None = None, path=None) -> Benchmark:
    mode = mode or requested_mode()
    if mode == "synthetic":
        return synthetic(df)
    p = Path(path) if path else national_path()
    if not p.exists():
        return synthetic(df, note=f"national file not found at {p}; fell back to synthetic peers")
    return national(p)
