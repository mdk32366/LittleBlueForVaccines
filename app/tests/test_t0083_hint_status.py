"""T-0083 three-state hint (AS-0073; resolves F-0035 and F-0037): hint_status gives Raised when a sentence holds 2+ of
the point's content words, or 1 and one of its own cue words; Partially when its name only comes up alone; Not raised
when it never does. The size point (no content words) is matched on its template anchors: 2+ Raised, 1 Partially, 0 Not
raised. Stop words and digits never count; the rule is deterministic; mentioned_hint is hint_status != Not raised.
Mutations: partial_dropped (Partially reads as Raised), a1_stopworded (anchor rule removed)."""
import pytest

from brief import payload as pl, talking

ROTA = pl.TalkingPoint("must.A2.3", "Must cover: dollar share of Rotavirus is 8.7% for this system against 2.0% for the "
                       "pooled national file (45,462 rows), an index of 437.")
MEN = pl.TalkingPoint("must.R1", "Must cover: MenB + MenABCWY to MenACWY + MenABCWY doses is 0.99 for this system "
                      "against 0.49 for synthetic in-state peers (n = 10), an index of 203.")
SIZE = pl.TalkingPoint("fixed.A1", "Size: $834.7K in net dollars, 17.8% of the in-state total (synthetic peers, n = 7), "
                       "and 0.0028% of national dollars.")

CASES = [
    (ROTA, "Rotavirus came up only in passing.", "Partially"),           # K only: a mention without substance
    (ROTA, "Rotavirus dollar share runs high.", "Raised"),                # K + a cue word (dollar) in one sentence
    (ROTA, "Rotavirus came up. The dollar share runs high.", "Partially"),  # the cue is in another sentence
    (ROTA, "Rotavirus came up\nand the index too", "Partially"),         # a newline ends a sentence
    (ROTA, "We only discussed parking.", "Not raised"),
    (ROTA, "", "Not raised"),
    (MEN, "MenB and MenACWY both came up.", "Raised"),                    # 2 distinct K words
    (MEN, "MenB came up.", "Partially"),
    (MEN, "the system and state peers, national 0.99 and 203", "Not raised"),  # stop words and digits never count
    (SIZE, "About $835K in net dollars and a small slice of national dollars.", "Raised"),  # 2 anchors
    (SIZE, "About $835K in net dollars.", "Partially"),                   # 1 anchor
    (SIZE, "The size of the book, dollars and net share.", "Not raised"),  # template words, no anchor phrase
    (SIZE, "In-State Total and NATIONAL DOLLARS", "Raised"),              # casefolded, whole phrase
    (SIZE, "the in-state totals and national dollarsx", "Not raised"),     # whole phrase only
]


@pytest.mark.parametrize("point,text,want", CASES)
def test_rule_unit_cases(point, text, want):
    assert pl.hint_status(point, text) == want


def test_size_point_has_no_keywords_and_uses_anchors(real_client):
    """F-0035: every word of the size template is a stop word, so the anchors are the only way it can hint."""
    assert pl.keywords(SIZE) == set()
    for sid in ("SYNCP000025", "SYNCP000031", "SYNCP000024", "SYNCP000098"):
        a1 = next(p for p in talking.payload_points(sid, real_client) if p.key == "fixed.A1")
        assert pl.keywords(a1) == set(), sid
        assert sum(a in a1.text.casefold() for a in pl.ANCHORS) >= 2, sid
        assert pl.hint_status(a1, "in net dollars, of the in-state total, of national dollars") == "Raised", sid
        assert pl.hint_status(a1, "in net dollars") == "Partially", sid
        assert pl.hint_status(a1, "nothing on scale") == "Not raised", sid


def test_cue_words_and_function_words():
    assert pl.FUNC <= pl.STOP
    assert {"dollar", "national", "file", "index", "pooled"} <= pl.cues(ROTA)
    assert not pl.cues(ROTA) & pl.FUNC and "rotavirus" not in pl.cues(ROTA)


def test_deterministic_and_mentioned_hint_compatible():
    for point, text, want in CASES:
        assert {pl.hint_status(point, text) for _ in range(3)} == {want}
        assert pl.mentioned_hint(point, text) == (want != "Not raised")
    assert set(pl.ADDRESSED) == {pl.hint_status(p, t) for p, t, _ in CASES}  # all three states are produced
