"""Shared inputs for the v0.2-d visit tests (synthetic rep names only)."""
from brief import payload as pl

POINTS = [pl.TalkingPoint("R1", "R1 MenB + MenABCWY to MenACWY + MenABCWY: system 0.62; state peers 0.83; national 0.55",
                          "0.62", "0.83 (n=7)", "0.55"),
          pl.TalkingPoint("R3", "R3 Influenza to COVID Vaccine: system 4.10; state peers 5.00; national 5.70",
                          "4.10", "5.00 (n=7)", "5.70")]


def outcomes(follow_up="Share the season comparison"):
    return [pl.Outcome(POINTS[0], "Raised", "Positive", 4, "We buy MenB through the clinic.", follow_up),
            pl.Outcome(POINTS[1], "Not raised", "Neutral", 3, "", "")]


def visit(**kw):
    base = dict(rep="Demo  Rep", visit_date="2026-11-18", system_id="SYNCP000025",
                system_name="Sunrise Care Partners 025", notes="Talked about MenB with the clinic manager.",
                outcomes=outcomes())
    base.update(kw)
    return base
