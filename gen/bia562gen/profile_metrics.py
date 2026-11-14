"""schema_v1 profile metrics (stdlib only): the app's client attributes and ratios (app/brief/client_metrics.py,
benchmark.pooled) recomputed from the (fake, D-0022 (fake data)) synthetic file in one pass, so EXH1 states the same
figures as the Brief. Parity with the app is a test (app/tests, T-0064), not a hope.

Rules kept from the app: the FULL window 202410-202609 for every attribute, the R7 Women's Health season 202510-202603,
returns netted into totals, a blank class / subclass / manufacturer / specialty read as "Unclassified" (clean.py),
the ratio rule AS-0044 (ratio rule), in-state peers per AS-0031 / AS-0043 (comparators) (at least five, the system
itself excluded) and the field mapping AS-0042 (client field mapping). Dollars are summed exactly (integer units of
1e-5), so the totals do not depend on row order.

Also computed here, for the contract and the switching section (not app figures):
- dollars by class x manufacturer and class x brand (the counterparty and covered brands, D-0044 (real manufacturer as the contract party));
- T12 class doses (tiers and commitments keep T12, AS-0024);
- brand and manufacturer dose shares within a class for the same-season windows 202410-202503 and 202510-202603
  (the Q7 default; AS-0064 (same-season switching)), each manufacturer- or brand-window floored at zero like the app's F5.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal

FULL = ("202410", "202609")
T12 = ("202510", "202609")
R7_SEASON = ("202510", "202603")
SEASONS = (("202410", "202503"), ("202510", "202603"))  # same-season switching windows (Q7 default)
BLANKABLE = ("VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "MFR_NM", "BAC_CHNL_SPEC_DESC")
R1_NUM = ("MenB", "MenABCWY")
ACWY = ("MenACWY", "MenABCWY")
OBGYN = "Women's Health"
R7_PRODUCT = "BOOSTRIX TDAP"
MIN_RATIO_DEN = 50
MIN_STATE_PEERS = 5
DOLLAR_SCALE = 100000  # DOLLARS carry at most five decimals in both files
SID = "BAC_CORP_PAR_IMS_ORG_ID"

SCALAR_KEYS = ("menb_abcwy", "acwy_abcwy", "hpv", "flu", "covid", "shingles", "flu_adult", "rsv", "hepb", "hepb_ped",
               "varicella", "dtap", "age_ped", "age_adult", "age_mixed", "r7_boostrix", "r7_flu", "r7_rsv", "r7_tdap")
MAP_KEYS = ("cls_dollars", "spec_dollars", "mfr_dollars", "type_dollars", "brand_dollars", "cls_spec_doses",
            "cls_mfr_dollars", "cls_brand_dollars", "t12_cls_doses", "sw1_cls_brand", "sw2_cls_brand", "sw1_cls_mfr",
            "sw2_cls_mfr")
DOLLAR_MAPS = ("cls_dollars", "spec_dollars", "mfr_dollars", "type_dollars", "brand_dollars", "cls_mfr_dollars",
               "cls_brand_dollars")


def to_units(s: str) -> int:
    return int(Decimal(s.strip() or "0") * DOLLAR_SCALE)


def to_doses(s: str) -> int:
    d = Decimal(s.strip() or "0")
    if d != d.to_integral_value():
        raise ValueError(f"DOSES {s!r} is not a whole number")
    return int(d)


def clean_row(r: dict) -> dict:
    r = dict(r)
    for c in BLANKABLE:
        if c in r and r[c].strip() == "":
            r[c] = "Unclassified"
    return r


class Acc:
    """Additive components for one set of rows (a system, a peer pool or the national file)."""

    def __init__(self):
        self.rows = 0
        self.units = 0  # dollars x DOLLAR_SCALE
        self.doses = 0
        self.s = {k: 0 for k in SCALAR_KEYS}
        self.m = {k: defaultdict(int) for k in MAP_KEYS}
        self.brand_mfr = {}

    def add(self, r: dict):
        m, c, u, a, p = r["MTH_ID"], r["VAC_PROD_CLAS_NM"], r["VAC_PROD_SUBCLAS_NM"], r["VAC_AGE_GRP_NM"], r["PROD_NM"]
        spec, mfr = r["BAC_CHNL_SPEC_DESC"], r["MFR_NM"]
        dol, dz = to_units(r["DOLLARS"]), to_doses(r["DOSES"])
        self.rows += 1
        self.units += dol
        self.doses += dz
        M, S = self.m, self.s
        M["cls_dollars"][c] += dol
        M["spec_dollars"][spec] += dol
        M["mfr_dollars"][mfr] += dol
        M["type_dollars"][r["BAC_CORP_PAR_ORG_TYP_DESC"]] += dol
        M["brand_dollars"][p] += dol
        M["cls_spec_doses"][(c, spec)] += dz
        M["cls_mfr_dollars"][(c, mfr)] += dol
        M["cls_brand_dollars"][(c, p)] += dol
        self.brand_mfr.setdefault(p, mfr)
        if T12[0] <= m <= T12[1]:
            M["t12_cls_doses"][c] += dz
        for i, (lo, hi) in enumerate(SEASONS, 1):
            if lo <= m <= hi:
                M[f"sw{i}_cls_brand"][(c, p)] += dz
                M[f"sw{i}_cls_mfr"][(c, mfr)] += dz
        if u in R1_NUM:
            S["menb_abcwy"] += dz
        if u in ACWY:
            S["acwy_abcwy"] += dz
        S["hpv"] += dz if c == "HPV" else 0
        S["flu"] += dz if c == "Influenza" else 0
        S["covid"] += dz if u == "COVID Vaccine" else 0
        S["shingles"] += dz if c == "Shingles" else 0
        S["flu_adult"] += dz if (c == "Influenza" and a == "Adult") else 0
        S["rsv"] += dz if u == "RSV Vaccine" else 0
        S["hepb"] += dz if u == "HepB" else 0
        S["hepb_ped"] += dz if (u == "HepB" and a == "Ped") else 0
        S["varicella"] += dz if c == "Varicella" else 0
        S["dtap"] += dz if c == "DTaP" else 0
        S["age_ped"] += dz if a == "Ped" else 0
        S["age_adult"] += dz if a == "Adult" else 0
        S["age_mixed"] += dz if a == "Mixed" else 0
        if R7_SEASON[0] <= m <= R7_SEASON[1] and spec == OBGYN:
            S["r7_boostrix"] += dz if p == R7_PRODUCT else 0
            S["r7_flu"] += dz if c == "Influenza" else 0
            S["r7_rsv"] += dz if u == "RSV Vaccine" else 0
            S["r7_tdap"] += dz if u == "Tdap" else 0

    def __iadd__(self, o: "Acc"):
        self.rows += o.rows
        self.units += o.units
        self.doses += o.doses
        for k in SCALAR_KEYS:
            self.s[k] += o.s[k]
        for k in MAP_KEYS:
            for kk, v in o.m[k].items():
                self.m[k][kk] += v
        for b, mf in o.brand_mfr.items():
            self.brand_mfr.setdefault(b, mf)
        return self

    def pooled(self) -> dict:
        """The app's benchmark.pooled() keys (dollars as float), plus the gen-only maps."""
        out = {"rows": self.rows, "dollars": self.units / DOLLAR_SCALE, "doses": float(self.doses)}
        out.update({k: float(v) for k, v in self.s.items()})
        for k in MAP_KEYS:
            div = DOLLAR_SCALE if k in DOLLAR_MAPS else 1
            out[k] = {kk: v / div for kk, v in sorted(self.m[k].items())}
        out["brand_mfr"] = dict(sorted(self.brand_mfr.items()))
        return out


