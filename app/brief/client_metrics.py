"""client_metrics.py (v0.2-a): the client's key system attributes (A1-A11) and important ratios (R1-R3, R5-R7; R4 held)
at three levels: the system, its pooled synthetic in-state peers (at least five, AS-0031) and the pooled national file
(D-0034 (national file public-real), benchmark only; never training input, T-0025).

- Fact ids F9 (A1-A4 and highest-dollar shares), F10 (A5-A9), F11 (A10), F12 (A11), F13 (R1-R7). F1-F8 (facts.py)
  are unchanged; these facts are added to the same FactSheet under new ids, so no existing pin moves.
- Level suffixes: system "", state "_state", national "_nat"; "<fid>_st" is the level's status label; indices are
  "<fid>_idx_state" / "<fid>_idx_nat" (index = system / comparator x 100, AS-0044 (ratio rule)).
- Every computation goes through availability.gate(); a NOT AVAILABLE metric gets the status "not available" and no
  value fact, and cell() renders "not available: <reason>", never a number.
Field mapping: AS-0042 (client field mapping). Comparators: AS-0043 (comparators)."""
from __future__ import annotations

import statistics

import pandas as pd

from . import availability as av, benchmark as bm, config, facts
from .facts import Fact, SID
from .fmt import fmt_fact

MIN_RATIO_DEN = 50                       # AS-0044 (ratio rule): denominator of at least fifty net doses
STATE_COLUMN = "synthetic peers (state)"
NATIONAL_COLUMN = "national (D-0034)"
TABLE_COLUMNS = ("metric", "system", f"{STATE_COLUMN} (n)", NATIONAL_COLUMN, "index vs state", "index vs national",
                 "status")
STRIP_COLUMNS = ("attribute", "system", STATE_COLUMN, NATIONAL_COLUMN, "status")
LEVELS = av.LEVELS
SUFFIX = {"system": "", "state": "_state", "national": "_nat"}
IDX = {"state": "_idx_state", "national": "_idx_nat"}
LABEL = {"system": config.SYSTEM_LABEL, "state": config.BENCH_LABEL, "national": bm.NATIONAL_LABEL}
MISSING = {"state": "too few in-state peers", "national": "no national file"}
NA_STATUS = "not available"
INCONSISTENT = "inconsistent (private exceeds total)"
FULL = f"{config.FULL_PERIOD[0]}-{config.FULL_PERIOD[1]}"
R7_PERIOD = f"{bm.R7_SEASON[0]}-{bm.R7_SEASON[1]}"
A2_TOP, A4_TOP = 5, 10

# R1-R3, R5, R6: (numerator component, denominator component) in benchmark.pooled() terms.
RATIOS = {"R1": ("menb_abcwy", "acwy_abcwy"), "R2": ("hpv", "acwy_abcwy"), "R3": ("flu", "covid"),
          "R5": ("shingles", "flu_adult"), "R6": ("rsv", "flu_adult")}
R7_PARTS = (("boostrix", "r7_boostrix", "Boostrix"), ("flu", "r7_flu", "Influenza"), ("rsv", "r7_rsv", "RSV Vaccine"))


def ratio_rule(num: float, den: float):
    """AS-0044 (ratio rule): denominator <= 0 -> undefined; under fifty -> insufficient volume; a negative numerator ->
    net returns; otherwise the ratio. Never inf, never negative."""
    if den <= 0:
        return None, "undefined"
    if den < MIN_RATIO_DEN:
        return None, "insufficient volume"
    if num < 0:
        return None, "net returns"
    return num / den, "ok"


def share_rule(num: float, den: float):
    """A share of a total, in percent: total <= 0 -> undefined; a negative part -> net returns."""
    if den <= 0:
        return None, "undefined"
    if num < 0:
        return None, "net returns"
    return num / den * 100, "ok"


