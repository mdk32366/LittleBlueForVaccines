"""talking.py (v0.2-b): the Talking points tab, from templates and computed facts only (no LLM; AS-0045 (must-cover
selection)). Every number in a point is a fact token rendered by fmt_fact; template text carries no digits.

Slots: three fixed (size vs state and national, the top class with its national index, the switching status), up to
three must-cover points, and one question. Guardrails: validator.validate (digits, unknown tokens, clinical words,
"should charge", advisory + commercial), plus allowed(): a token must not be a status label, must not map to a NOT
AVAILABLE registry entry, and its own status must be ok."""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import availability as av, client_metrics as cm, validator
from .fmt import fmt_fact

MUST_COVER_MIN_DEV = 25      # AS-0045: |index - 100| >= 25 qualifies
MUST_COVER_TOP = 3
NONE_QUALIFY = "No ratio differs from state peers or national by a quarter or more."
QUESTION = "Question to ask: what is driving purchasing in {F2.top_class}, and which programs are planned for next season?"

# Must-cover candidates: (metric id, base fact id, label). R1-R3, R5-R7 (plus the two OBGYN ratios under R7) and the
# A2 top-five classes. R4 is the client's interim definition and stays in the table only.
CANDIDATES = ([("R1", "F13.r1", "MenB + MenABCWY to MenACWY + MenABCWY doses"),
               ("R2", "F13.r2", "HPV to MenACWY + MenABCWY doses"),
               ("R3", "F13.r3", "Influenza to COVID Vaccine doses"),
               ("R5", "F13.r5", "Shingles to adult-labelled Influenza doses"),
               ("R6", "F13.r6", "RSV Vaccine to adult-labelled Influenza doses")]
              + [(f"R7.{name}", f"F13.r7_{name}", f"{label} share of Women's Health season doses")
                 for name, _, label in cm.R7_PARTS]
              + [("R7_FLU_TDAP", "F13.r7_flu_tdap", "Women's Health season Influenza to Tdap doses"),
                 ("R7_RSV_TDAP", "F13.r7_rsv_tdap", "Women's Health season RSV Vaccine to Tdap doses")]
              + [(f"A2.{i}", f"F9.cls{i}", None) for i in range(1, cm.A2_TOP + 1)])
COMPARATOR = {"state": "synthetic in-state peers (n = {F9.n_state_peers})",
              "national": "the pooled national file ({F9.n_nat_rows} rows)"}


@dataclass(frozen=True)
class Point:
    slot: str       # fixed | must | question
    metric: str     # metric id ("" for fixed text without one)
    text: str       # token text (validated)
    rendered: str   # display text


def allowed(fid: str, fs) -> bool:
    """A talking point may cite fid only if it is a value (not a status label), its registry entry is not NOT
    AVAILABLE, and its own status is ok."""
    if fid.endswith("_st"):
        return False
    key = cm.KEY_OF.get(fid)
    if key and av.status(key) == av.NA:
        return False
    st = fs.facts.get(fid + "_st")
    return st is None or st.value == "ok"


def check(text: str, fs) -> validator.Result:
    r = validator.validate(text, fs.scalar_ids())
    reasons = list(r.reasons)
    for m in validator.TOKEN.finditer(text):
        if m.group(1) in fs.facts and not allowed(m.group(1), fs):
            reasons.append(f"token not citable (status label, not available, or status not ok): {m.group(0)}")
    return validator.Result(not reasons, reasons)


def render(text: str, fs) -> str:
    return validator.TOKEN.sub(lambda m: fmt_fact(fs.facts[m.group(1)]), text)


def _has(fs, *fids) -> bool:
    return all(f in fs.facts and fs.facts[f].value is not None and allowed(f, fs) for f in fids)


def candidates(fs) -> list:
    """(metric id, comparator level, index) for every candidate with a system value, a comparator value and an index."""
    out = []
    for mid, base, _ in CANDIDATES:
        for lvl in ("state", "national"):
            idx = base + cm.IDX[lvl]
            if _has(fs, base, cm._fid(base, lvl), idx):
                out.append((mid, lvl, float(fs.v(idx))))
    return out


def select(cands, min_dev=None, top=None) -> list:
    """AS-0045: keep |index - 100| >= min_dev (index above zero), one per metric (its larger deviation; state first on a
    tie), ranked by |ln(index / 100)| then metric id; take the top three. Deterministic."""
    min_dev = MUST_COVER_MIN_DEV if min_dev is None else min_dev
    top = MUST_COVER_TOP if top is None else top
    best = {}
    for mid, lvl, idx in cands:
        if idx <= 0 or abs(idx - 100) < min_dev:
            continue
        d = abs(math.log(idx / 100))
        cur = best.get(mid)
        if cur is None or d > cur[2] or (d == cur[2] and lvl == "state"):
            best[mid] = (mid, lvl, d, idx)
    ranked = sorted(best.values(), key=lambda x: (-x[2], x[0]))
    return [(mid, lvl, idx) for mid, lvl, _, idx in ranked[:top]]


