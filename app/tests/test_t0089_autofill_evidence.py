"""T-0089 evidence quote rule (AS-0077, D-0048): the auto-filled Evidence quote is an exact substring of its source
(after removing a trailing "…"); it is the sentence with the highest (K hits, C hits), the earliest on a tie, and never
a sentence with no K hit; a sentence over 280 characters is cut at a word boundary with "…" (at most 280 in all); after
'Address now' (path B) a point the addendum lifted is quoted from the addendum, not the notes.
The ranking-only cue words (payload.RANK_CUES_EXTRA, `share`) never change a status: the same rows (the five narratives
plus a planted row where `share` would decide) give identical hints with and without them.
Mutations: quote_paraphrased (the quote is collapsed to single spaces and lowercased), share_reaches_status (the
ranking-only cue reaches the status rule)."""
import pytest

from brief import autofill as af, payload as pl, talking, visit_tab
from tests import narratives_fixture as nf

CASES = nf.cases()
RSV = pl.TalkingPoint("must.A2.1", "Must cover: dollar share of RSV is 70.1% for this system against 5.3% for the pooled "
                                   "national file (45,462 rows), an index of 1332.")
ADD04 = "Shingles uptake runs ahead of the national file this year. Hepatitis came up only briefly."
MISSED04 = ["fixed.A2.1", "must.R5", "must.A2.3", "must.R6", "question.F2"]


def _source_has(quote: str, source: str) -> bool:
    return quote.removesuffix(af.ELLIPSIS) in source


@pytest.mark.parametrize("n", sorted(CASES))
def test_quote_is_verbatim_substring(n, real_client):
    notes = nf.notes(CASES[n])
    got = 0
    for p in talking.payload_points(CASES[n]["sid"], real_client):
        status = pl.hint_status(p, notes)
        if status in af.ELIGIBLE:
            q = af.evidence(p, notes)
            assert q and _source_has(q, notes) and len(q) <= af.CAP, (p.key, q)
            assert q in af.sentences(notes), (p.key, q)  # a whole sentence, untouched
            got += 1
    assert got >= 2


def test_highest_k_then_c_earliest_on_tie():
    text = ("RSV came up first. RSV index against the national file was discussed. "
            "Again the RSV index against the national file. Nothing else here.")
    assert af.evidence(RSV, text) == "RSV index against the national file was discussed."  # (1,3) beats (1,0); tie -> earliest
    two_k = pl.TalkingPoint("x", "Shingles and pneumococcal share of doses.")
    t2 = "Shingles doses were discussed. Shingles and pneumococcal came up."  # (1, 1) then (2, 0)
    assert af.evidence(two_k, t2) == "Shingles and pneumococcal came up."  # K hits rank before C hits
    assert af.evidence(RSV, "The national file index was pooled. Dollar share moved.") == ""  # no K hit, no quote


def test_size_point_ranks_by_anchors():
    a1 = pl.TalkingPoint("fixed.A1", "Size: $1.0M in net dollars, 5% of the in-state total (synthetic peers, n = 7), "
                                     "and 0.1% of national dollars.")
    text = "We met. The book is about $1M in net dollars. Net dollars and the in-state total came up."
    assert af.evidence(a1, text) == "Net dollars and the in-state total came up."
    assert af.evidence(a1, "Nothing about size.") == ""


def test_cap_280_at_a_word_boundary():
    long = "RSV " + " ".join(["index"] * 80) + "."
    assert len(long) > af.CAP
    q = af.evidence(RSV, "Hello there. " + long)
    assert len(q) <= af.CAP and q.endswith(af.ELLIPSIS)
    body = q.removesuffix(af.ELLIPSIS)
    assert long.startswith(body) and long[len(body)].isspace() and not body.endswith(" ")
    exact = "RSV " + "x" * (af.CAP - 5) + "."
    assert len(exact) == af.CAP and af.evidence(RSV, exact) == exact  # 280 is not cut
    assert af.cap("y" * 300) == "y" * (af.CAP - 1) + af.ELLIPSIS  # no whitespace at all: hard cut at 279


def test_source_after_path_b_is_the_addendum():
    state = {"addendum_text": {"must.R5": [ADD04]}}
    assert visit_tab._source_text(state, "must.R5", "the notes", lifted=True) == ADD04
    assert visit_tab._source_text(state, "must.R5", "the notes", lifted=False) == "the notes"
    assert visit_tab._source_text(state, "fixed.A1", "the notes", lifted=True) == "the notes"


def test_apptest_path_b_quotes_the_addendum(tmp_path, monkeypatch):
    case = CASES["04"]
    sid = case["sid"]
    at = nf.app_with_notes(tmp_path, monkeypatch, case)
    for k in MISSED04:
        at.radio(key=nf.mode_key(sid, k)).set_value(visit_tab.GAP["B"])
    at.run()
    box = next(t for t in at.text_area if str(t.key).startswith(f"vr_gap_add_{sid}_"))
    box.input(ADD04).run()
    at.button(key=f"vr_gap_check_{sid}").click().run()
    assert not at.exception, [e.value for e in at.exception]
    idx = {p: i for i, p in enumerate(r[0] for r in case["rows"])}
    ev = {k: at.text_input(key=f"vr_ev_{sid}_{idx[k]}").value for k in MISSED04}
    assert ev["must.R5"] == "Shingles uptake runs ahead of the national file this year."  # lifted to Raised
    assert ev["must.A2.3"] == "Hepatitis came up only briefly."  # lifted to Partially
    assert ev["fixed.A2.1"] == ev["must.R6"] == ev["question.F2"] == ""  # still Not raised
    assert all(_source_has(ev[k], ADD04) for k in ("must.R5", "must.A2.3"))
    assert not _source_has(ev["must.R5"], nf.notes(case))


PLANTED = (RSV, "RSV share was discussed.")  # K = rsv alone; `share` would make it Raised if it were a status cue


def test_rank_cues_never_affect_status(real_client, monkeypatch):
    assert af.RANK_CUES_EXTRA is pl.RANK_CUES_EXTRA and "share" in pl.RANK_CUES_EXTRA and "share" in pl.FUNC
    rows = [(p, nf.notes(c)) for c in CASES.values() for p in talking.payload_points(c["sid"], real_client)]
    rows.append(PLANTED)
    with_extra = [pl.hint_status(p, t) for p, t in rows]
    assert not any(pl.RANK_CUES_EXTRA & pl.cues(p) for p, _ in rows)
    monkeypatch.setattr(pl, "RANK_CUES_EXTRA", frozenset())
    monkeypatch.setattr(af, "RANK_CUES_EXTRA", frozenset())
    without = [pl.hint_status(p, t) for p, t in rows]
    assert with_extra == without
    assert with_extra[-1] == "Partially"  # the planted row: one K word and no AS-0073 cue
    assert af.evidence(*PLANTED) == PLANTED[1]  # ranking still quotes it (K hit)