def state_share(sys_dollars: float, peer_dollars: float):
    """A1 state, AS-0043 (comparators): the system's share of the state total INCLUDING the system, as a fraction
    bounded 0 to 1. State total <= 0 -> undefined; negative system dollars -> net returns; above 1 (peers net
    negative) -> undefined."""
    tot = sys_dollars + peer_dollars
    if tot <= 0:
        return None, "undefined"
    if sys_dollars < 0:
        return None, "net returns"
    v = sys_dollars / tot
    return (v, "ok") if v <= 1 else (None, "undefined")


def _babies(c):
    total, private = c["varicella"] / 2, c["dtap"] / 5     # the client's heuristic, A10 (an estimate)
    return total, private


def _b_total(c, s):
    t, _ = _babies(c)
    return (t, "ok") if t > 0 else (None, "undefined")


def _b_private(c, s):
    t, p = _babies(c)
    if t <= 0:
        return None, "undefined"
    return (None, "net returns") if p < 0 else (p, "ok")


def _b_public(c, s):
    t, p = _babies(c)
    if t <= 0:
        return None, "undefined"
    if p < 0:
        return None, "net returns"
    return (None, INCONSISTENT) if p > t else (t - p, "ok")


def _b_share(c, s):
    t, p = _babies(c)
    if t <= 0:
        return None, "undefined"
    if p < 0:
        return None, "net returns"
    return (None, INCONSISTENT) if p > t else (p / t * 100, "ok")


def _ratio(item):
    def f(c, s):
        num, den = RATIOS[item]
        return ratio_rule(c[num], c[den])
    return f


def _r7(comp):
    def f(c, s):
        tot = c["r7_boostrix"] + c["r7_flu"] + c["r7_rsv"]
        v, st = ratio_rule(c[comp], tot)
        return (None if v is None else v * 100), st
    return f


def _age(comp):
    return lambda c, s: share_rule(c[comp], c["doses"])


def _type_share(c, s):  # A5 national: national dollars of this system's parent type, as a share
    t = s["_type"]
    return share_rule(c["type_dollars"].get(t, 0.0), c["dollars"])


# (item, base fact id, unit, levels, period, compute(comparator components, system components) -> (value, status),
#  indexed against comparators)
SCALARS = [
    ("A1", "F9.share", "frac", ("state",), FULL, lambda c, s: state_share(s["dollars"], c["dollars"]), False),
    ("A1", "F9.share", "pct_fine", ("national",), FULL, lambda c, s: share_rule(s["dollars"], c["dollars"]), False),
    ("A5", "F10.parent_type_share", "pct", ("national",), FULL, _type_share, False),
    ("A10", "F11.babies_total", "est", LEVELS, FULL, _b_total, False),
    ("A10", "F11.babies_private", "est", LEVELS, FULL, _b_private, False),
    ("A10", "F11.babies_public", "est", LEVELS, FULL, _b_public, False),
    ("A10", "F11.private_share", "pct", LEVELS, FULL, _b_share, True),
    ("A11", "F12.ped_share", "pct", LEVELS, FULL, _age("age_ped"), True),
    ("A11", "F12.adult_share", "pct", LEVELS, FULL, _age("age_adult"), True),
    ("A11", "F12.mixed_share", "pct", LEVELS, FULL, _age("age_mixed"), True),
] + [(r, f"F13.{r.lower()}", "ratio", LEVELS, FULL, _ratio(r), True) for r in RATIOS] + [
    ("R7", f"F13.r7_{name}", "pct", LEVELS, R7_PERIOD, _r7(comp), True) for name, comp, _ in R7_PARTS]

# Series (A2, A3, A4, highest dollars by manufacturer): (item, fact id, components key, total key, top-N or None)
SERIES = [("A2", "F9.cls_pct", "cls_dollars", "dollars", A2_TOP), ("A3", "F9.spec_pct", "spec_dollars", "dollars", None),
          ("A4", "F9.cls_spec_dose_pct", "cls_spec_doses", "doses", None),
          ("HD", "F9.mfr_pct", "mfr_dollars", "dollars", None)]


def _fid(base, level):
    return base + SUFFIX[level]


def _put(fs, fid, value, unit, period, n, label):
    if fid not in fs.facts:
        fs.add(Fact(fid, value, unit, period, int(n), label))