def read_systems(path) -> dict:
    """One pass over the synthetic file -> {sid: {"name", "state", "type", "acc": Acc, "subs": set, "ddd": set,
    "ddd_by_spec": {spec: set}}}."""
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for raw in csv.DictReader(f):
            r = clean_row(raw)
            sid = r[SID]
            s = out.get(sid)
            if s is None:
                s = out[sid] = {"name": r["BAC_CORP_PAR_NM"], "state": r["BAC_CORP_PAR_ST_CD"],
                                "type": r["BAC_CORP_PAR_ORG_TYP_DESC"], "acc": Acc(), "subs": set(), "ddd": set(),
                                "ddd_by_spec": defaultdict(set)}
            s["acc"].add(r)
            sub = r["BAC_OWN_SUBS_IMS_ORG_ID"]
            if sub.strip() != "":
                s["subs"].add(sub)  # a blank subsidiary is parent-owned (the app's rule, AS-0063 (blank subsidiary is parent-owned)), not a gap
            s["ddd"].add(r["DDD_OTLT_NBR"])
            s["ddd_by_spec"][r["BAC_CHNL_SPEC_DESC"]].add(r["DDD_OTLT_NBR"])
    return out


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return None
    return float(xs[n // 2]) if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def system_metrics(raw: dict) -> dict:
    """{sid: metrics} with the system's pooled components, its counts, and its in-state peer pool (or None)."""
    counts = {sid: {"n_subs": len(s["subs"]), "n_ddd": len(s["ddd"]),
                    "ddd_by_spec": {k: len(v) for k, v in sorted(s["ddd_by_spec"].items())},
                    "type": s["type"], "state": s["state"]} for sid, s in raw.items()}
    out = {}
    for sid in sorted(raw):
        peers = peer_ids(sid, counts)
        pool = None
        if len(peers) >= MIN_STATE_PEERS:
            acc = Acc()
            for p in peers:
                acc += raw[p]["acc"]
            pool = acc.pooled()
        med = None
        if pool is not None:
            med = {"dollars": _median([raw[p]["acc"].units / DOLLAR_SCALE for p in peers]),
                   "n_subs": _median([counts[p]["n_subs"] for p in peers]),
                   "n_ddd": _median([counts[p]["n_ddd"] for p in peers]),
                   "ddd_by_spec": {k: _median([counts[p]["ddd_by_spec"].get(k, 0) for p in peers])
                                   for k in counts[sid]["ddd_by_spec"]}}
        out[sid] = {"system": raw[sid]["acc"].pooled(), "counts": counts[sid], "peers": peers, "state": pool,
                    "state_median": med}
    return out


def peer_ids(sid: str, counts: dict) -> list:
    """In-state peers: every other system with the same parent state (AS-0031); the system itself is excluded."""
    st = counts[sid]["state"]
    return sorted(p for p, c in counts.items() if c["state"] == st and p != sid)


def load(path) -> dict:
    return system_metrics(read_systems(path))


# ---------------- the app's rules (client_metrics.py), value + status ----------------
def ratio_rule(num: float, den: float):
    if den <= 0:
        return None, "undefined"
    if den < MIN_RATIO_DEN:
        return None, "insufficient volume"
    if num < 0:
        return None, "net returns"
    return num / den, "ok"


def share_rule(num: float, den: float):
    if den <= 0:
        return None, "undefined"
    if num < 0:
        return None, "net returns"
    return num / den * 100, "ok"


def state_share(sys_dollars: float, peer_dollars: float):
    tot = sys_dollars + peer_dollars
    if tot <= 0:
        return None, "undefined"
    if sys_dollars < 0:
        return None, "net returns"
    v = sys_dollars / tot
    return (v, "ok") if v <= 1 else (None, "undefined")


INCONSISTENT = "inconsistent (private exceeds total)"


def babies(c: dict) -> dict:
    """A10, the client's heuristic: total = Varicella / two, private = DTaP / five (an estimate)."""
    t, p = c["varicella"] / 2, c["dtap"] / 5
    if t <= 0:
        u = (None, "undefined")
        return {"total": u, "private": u, "public": u, "share": u}
    tot = (t, "ok")
    if p < 0:
        nr = (None, "net returns")
        return {"total": tot, "private": nr, "public": nr, "share": nr}
    if p > t:
        inc = (None, INCONSISTENT)
        return {"total": tot, "private": (p, "ok"), "public": inc, "share": inc}
    return {"total": tot, "private": (p, "ok"), "public": (t - p, "ok"), "share": (p / t * 100, "ok")}


RATIOS = {"R1": ("menb_abcwy", "acwy_abcwy"), "R2": ("hpv", "acwy_abcwy"), "R3": ("flu", "covid"),
          "R4": ("hepb_ped", "dtap"), "R5": ("shingles", "flu_adult"), "R6": ("rsv", "flu_adult"),
          "R7_FLU_TDAP": ("r7_flu", "r7_tdap"), "R7_RSV_TDAP": ("r7_rsv", "r7_tdap")}
AGES = (("ped", "age_ped"), ("adult", "age_adult"), ("mixed", "age_mixed"))


def ratio(c: dict, item: str):
    n, d = RATIOS[item]
    return ratio_rule(c[n], c[d])


def series(sys_map: dict, sys_tot: float, comps: dict, top: int):
    """The app's series_rows for the listed (top-N by system value, then label) items, without the remainder row:
    [{label, system, state, national, idx_state, idx_nat}] with percent shares; None where a total is <= 0."""
    def lab(k):
        return " / ".join(k) if isinstance(k, tuple) else str(k)

    def clamp(x):
        return 0.0 if abs(x) < 1e-9 else x

    def pct(m, tot, k):
        return None if tot <= 0 else clamp(m.get(k, 0.0) / tot * 100)

    keys = sorted(sys_map, key=lambda k: (-sys_map[k], lab(k)))[:top]
    rows = []
    for k in keys:
        r = {"key": k, "label": lab(k), "system": pct(sys_map, sys_tot, k)}
        for lvl, ik in (("state", "idx_state"), ("national", "idx_nat")):
            c = comps.get(lvl)
            r[lvl] = None if c is None else pct(c[0], c[1], k)
            r[ik] = (r["system"] / r[lvl] * 100 if r["system"] is not None and r[lvl] and r[lvl] > 0 else None)
        rows.append(r)
    return rows


def window_shares(c: dict, cls: str, kind: str = "brand") -> dict:
    """{name: (share_w1, share_w2)} in percent of the class's doses in each same-season window (None if the class
    has no positive volume in that window). Each name-window is floored at zero first (as the app's F5)."""
    out = {}
    w = []
    for i in (1, 2):
        m = {k[1]: max(0.0, float(v)) for k, v in c[f"sw{i}_cls_{kind}"].items() if k[0] == cls}
        w.append(m)
    names = sorted(set(w[0]) | set(w[1]))
    tots = [sum(m.values()) for m in w]
    for n in names:
        out[n] = tuple((w[i].get(n, 0.0) / tots[i] * 100) if tots[i] > 0 else None for i in (0, 1))
    return out


SWITCH_POINTS = 15.0  # the Q7 default: a share change of at least fifteen points


def largest_gain(c: dict, cls: str):
    """(brand, gain points) for the brand with the largest share gain >= SWITCH_POINTS between the two same-season
    windows (ties by name), or ("steady", None); ("no volume", None) when either window has no class volume."""
    sh = window_shares(c, cls)
    if not sh or any(v[0] is None or v[1] is None for v in sh.values()):
        return "no volume", None
    best = sorted(((s2 - s1, n) for n, (s1, s2) in sh.items()), key=lambda x: (-x[0], x[1]))[0]
    return (best[1], best[0]) if best[0] >= SWITCH_POINTS else ("steady", None)