def _must_text(fs, mid, lvl) -> str:
    _, base, label = next(c for c in CANDIDATES if c[0] == mid)
    if label is None:  # an A2 class
        label = "dollar share of {" + base + "_name}"
    return (f"Must cover: {label} is {{{base}}} for this system against {{{cm._fid(base, lvl)}}} for "
            f"{COMPARATOR[lvl]}, an index of {{{base}{cm.IDX[lvl]}}}.")


def _size_text(fs) -> str:
    s = "Size: {F1.dollars} in net dollars"
    if _has(fs, "F9.share_state", "F9.n_state_peers"):
        s += ", {F9.share_state} of the in-state total (synthetic peers, n = {F9.n_state_peers})"
    else:
        s += f", in-state comparison: {fs.v('F9.share_state_st')}"
    if _has(fs, "F9.share_nat"):
        s += ", and {F9.share_nat} of national dollars."
    else:
        s += f", national comparison: {fs.v('F9.share_nat_st')}."
    return s


def _class_text(fs) -> str:
    s = "Top class: {F9.cls1_name} leads at {F9.cls1} of dollars"
    if _has(fs, "F9.cls1_nat", "F9.cls1_idx_nat"):
        s += " against {F9.cls1_nat} nationally, an index of {F9.cls1_idx_nat}."
    else:
        s += "; national comparison: not shown."
    return s


def _switch_text(fs) -> str:
    if fs.v("F5.status") == "flagged":
        return ("Share move: {F5.top_mfr} in {F5.top_class} moved from {F5.top_from} to {F5.top_to} of class doses "
                "between the two windows.")
    return "Switching: no material switching between the two windows."


def build(fs) -> list:
    """All points for one FactSheet (client facts required: client_metrics.compute_all). Raises if a template fails
    its guardrails, like narrative's templated path."""
    raw = [("fixed", "A1", _size_text(fs)), ("fixed", "A2.1", _class_text(fs)), ("fixed", "F5", _switch_text(fs))]
    picked = select(candidates(fs))
    raw += [("must", mid, _must_text(fs, mid, lvl)) for mid, lvl, _ in picked] or [("must", "", NONE_QUALIFY)]
    raw.append(("question", "F2", QUESTION))
    out = []
    for slot, mid, text in raw:
        r = check(text, fs)
        if not r.ok:
            raise AssertionError(f"talking point failed its guardrails: {text!r}: {r.reasons}")
        out.append(Point(slot, mid, text, render(text, fs)))
    return out


# --- payload seam (the visit-record payload builds on these items; brief/payload.py has the matching dataclass) ---
@dataclass(frozen=True)
class PayloadPoint:
    """One talking point for the payload. Field names and order are a contract (T-0045 test_payload_fields); values
    are computed numbers or None (never a number for a NOT AVAILABLE or not-ok fact)."""
    key: str                # "<slot>.<metric>", e.g. "fixed.A1", "must.R2", "question.F2", "must.none"
    text: str               # rendered point text (every number from a fact)
    metric_value: float | None
    bench_state: float | None
    bench_national: float | None


PAYLOAD_FIELDS = ("key", "text", "metric_value", "bench_state", "bench_national")
_BASES = {"A1": "F9.share", "A2.1": "F9.cls1", **{mid: base for mid, base, _ in CANDIDATES}}


def _num(fs, fid):
    if fid in fs.facts and allowed(fid, fs) and isinstance(fs.v(fid), (int, float)):
        return float(fs.v(fid))
    return None


def _real_fsets() -> dict:
    global _FSETS
    if _FSETS is None:
        from . import benchmark as bm, clean, config, load
        _FSETS = cm.compute_all(clean.clean(load.load_csv(config.DATA_PATH)), nat=bm.national_profile())
    return _FSETS


_FSETS = None


def payload_points(system_id: str, fsets: dict | None = None) -> list:
    """The talking points for one system as PayloadPoint items (positional construction keeps the field order the
    contract). fsets: client FactSheets from client_metrics.compute_all; default: the synthetic file plus the
    national file."""
    fs = (fsets if fsets is not None else _real_fsets())[system_id]
    out = []
    for p in build(fs):
        base = _BASES.get(p.metric)
        if base == "F9.share":  # A1: the system value is net dollars; comparators are shares
            vals = (_num(fs, "F1.dollars"), _num(fs, "F9.share_state"), _num(fs, "F9.share_nat"))
        elif base:
            vals = (_num(fs, base), _num(fs, cm._fid(base, "state")), _num(fs, cm._fid(base, "national")))
        else:
            vals = (None, None, None)
        out.append(PayloadPoint(f"{p.slot}.{p.metric or 'none'}", p.rendered, *vals))
    return out
