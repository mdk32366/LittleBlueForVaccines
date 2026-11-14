"""T-0071 (coverage): every client item maps to at least one question type at each available level, and every
pool question type is asked somewhere in the output."""
from bia562gen.specs import schema_v1 as V1

from .v1_helpers import qa

REQUIRED = {  # item -> levels (system / state / national), from the app's availability registry
    "A1": ("system", "state", "national"), "A2": ("system", "state", "national"), "A3": ("system", "state", "national"),
    "A4": ("system", "state", "national"), "A5": ("system", "national"), "A6": ("system", "national"),
    "A7": ("system", "state", "national"), "A8": ("system", "state", "national"), "A9": ("system", "state", "national"),
    "A10": ("system", "state", "national"), "A11": ("system", "state", "national"), "HD": ("system",),
    **{r: ("system", "state", "national") for r in ("R1", "R2", "R3", "R4", "R5", "R6", "R7_FLU_TDAP", "R7_RSV_TDAP")},
}


def test_pool_covers_every_item_level():
    have = {tuple(q.split(".")[1:3]) for q in V1.POOL}
    missing = [(i, lvl) for i, lvls in REQUIRED.items() for lvl in lvls if (i, lvl) not in have]
    assert missing == []


def test_every_pool_type_asked(v1_out):
    asked = {q["question_type"] for q in qa(v1_out)}
    assert set(V1.POOL) <= asked, sorted(set(V1.POOL) - asked)
