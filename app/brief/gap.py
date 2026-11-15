"""gap.py (v0.2-g, D-0047 (missed talking-point follow-up)): the 'Not covered yet: What about these?' rules. Pure: no
Streamlit, no store, no network; visit_tab only renders what this module decides.

The owner's ask (10:46 PT 11/14): after the notes are processed, the app asks about the talking points the visit did
not cover; the rep marks each one not addressed with a reason, or gets another chance to address it.
- `uncovered(outcomes)`: every outcome whose current status is not Raised (the panel's list).
- `second_pass(outcomes, addendum, keys)`: 'Address now'. Only the listed (not Raised) points named in `keys` are
  checked, and only against the addendum text. The status never goes down (Not raised < Partially < Raised); every
  checked point is marked addendum=True. Raised points are never passed to the hint and never change.
- `unresolved(outcomes)`: the outcomes that block a save: not Raised without a known reason code, OTHER without
  details, details over REASON_TEXT_MAX, or a reason on a Raised point. Save is disabled while this is not empty,
  and visits.save_visit refuses it too (ValueError).
AS-0075 (reason pick list): the five codes and labels below; details up to 280 characters, required for OTHER.
"""
from __future__ import annotations

import dataclasses

from . import payload as pl

REASONS = {"NOT_RELEVANT": "Not relevant to this facility", "OUT_OF_TIME": "Ran out of time",
           "CONTACT_DECLINED": "Contact declined", "COVERED_PREVIOUSLY": "Already covered previously",
           "OTHER": "Other"}
assert tuple(REASONS) == pl.REASON_CODES
REASON_TEXT_MAX = pl.REASON_TEXT_MAX
RAISED = pl.ADDRESSED[0]
__all__ = ["REASONS", "REASON_TEXT_MAX", "uncovered", "second_pass", "problem", "unresolved", "upgrade"]


def uncovered(outcomes) -> list:
    """The outcomes the panel asks about: current status Partially or Not raised, in talking-point order."""
    return [o for o in outcomes or [] if o.addressed != RAISED]


def upgrade(old: str, new: str) -> str:
    """The higher of two statuses by rank, so an addendum never moves a point down."""
    return new if pl.RANK[new] > pl.RANK[old] else old


def second_pass(outcomes, addendum: str, keys) -> list:
    """'Check addendum': a new outcome list where each not-Raised outcome whose key is in `keys` gets
    max(old status, hint_status(point, addendum)) and addendum=True. Every other outcome is returned unchanged; a
    Raised outcome is never re-checked."""
    keys = set(keys or ())
    out = []
    for o in outcomes or []:
        if o.addressed != RAISED and o.point.key in keys:
            status = upgrade(o.addressed, pl.hint_status(o.point, addendum or ""))
            o = dataclasses.replace(o, addressed=status, addendum=True,
                                    reason_code=None if status == RAISED else o.reason_code,
                                    reason_text=None if status == RAISED else o.reason_text)
        out.append(o)
    return out


def problem(o) -> str | None:
    """Why this outcome blocks a save, or None when it is resolved."""
    code, text = getattr(o, "reason_code", None), getattr(o, "reason_text", None)
    if o.addressed == RAISED:
        return "a Raised point takes no reason" if code is not None else None
    if code is None:
        return "needs a reason or an addendum"
    if code not in REASONS:
        return f"unknown reason {code!r}"
    if text is not None and len(text) > REASON_TEXT_MAX:
        return f"details are limited to {REASON_TEXT_MAX} characters"
    if code == "OTHER" and not (text or "").strip():
        return "reason Other needs details"
    return None


def unresolved(outcomes) -> list:
    """The outcomes that still block a save (see `problem`)."""
    return [o for o in outcomes or [] if problem(o) is not None]


def describe(outcomes) -> str:
    """'key (why); key (why)' for the save warning and the save_visit error."""
    return "; ".join(f"{o.point.key} ({problem(o)})" for o in unresolved(outcomes))
