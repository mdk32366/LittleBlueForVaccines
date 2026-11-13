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


# --- v0.2: pooled client-metric components (AS-0042 (client field mapping), AS-0043 (comparators)) -------------------
# One aggregation is used at every level (system, pooled in-state peers, pooled national file), so the three columns
# can never drift apart. Every component is an additive sum, so pooled peers are the sum of the peers' components.
# The sets below are read at call time (red-proof mutations patch them in tests only).
R1_NUM_SUBCLASSES = ("MenB", "MenABCWY")        # R1 numerator, the client's "MenB + MenABCWY"
ACWY_SUBCLASSES = ("MenACWY", "MenABCWY")       # R1/R2 denominator, the client's "Men ACWY + MenABCWY"
OBGYN_SPECIALTY = "Women's Health"              # the client's "OBGYN offices" (AS-0042 (client field mapping))
R7_PRODUCT = "BOOSTRIX TDAP"
R7_SEASON = ("202510", "202603")                # latest full Oct-Mar season, spec §3.2 R7 (AS-0046 (season windows), logged with PR 6)
_BLANKABLE = ("VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "MFR_NM", "BAC_CHNL_SPEC_DESC")


def _sum_by(d: pd.DataFrame, cols, value: str) -> dict:
    if d.empty:
        return {}
    g = d.groupby(cols)[value].sum()
    return {k: float(v) for k, v in g.items()}


def pooled(d: pd.DataFrame) -> dict:
    """Additive components of the client's attributes and ratios for any set of rows (net of returns)."""
    C, U, A, P = d["VAC_PROD_CLAS_NM"], d["VAC_PROD_SUBCLAS_NM"], d["VAC_AGE_GRP_NM"], d["PROD_NM"]
    doses = d["DOSES"]

    def sd(mask) -> float:
        return float(doses[mask].sum())

    m = d["MTH_ID"]
    season = (m >= R7_SEASON[0]) & (m <= R7_SEASON[1]) & (d["BAC_CHNL_SPEC_DESC"] == OBGYN_SPECIALTY)
    return {
        "rows": int(len(d)), "dollars": float(d["DOLLARS"].sum()), "doses": float(doses.sum()),
        "cls_dollars": _sum_by(d, "VAC_PROD_CLAS_NM", "DOLLARS"),
        "spec_dollars": _sum_by(d, "BAC_CHNL_SPEC_DESC", "DOLLARS"),
        "mfr_dollars": _sum_by(d, "MFR_NM", "DOLLARS"),
        "type_dollars": _sum_by(d, "BAC_CORP_PAR_ORG_TYP_DESC", "DOLLARS"),
        "cls_spec_doses": _sum_by(d, ["VAC_PROD_CLAS_NM", "BAC_CHNL_SPEC_DESC"], "DOSES"),
        "menb_abcwy": sd(U.isin(list(R1_NUM_SUBCLASSES))), "acwy_abcwy": sd(U.isin(list(ACWY_SUBCLASSES))),
        "hpv": sd(C == "HPV"), "flu": sd(C == "Influenza"), "covid": sd(U == "COVID Vaccine"),
        "shingles": sd(C == "Shingles"), "flu_adult": sd((C == "Influenza") & (A == "Adult")),
        "rsv": sd(U == "RSV Vaccine"), "hepb": sd(U == "HepB"), "hepb_ped": sd((U == "HepB") & (A == "Ped")),
        "varicella": sd(C == "Varicella"), "dtap": sd(C == "DTaP"),
        "age_ped": sd(A == "Ped"), "age_adult": sd(A == "Adult"), "age_mixed": sd(A == "Mixed"),
        "r7_boostrix": sd(season & (P == R7_PRODUCT)), "r7_flu": sd(season & (C == "Influenza")),
        "r7_rsv": sd(season & (U == "RSV Vaccine")),
    }


def add_pooled(a: dict, b: dict) -> dict:
    """Sum two component dicts (nested dicts are summed key by key)."""
    out = {}
    for k in set(a) | set(b):
        x, y = a.get(k), b.get(k)
        if isinstance(x, dict) or isinstance(y, dict):
            x, y = x or {}, y or {}
            out[k] = {kk: x.get(kk, 0.0) + y.get(kk, 0.0) for kk in set(x) | set(y)}
        else:
            out[k] = (x or 0) + (y or 0)
    return out


def national_profile(path=None) -> dict | None:
    """Pooled national components from the national file (benchmark only, D-0034 (national file public-real); never
    training input, T-0025). None when the file is missing; the caller shows that instead of a number."""
    p = Path(path) if path else national_path()
    if not p.exists():
        return None
    d = load_national(p)
    for c in _BLANKABLE:  # same rule as clean.clean on the synthetic file
        d[c] = d[c].where(d[c].str.strip() != "", "Unclassified")
    prof = pooled(d)
    prof["path"] = str(p)
    return prof
