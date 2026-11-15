"""T-0090 follow-up cue rule (AS-0078, D-0048): the Follow-up is filled only when the evidence sentence or the one
after it matches the cue (follow up, follow-up, send, next visit, call back, by <weekday>, by m/d, by <month> d;
case-insensitive), with that sentence verbatim; no cue gives ""; a cue two sentences later does not count. Each fill
is one Task, so a follow-up with no cue would be a phantom Task.
Mutation: followup_without_cue (the follow-up is always the next sentence)."""
import pytest

from brief import autofill as af, payload as pl

RSV = pl.TalkingPoint("must.A2.1", "Must cover: dollar share of RSV is 70.1% for this system against 5.3% for the pooled "
                                   "national file (45,462 rows), an index of 1332.")
EV = "RSV index against the national file was discussed."
CUES = ["They want a follow up on the window.", "We set a follow-up on the window.", "I will send the table.",
        "Bring it to the next visit.", "They asked me to call back.", "They need it by Friday.",
        "They need it by 11/20.", "They need it by Nov 20.", "They need it by November 20.", "PLEASE FOLLOW UP SOON."]


@pytest.mark.parametrize("cue", CUES)
def test_each_cue_in_next_sentence(cue):
    assert af.follow_up(RSV, f"{EV} {cue} Then we left.") == cue


@pytest.mark.parametrize("cue", ["send", "follow-up", "by Tuesday"])
def test_cue_in_the_evidence_sentence(cue):
    ev = f"RSV index against the national file, {cue} the summary."
    assert af.follow_up(RSV, f"{ev} They nodded.") == ev


@pytest.mark.parametrize("text", [f"{EV} They nodded.", f"{EV}", f"{EV} They sent it already. Sending works.",
                                  f"{EV} Due by the end of the month.", f"{EV} We spoke by phone."])
def test_no_cue_gives_blank(text):
    assert af.follow_up(RSV, text) == ""


def test_only_the_evidence_sentence_and_the_next():
    assert af.follow_up(RSV, f"{EV} They nodded. Please follow up next week.") == ""
    assert af.follow_up(RSV, "Please follow up next week. " + EV) == ""  # the sentence before does not count
    assert af.follow_up(RSV, "Nothing about the point. Please send it.") == ""  # no evidence sentence, no follow-up


def test_cap_applies_to_follow_up():
    long = "Please send " + " ".join(["copies"] * 60) + "."
    fu = af.follow_up(RSV, f"{EV} {long}")
    assert len(fu) <= af.CAP and fu.endswith(af.ELLIPSIS) and long.startswith(fu.removesuffix(af.ELLIPSIS))
