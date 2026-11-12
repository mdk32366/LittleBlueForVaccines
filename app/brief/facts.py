"""facts.py: F1..F8 per system + synthetic-peers benchmark (§1). pandas owns every number (§3 D-0001 (hybrid, facts first))."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

import pandas as pd

from . import benchmark as bm, config, switching

PFIZER = "PFIZER"  # manufacturer value in the synthetic file; F4 highlights it (§1)
MIN_RATIO_DOSES = 50
MIN_STATE_PEERS = 5
SID = "BAC_CORP_PAR_IMS_ORG_ID"


@dataclass(frozen=True)
class Fact:
    fact_id: str
    value: object
    unit: str          # usd | doses | pct | ratio | index | int | label | series
    period: str
    n: int
    source_label: str  # "synthetic peers" for benchmark-derived facts (T-0008); "system" otherwise


@dataclass
class FactSheet:
    fs_id: str
    system_id: str
    name: str
    state: str
    as_of: str
    benchmark: str = "synthetic"
    benchmark_label: str = config.BENCH_LABEL
    benchmark_note: str = ""
    facts: dict = field(default_factory=dict)  # fact_id -> Fact

    def add(self, f: Fact):
        if f.fact_id in self.facts:
            raise ValueError(f"duplicate fact {f.fact_id}")
        if f.unit == "usd":
            f = Fact(f.fact_id, round(float(f.value), 2), f.unit, f.period, f.n, f.source_label)
        elif f.unit == "series" and f.fact_id in ("F2.by_class", "F3.by_facility", "F4.by_mfr"):
            f = Fact(f.fact_id, [(k, round(v, 2)) for k, v in f.value], f.unit, f.period, f.n, f.source_label)
        self.facts[f.fact_id] = f

    def v(self, fid):
        return self.facts[fid].value

    def scalar_ids(self):
        return sorted(k for k, f in self.facts.items() if f.unit != "series")

    def to_json(self) -> str:
        return json.dumps({"fs_id": self.fs_id, "system_id": self.system_id, "name": self.name, "state": self.state,
                           "as_of": self.as_of, "benchmark": self.benchmark, "benchmark_label": self.benchmark_label,
                           "benchmark_note": self.benchmark_note, "facts": [asdict(f) for f in self.facts.values()]},
                          indent=1, default=float, sort_keys=False)


def ratio_status(menb: float, menacwy: float):
    """F6 / T-0002: MenACWY = 0 -> undefined; either below 50 doses -> insufficient volume; never inf."""
    if menacwy <= 0:
        return None, "undefined"
    if menb < MIN_RATIO_DOSES or menacwy < MIN_RATIO_DOSES:
        return None, "insufficient volume"
    return menb / menacwy, "ok"


def _period(p):
    return f"{p[0]}-{p[1]}"


def compute_all(df: pd.DataFrame, bench: "bm.Benchmark | None" = None) -> dict:
    """bench: the live benchmark (default synthetic peers). Peer facts (rank, in-state) are always synthetic peers."""
    bench = bench or bm.synthetic(df)
    full = _period(config.FULL_PERIOD)
    B, S = config.BENCH_LABEL, config.SYSTEM_LABEL
    L = bench.label  # source_label for facts measured against the live benchmark
    sys_info = df.groupby(SID).agg(name=("BAC_CORP_PAR_NM", "first"), state=("BAC_CORP_PAR_ST_CD", "first"),
                                   rows=("DOLLARS", "size"), dollars=("DOLLARS", "sum"), doses=("DOSES", "sum"))
    n_sys = len(sys_info)
    bench_total = bench.total_dollars
    rank = sys_info["dollars"].rank(ascending=False, method="min").astype(int)
    by_cls = df.groupby([SID, "VAC_PROD_CLAS_NM"])["DOLLARS"].sum()
    by_fac = df.groupby([SID, "BAC_CHNL_SPEC_DESC"])["DOLLARS"].sum()
    by_mfr = df.groupby([SID, "MFR_NM"])["DOLLARS"].sum()
    sub = df.pivot_table(index=SID, columns="VAC_PROD_SUBCLAS_NM", values="DOSES", aggfunc="sum", fill_value=0)
    for c in ("MenB", "MenACWY", "MenABCWY"):
        if c not in sub.columns:
            sub[c] = 0
    bench_ratio, bench_status = ratio_status(bench.menb_doses, bench.menacwy_doses)
    m = df["MTH_ID"]
    t12 = df[(m >= config.T12[0]) & (m <= config.T12[1])].groupby([SID, "VAC_PROD_CLAS_NM"])["DOLLARS"].sum()
    p12 = df[(m >= config.P12[0]) & (m <= config.P12[1])].groupby([SID, "VAC_PROD_CLAS_NM"])["DOLLARS"].sum()
    ret = df[df["DOLLARS"] < 0].groupby(SID)["DOLLARS"].agg(["sum", "size"])
    flags = switching.flags_all(df)
    states = sys_info["state"]
    out = {}
    for sid, info in sys_info.iterrows():
        fs = FactSheet(f"FS-{sid}-{config.AS_OF}", sid, info["name"], info["state"], config.AS_OF,
                       benchmark=bench.mode, benchmark_label=bench.label, benchmark_note=bench.note)
        n = int(info["rows"])
        dollars = float(info["dollars"])
        # F1 size
        fs.add(Fact("F1.dollars", dollars, "usd", full, n, S))
        fs.add(Fact("F1.doses", int(info["doses"]), "doses", full, n, S))
        fs.add(Fact("F1.rank", int(rank[sid]), "int", full, n_sys, B))
        fs.add(Fact("F1.n_systems", n_sys, "int", full, n_sys, B))
        fs.add(Fact("F1.bench_share", dollars / bench_total * 100, "pct", full, n_sys, L))
        # F2 class (top 5 + Other)
        c = by_cls.loc[sid].sort_values(ascending=False)
        series = [(k, float(v)) for k, v in c.head(5).items()]
        if len(c) > 5:
            series.append(("Other", float(c.iloc[5:].sum())))
        fs.add(Fact("F2.by_class", series, "series", full, n, S))
        fs.add(Fact("F2.top_class", c.index[0], "label", full, n, S))
        fs.add(Fact("F2.top_class_share", float(c.iloc[0]) / dollars * 100, "pct", full, n, S))
        # F3 facility type (BAC_CHNL_SPEC_DESC, AS-0031)
        f3 = by_fac.loc[sid].sort_values(ascending=False)
        fs.add(Fact("F3.by_facility", [(k, float(v)) for k, v in f3.items()], "series", full, n, S))
        fs.add(Fact("F3.top_facility", f3.index[0], "label", full, n, S))
        fs.add(Fact("F3.top_facility_share", float(f3.iloc[0]) / dollars * 100, "pct", full, n, S))
        # F4 manufacturer, Pfizer highlighted
        f4 = by_mfr.loc[sid].sort_values(ascending=False)
        pf = float(f4.get(PFIZER, 0.0))
        fs.add(Fact("F4.by_mfr", [(k, float(v)) for k, v in f4.items()], "series", full, n, S))
        fs.add(Fact("F4.top_mfr", f4.index[0], "label", full, n, S))
        fs.add(Fact("F4.pfizer_dollars", pf, "usd", full, n, S))
        fs.add(Fact("F4.pfizer_share", pf / dollars * 100, "pct", full, n, S))
        # F5 switching
        fl = flags.get(sid, [])
        win = f"{_period(config.W1)} vs {_period(config.W2)}"
        fs.add(Fact("F5.flags", fl, "series", win, len(fl), S))
        fs.add(Fact("F5.n_flags", len(fl), "int", win, len(fl), S))
        fs.add(Fact("F5.status", "flagged" if fl else "no material switching", "label", win, len(fl), S))
        if fl:
            t = fl[0]
            fs.add(Fact("F5.top_class", t["class"], "label", win, t["n_w1"] + t["n_w2"], S))
            fs.add(Fact("F5.top_mfr", t["mfr"], "label", win, t["n_w1"] + t["n_w2"], S))
            fs.add(Fact("F5.top_from", t["share_w1"], "pct", win, t["n_w1"], S))
            fs.add(Fact("F5.top_to", t["share_w2"], "pct", win, t["n_w2"], S))
        # F6 MenB:MenACWY
        mb, ma, mabc = (float(sub.loc[sid, k]) if sid in sub.index else 0.0 for k in ("MenB", "MenACWY", "MenABCWY"))
        r, st = ratio_status(mb, ma)
        fs.add(Fact("F6.menb_doses", int(mb), "doses", full, n, S))
        fs.add(Fact("F6.menacwy_doses", int(ma), "doses", full, n, S))
        fs.add(Fact("F6.menabcwy_doses", int(mabc), "doses", full, n, S))
        fs.add(Fact("F6.status", st, "label", full, n, S))
        fs.add(Fact("F6.bench_ratio", bench_ratio, "ratio", full, n_sys, L))
        if r is not None:
            fs.add(Fact("F6.ratio", r, "ratio", full, n, S))
            fs.add(Fact("F6.index_vs_bench", r / bench_ratio * 100 if bench_ratio else None, "index", full, n_sys, L))
        peers = [p for p in states.index[states == info["state"]] if p != sid]
        if len(peers) < MIN_STATE_PEERS:
            fs.add(Fact("F6.state_status", "too few in-state peers", "label", full, len(peers), B))
        else:
            sr, sst = ratio_status(float(sub.loc[peers, "MenB"].sum()), float(sub.loc[peers, "MenACWY"].sum()))
            fs.add(Fact("F6.state_status", sst, "label", full, len(peers), B))
            if sr is not None:
                fs.add(Fact("F6.state_ratio", sr, "ratio", full, len(peers), B))
                if r is not None:
                    fs.add(Fact("F6.index_vs_state", r / sr * 100, "index", full, len(peers), B))
        # F7 trailing 12 vs prior 12 by class
        a = t12.loc[sid] if sid in t12.index.get_level_values(0) else pd.Series(dtype=float)
        b = p12.loc[sid] if sid in p12.index.get_level_values(0) else pd.Series(dtype=float)
        cls = sorted(set(a.index) | set(b.index))
        f7 = [(k, float(a.get(k, 0.0)), float(b.get(k, 0.0))) for k in cls]
        per = f"{_period(config.T12)} vs {_period(config.P12)}"
        ta, tb = float(a.sum()), float(b.sum())
        fs.add(Fact("F7.by_class", f7, "series", per, n, S))
        fs.add(Fact("F7.t12_dollars", ta, "usd", _period(config.T12), n, S))
        fs.add(Fact("F7.p12_dollars", tb, "usd", _period(config.P12), n, S))
        if tb > 0:
            fs.add(Fact("F7.growth_pct", (ta - tb) / tb * 100, "pct", per, n, S))
        if f7:
            delta = sorted(f7, key=lambda x: (-(x[1] - x[2]), x[0]))
            fs.add(Fact("F7.top_grower", delta[0][0], "label", per, n, S))
            fs.add(Fact("F7.top_decliner", delta[-1][0], "label", per, n, S))
        # F8 returns
        rs, rn = (float(ret.loc[sid, "sum"]), int(ret.loc[sid, "size"])) if sid in ret.index else (0.0, 0)
        fs.add(Fact("F8.returns_dollars", abs(rs), "usd", full, rn, S))
        fs.add(Fact("F8.returns_rows", rn, "int", full, rn, S))
        out[sid] = fs
    return out