def _emit(fs, key, fid, unit, period, n, label, compute):
    """Gate, then add the value fact (when there is one) and its status label."""
    res = av.gate(key, compute)
    if isinstance(res, av.NotAvailable):
        _put(fs, fid + "_st", NA_STATUS, "label", period, 0, label)
        return None
    v, st = res
    if v is not None:
        _put(fs, fid, v, unit, period, n, label)
    _put(fs, fid + "_st", st, "label", period, n, label)
    return v


REST = "All other"  # the remainder row label (a data value can itself be "Other", e.g. specialty Other)
_REST = object()


def _label(k):
    return " / ".join(k) if isinstance(k, tuple) else str(k)


def series_rows(sys_map, sys_tot, comps: dict, top=None) -> list:
    """Rows of percent shares: the system's items (largest first, top-N plus Other), each with its comparator share and
    index. comps: level -> (map, total) or None. "All other" collects everything not listed, on every side."""
    keys = sorted(sys_map, key=lambda k: (-sys_map[k], _label(k)))
    listed = keys[:top] if top else keys
    extra = set(keys) - set(listed)
    for v in comps.values():
        if v is not None:
            extra |= set(v[0]) - set(listed)

    def clamp(x):
        return 0.0 if abs(x) < 1e-9 else x

    def pct(m, tot, k):
        return None if tot <= 0 else clamp(m.get(k, 0.0) / tot * 100)

    def other(m, tot):
        return None if tot <= 0 else clamp((tot - sum(m.get(k, 0.0) for k in listed)) / tot * 100)

    rows = []
    for k in listed + ([_REST] if extra else []):
        r = {"label": REST if k is _REST else _label(k), "system": other(sys_map, sys_tot) if k is _REST else pct(sys_map, sys_tot, k)}
        for lvl in ("state", "national"):
            c = comps.get(lvl)
            r[lvl] = None if c is None else (other(*c) if k is _REST else pct(c[0], c[1], k))
            r[IDX[lvl][1:]] = (r["system"] / r[lvl] * 100 if r["system"] is not None and r[lvl] and r[lvl] > 0
                               else None)
        rows.append(r)
    return rows


def _system_counts(g: pd.DataFrame) -> dict:
    subs = g["BAC_OWN_SUBS_IMS_ORG_ID"]
    by_spec = g.groupby("BAC_CHNL_SPEC_DESC")["DDD_OTLT_NBR"].nunique()
    return {"n_subs": int(subs[subs.str.strip() != ""].nunique()), "n_ddd": int(g["DDD_OTLT_NBR"].nunique()),
            "ddd_by_spec": {k: int(v) for k, v in by_spec.items()},
            "type": g["BAC_CORP_PAR_ORG_TYP_DESC"].iloc[0], "state": g["BAC_CORP_PAR_ST_CD"].iloc[0]}


