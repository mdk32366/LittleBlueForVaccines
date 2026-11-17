"""T-0099 hint fixes (bug 1, AS-0086): a sentence (clause) that says a point was NOT discussed never counts for it, and
a ratio point ("X to Y doses") needs both sides for Raised: the numerator alone is Partially, the denominator alone
(shared between ratios) does not count. Content that merely contains "not" still counts. The committed narratives
keep their pinned hints (T-0084, T-0092 unchanged).
Mutations: hint_negation_off, hint_ratio_off."""
import pytest

from brief import payload as pl

ROTA = pl.TalkingPoint("must.A2.4", "Must cover: dollar share of Rotavirus is 9.4% for this system against 2.0% for the "
                       "pooled national file (45,462 rows), an index of 470.")
R5 = pl.TalkingPoint("must.R5", "Must cover: Shingles to adult-labelled Influenza doses is 0.83 for this system "
                     "against 0.19 for the pooled national file (45,462 rows), an index of 432.")
R6 = pl.TalkingPoint("must.R6", "Must cover: RSV Vaccine to adult-labelled Influenza doses is 0.00 for this system "
                     "against 0.08 for the pooled national file (45,462 rows), an index of 6.")
MEN = pl.TalkingPoint("must.R1", "Must cover: MenB + MenABCWY to MenACWY + MenABCWY doses is 2.29 for this system "
                      "against 0.55 for the pooled national file (45,462 rows), an index of 417.")
SIZE = pl.TalkingPoint("fixed.A1", "Size: $834.7K in net dollars, 17.8% of the in-state total (synthetic peers, n = 7), "
                       "and 0.0028% of national dollars.")

NEGATED = [
    (ROTA, "We did not get to rotavirus at all."),
    (ROTA, "We didn't discuss the rotavirus dollar share."),
    (ROTA, "We ran out of time before the rotavirus point."),
    (ROTA, "Rotavirus never came up, and the dollar share stays for next time."),
    (ROTA, "We skipped rotavirus today."),
    (R5, "We did not discuss the shingles to adult-labelled influenza ratio."),
    (SIZE, "We did not go through net dollars or national dollars."),
]


@pytest.mark.parametrize("point,text", NEGATED)
def test_not_discussed_is_not_raised(point, text):
    assert pl.hint_status(point, text) == "Not raised"


@pytest.mark.parametrize("point,text,want", [
    (MEN, "I mentioned MenB briefly, but we ran out of time before going through it.", "Partially"),
    (ROTA, "Rotavirus dollar share runs high; they will not move back.", "Raised"),   # "not" about content counts
    (ROTA, "Rotavirus dollar share runs high, though we did not discuss programs.", "Raised"),
    (ROTA, "We did not get to rotavirus. Later the rotavirus dollar share came up.", "Raised"),  # another sentence
])
def test_clauses_and_content_negation(point, text, want):
    assert pl.hint_status(point, text) == want


@pytest.mark.parametrize("point,text,want", [
    (R5, "Dollar share of shingles is about four times the national file.", "Partially"),       # numerator only
    (R5, "The adult-labelled influenza doses ran far above the national file.", "Not raised"),  # denominator only
    (R5, "Shingles to adult-labelled influenza doses is far above the national file.", "Raised"),
    (R6, "Shingles to adult-labelled influenza doses is far above the national file.", "Not raised"),  # shared side
    (R6, "RSV vaccine to adult-labelled influenza is low against the national file.", "Raised"),
    (MEN, "MenB and MenACWY both came up.", "Raised"),
    (MEN, "MenACWY came up.", "Not raised"),
])
def test_ratio_needs_both_sides(point, text, want):
    assert pl.hint_status(point, text) == want


def test_ratio_sides_parsed_only_for_ratio_points():
    assert pl.ratio_sides(R5) == ({"shingles"}, {"adult-labelled", "influenza"})
    assert pl.ratio_sides(ROTA) is None and pl.ratio_sides(SIZE) is None