def extend(fsets: dict, df: pd.DataFrame, nat: dict | None) -> dict:
    """Add the F9-F13 client facts to every FactSheet in fsets (computed from df, the cleaned synthetic rows), against
    pooled in-state peers and nat (benchmark.national_profile(), or None when the national file is missing)."""
    comps, counts = {}, {}
    for sid, g in df.groupby(SID):
        comps[sid], counts[sid] = bm.pooled(g), _system_counts(g)
    states = pd.Series({s: c["state"] for s, c in counts.items()})
    for sid, fs in fsets.items():
        if sid not in comps:
            continue
        sc, cnt = dict(comps[sid], _type=counts[sid]["type"]), counts[sid]
        peers = [p for p in states.index[states == cnt["state"]] if p != sid]
        state_c = None
        if len(peers) >= facts.MIN_STATE_PEERS:
            state_c = comps[peers[0]]
            for p in peers[1:]:
                state_c = bm.add_pooled(state_c, comps[p])
        ctx = {"system": sc, "state": state_c, "national": nat}
        n = {"system": sc["rows"], "state": len(peers), "national": nat["rows"] if nat else 0}
        # A1M: in-state peer median dollars, for scale next to the A1 state share
        if state_c is None:
            _put(fs, "F9.peer_median_dollars_state_st", MISSING["state"], "label", FULL, n["state"], LABEL["state"])
        else:
            _emit(fs, "A1M.state", "F9.peer_median_dollars_state", "usd", FULL, n["state"], LABEL["state"],
                  lambda: (float(statistics.median(comps[p]["dollars"] for p in peers)), "ok"))
        _emit(fs, "A1M.national", "F9.peer_median_dollars_nat", "usd", FULL, n["national"], LABEL["national"],
              lambda: (None, "no system id"))
        # scalars + indices
        for item, base, unit, levels, period, fn, indexed in SCALARS:
            vals = {}
            for lvl in levels:
                fid, key, c = _fid(base, lvl), f"{item}.{lvl}", ctx[lvl]
                if c is None and av.status(key) != av.NA:
                    _put(fs, fid + "_st", MISSING[lvl], "label", period, n[lvl], LABEL[lvl])
                    continue
                vals[lvl] = _emit(fs, key, fid, unit, period, n[lvl], LABEL[lvl], lambda c=c: fn(c, sc))
            if indexed and vals.get("system") is not None:
                for lvl in ("state", "national"):
                    cv = vals.get(lvl)
                    if cv is not None and cv > 0:
                        _put(fs, base + IDX[lvl], vals["system"] / cv * 100, "index", period, n[lvl], LABEL[lvl])
        # series
        for item, fid, mkey, tkey, top in SERIES:
            cmp = {}
            for lvl in ("state", "national"):
                key, c = f"{item}.{lvl}", ctx[lvl]
                res = av.gate(key, lambda c=c: None if c is None else (c[mkey], c[tkey]))
                cmp[lvl] = None if isinstance(res, av.NotAvailable) else res
                st = (NA_STATUS if isinstance(res, av.NotAvailable) else MISSING[lvl] if res is None else "ok")
                _put(fs, _fid(fid, lvl) + "_st", st, "label", FULL, n[lvl], LABEL[lvl])
            rows = series_rows(sc[mkey], sc[tkey], cmp, top)
            _put(fs, fid, rows, "series", FULL, n["system"], LABEL["system"])
            _put(fs, fid + "_st", "ok", "label", FULL, n["system"], LABEL["system"])
        # A5-A9 attributes (labels and counts; there is no national outlet, subsidiary or state column)
        _put(fs, "F10.parent_type", cnt["type"], "label", FULL, n["system"], LABEL["system"])
        _put(fs, "F10.parent_state", cnt["state"], "label", FULL, n["system"], LABEL["system"])
        for item, base, ckey in (("A7", "F10.n_subs", "n_subs"), ("A8", "F10.n_ddd", "n_ddd")):
            _emit(fs, f"{item}.system", base, "int", FULL, n["system"], LABEL["system"], lambda k=ckey: (cnt[k], "ok"))
            if state_c is None:
                _put(fs, base + "_state_st", MISSING["state"], "label", FULL, n["state"], LABEL["state"])
            else:
                _emit(fs, f"{item}.state", base + "_state", "median", FULL, n["state"], LABEL["state"],
                      lambda k=ckey: (float(statistics.median(counts[p][k] for p in peers)), "ok"))
            _emit(fs, f"{item}.national", base + "_nat", "int", FULL, n["national"], LABEL["national"],
                  lambda: (None, "no column"))
        spec_rows = []
        for spec in sorted(cnt["ddd_by_spec"], key=lambda k: (-cnt["ddd_by_spec"][k], k)):
            med = (None if state_c is None
                   else float(statistics.median(counts[p]["ddd_by_spec"].get(spec, 0) for p in peers)))
            spec_rows.append({"label": spec, "system": cnt["ddd_by_spec"][spec], "state": med, "national": None})
        res = av.gate("A9.national", lambda: None)
        _put(fs, "F10.n_ddd_by_spec", spec_rows, "series", FULL, n["system"], LABEL["system"])
        _put(fs, "F10.n_ddd_by_spec_st", "ok", "label", FULL, n["system"], LABEL["system"])
        _put(fs, "F10.n_ddd_by_spec_state_st", MISSING["state"] if state_c is None else "ok", "label", FULL,
             n["state"], LABEL["state"])
        _put(fs, "F10.n_ddd_by_spec_nat_st", NA_STATUS if isinstance(res, av.NotAvailable) else "ok", "label", FULL,
             0, LABEL["national"])
    return fsets


def compute_all(df: pd.DataFrame, bench=None, nat="auto") -> dict:
    """facts.compute_all plus the client facts. nat="auto" reads the national file if present (None if missing)."""
    fsets = facts.compute_all(df, bench)
    return extend(fsets, df, bm.national_profile() if nat == "auto" else nat)


# --- rendering (the UI and payload read these; a NOT AVAILABLE metric is text, never a number) ---------------------
def cell(fs, item: str, level: str, fid: str) -> str:
    key = f"{item}.{level}"
    if av.status(key) == av.NA:
        return av.render_na(key)
    st = fs.facts.get(fid + "_st")
    if st is not None and st.value == NA_STATUS:
        return av.render_na(key)
    f = fs.facts.get(fid)
    if f is not None and f.value is not None:
        return fmt_fact(f)
    return st.value if st is not None else "n/a"


def _idx(fs, base, level):
    f = fs.facts.get(base + IDX[level])
    return fmt_fact(f) if f is not None else "n/a"


def _state_cell(fs, item, fid, base_n_from):
    txt = cell(fs, item, "state", fid)
    if av.status(f"{item}.state") == av.NA or txt.startswith("not available"):
        return txt
    st = fs.facts.get(base_n_from)
    return f"{txt} (n={st.n})" if st is not None else txt


def _fmt_num(v, unit):
    if v is None:
        return None
    return fmt_fact(Fact("x", v, unit, "", 0, ""))


def _series_table(fs, item, fid, unit, top=None):
    out = []
    f = fs.facts.get(fid)
    if f is None:
        return out
    rows = f.value[:top] if top else f.value
    for r in rows:
        cells = {}
        for lvl in ("state", "national"):
            key = f"{item}.{lvl}"
            st = fs.facts.get(_fid(fid, lvl) + "_st")
            if av.status(key) == av.NA or (st is not None and st.value == NA_STATUS):
                cells[lvl] = av.render_na(key)
            elif r.get(lvl) is None:
                cells[lvl] = st.value if st is not None else "n/a"
            else:
                cells[lvl] = _fmt_num(r[lvl], unit)
        n_st = fs.facts.get(_fid(fid, "state") + "_st")
        state_txt = cells["state"] if cells["state"].startswith("not available") else f"{cells['state']} (n={n_st.n})"
        out.append({TABLE_COLUMNS[0]: f"{item} {r['label']}", TABLE_COLUMNS[1]: _fmt_num(r["system"], unit) or "n/a",
                    TABLE_COLUMNS[2]: state_txt, TABLE_COLUMNS[3]: cells["national"],
                    TABLE_COLUMNS[4]: _fmt_num(r.get("idx_state"), "index") or "n/a",
                    TABLE_COLUMNS[5]: _fmt_num(r.get("idx_nat"), "index") or "n/a",
                    TABLE_COLUMNS[6]: av.status_text(f"{item}.system")})
    return out


def _scalar_row(fs, item, base, name, system_text=None):
    return {TABLE_COLUMNS[0]: f"{item} {name}",
            TABLE_COLUMNS[1]: system_text if system_text is not None else cell(fs, item, "system", base),
            TABLE_COLUMNS[2]: _state_cell(fs, item, _fid(base, "state"), _fid(base, "state") + "_st"),
            TABLE_COLUMNS[3]: cell(fs, item, "national", _fid(base, "national")),
            TABLE_COLUMNS[4]: _idx(fs, base, "state"), TABLE_COLUMNS[5]: _idx(fs, base, "national"),
            TABLE_COLUMNS[6]: av.status_text(f"{item}.system")}


def _na_row(item):
    return {TABLE_COLUMNS[0]: f"{item} {av.ITEMS[item]}", TABLE_COLUMNS[1]: av.render_na(f"{item}.system"),
            TABLE_COLUMNS[2]: av.render_na(f"{item}.state"), TABLE_COLUMNS[3]: av.render_na(f"{item}.national"),
            TABLE_COLUMNS[4]: "n/a", TABLE_COLUMNS[5]: "n/a", TABLE_COLUMNS[6]: av.status_text(f"{item}.system")}


def table_rows(fs) -> list:
    """'System vs state peers vs national' rows: A1-A4, A10-A11 and R1-R7 (R4 and older-adult RSV as not available)."""
    a1 = _scalar_row(fs, "A1", "F9.share", "dollars (state: share of the state total incl. the system; "
                     "national: share of national dollars)", system_text=fmt_fact(fs.facts["F1.dollars"]))
    med = cell(fs, "A1M", "state", "F9.peer_median_dollars_state")
    if not a1[TABLE_COLUMNS[2]].startswith("not available"):
        a1[TABLE_COLUMNS[2]] += f"; peer median {med}"
    rows = [a1, _scalar_row(fs, "A1M", "F9.peer_median_dollars", av.ITEMS["A1M"],
                            system_text=fmt_fact(fs.facts["F1.dollars"]))]
    rows += _series_table(fs, "A2", "F9.cls_pct", "pct")
    rows += _series_table(fs, "A3", "F9.spec_pct", "pct")
    rows += _series_table(fs, "A4", "F9.cls_spec_dose_pct", "pct", top=A4_TOP)
    for base, name in (("F11.babies_total", "babies total (estimate)"), ("F11.babies_private", "babies private (estimate)"),
                       ("F11.babies_public", "babies public (estimate)"), ("F11.private_share", "private share")):
        rows.append(_scalar_row(fs, "A10", base, name))
    for base, name in (("F12.ped_share", "Ped share of doses"), ("F12.adult_share", "Adult share of doses"),
                       ("F12.mixed_share", "Mixed share of doses")):
        rows.append(_scalar_row(fs, "A11", base, name))
    for r in ("R1", "R2", "R3"):
        rows.append(_scalar_row(fs, r, f"F13.{r.lower()}", av.ITEMS[r]))
    rows.append(_na_row("R4"))
    for r in ("R5", "R6"):
        rows.append(_scalar_row(fs, r, f"F13.{r.lower()}", av.ITEMS[r]))
    rows.append(_na_row("R6_OLDER"))
    for name, _, label in R7_PARTS:
        rows.append(_scalar_row(fs, "R7", f"F13.r7_{name}", f"{label} share (Women's Health, season)"))
    return rows


def attribute_strip(fs) -> list:
    """A5-A9 compact strip, led by the A1 scale line (system dollars against the in-state peer median)."""
    def row(item, sys_txt, state_txt, nat_txt):
        return dict(zip(STRIP_COLUMNS, (f"{item} {av.ITEMS[item]}", sys_txt, state_txt, nat_txt,
                                        av.status_text(f"{item}.system"))))
    out = [row("A1M", fmt_fact(fs.facts["F1.dollars"]), cell(fs, "A1M", "state", "F9.peer_median_dollars_state"),
               av.render_na("A1M.national")),
           row("A5", fs.v("F10.parent_type"), av.render_na("A5.state"), cell(fs, "A5", "national", "F10.parent_type_share_nat")),
           row("A6", fs.v("F10.parent_state"), av.render_na("A6.state"), av.render_na("A6.national"))]
    for item, base in (("A7", "F10.n_subs"), ("A8", "F10.n_ddd")):
        out.append(row(item, cell(fs, item, "system", base), cell(fs, item, "state", base + "_state"),
                       cell(fs, item, "national", base + "_nat")))
    spec = fs.v("F10.n_ddd_by_spec")
    sys_txt = "; ".join(f"{r['label']} {r['system']}" for r in spec)
    st_txt = ("; ".join(f"{r['label']} {_fmt_num(r['state'], 'median')}" for r in spec) if spec and
              spec[0]["state"] is not None else fs.v("F10.n_ddd_by_spec_state_st"))
    out.append(row("A9", sys_txt, st_txt, av.render_na("A9.national")))
    return out
