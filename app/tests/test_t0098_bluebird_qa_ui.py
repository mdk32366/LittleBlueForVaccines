"""T-0098 Contract Q&A tab with Bluebird (D-0050), AppTest of the whole app against the stub sidecar:
- flag off: the tab is today's tab (TermSet lookup, LLM off), no Bluebird button, the page caption still says LLM off;
- flag on: the tab says Bluebird, nothing is sent until 'Ask Bluebird' is clicked, the checked answer is shown with
  its quoted span and cited clause, and the TermSet lookup is still shown under it; the answer is kept for the
  session (a rerun does not ask again);
- a rejected answer or a model that is down shows a warning, never an answer, and the TermSet lookup still works.
Mutations: qa_span_unchecked, qa_down_hidden."""
import json

import pytest
from streamlit.testing.v1 import AppTest

from brief import qa_panel
from tests import narratives_fixture as nf
from tests.bluebird_stub import Stub, free_port_url

SID = "SYNCP000002"
Q = "Starting when is the master arrangement binding?"
GOOD = {"answer": "Commencement: {S1}.", "spans": {"S1": {"anchor": "SYN-SYNCP000002-MSA1#2", "text": "1 June 2024"}}}
OFF_SUBHEADER = "Ask the contracts (TermSet lookup, LLM off)"


def app(tmp_path, monkeypatch, url=None, question=Q):
    monkeypatch.setenv("LB_VISITS_DB", str(tmp_path / "ui.db"))
    if url is None:
        monkeypatch.delenv("LB_BLUEBIRD", raising=False)
        monkeypatch.delenv("LB_BLUEBIRD_URL", raising=False)
    else:
        monkeypatch.setenv("LB_BLUEBIRD", "on")
        monkeypatch.setenv("LB_BLUEBIRD_URL", url)
    at = AppTest.from_file(nf.APP, default_timeout=240).run()
    at.selectbox(key="system").set_value(SID).run()
    at.text_input(key="qa_text").input(question).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def ask(at):
    at.button(key=qa_panel.BUTTON_KEY).click().run()
    assert not at.exception, [e.value for e in at.exception]


def md(at):
    return " ".join(m.value for m in at.markdown)


def termset_shown(at):
    return "**Answer:** 1 June 2024" in md(at) and "SYN-SYNCP000002-MSA1#2" in md(at)


@pytest.fixture
def stub():
    s = Stub(answer=lambda body: json.dumps(GOOD))
    yield s
    s.close()


def test_flag_off_is_todays_tab(tmp_path, monkeypatch):
    at = app(tmp_path, monkeypatch)
    assert OFF_SUBHEADER in [s.value for s in at.subheader]
    assert qa_panel.BUTTON_KEY not in [b.key for b in at.button]
    assert "Bluebird answer" not in md(at) and termset_shown(at)
    assert any("LLM off" in c.value for c in at.caption)


def test_flag_on_answers_with_cited_span(tmp_path, monkeypatch, stub):
    at = app(tmp_path, monkeypatch, stub.url)
    assert qa_panel.QA["subheader"] in [s.value for s in at.subheader]
    assert qa_panel.QA["caption"] in [c.value for c in at.caption]
    assert any("Bluebird on" in c.value for c in at.caption)
    assert stub.requests == []  # nothing is sent before the click
    assert qa_panel.QA["prompt"] in [c.value for c in at.caption]
    ask(at)
    assert len(stub.requests) == 1
    text = md(at)
    assert "**Bluebird answer:** Commencement: **1 June 2024**." in text
    assert "`SYN-SYNCP000002-MSA1#2` · Duration and Extension · span: **1 June 2024**" in text
    assert any("found word for word" in c.value for c in at.caption)
    assert qa_panel.QA["termset"] in text and termset_shown(at)
    at.run()  # a rerun shows the kept answer and does not ask again
    assert len(stub.requests) == 1 and "**Bluebird answer:**" in md(at)


def test_cross_document_answer_carries_a_warning(tmp_path, monkeypatch, stub):
    at = app(tmp_path, monkeypatch, stub.url,
             question="Has the account cleared its Influenza minimum take over the latest year?")
    ask(at)
    assert "**Bluebird answer:**" in md(at)
    assert qa_panel.QA["cross"] in [w.value for w in at.warning]


def test_plain_contract_answer_has_no_cross_warning(tmp_path, monkeypatch, stub):
    at = app(tmp_path, monkeypatch, stub.url)
    ask(at)
    assert qa_panel.QA["cross"] not in [w.value for w in at.warning]


def test_rejected_answer_is_not_shown(tmp_path, monkeypatch, stub):
    stub.answer = lambda body: json.dumps({"answer": "Commencement: {S1}.",
                                           "spans": {"S1": {"anchor": "SYN-SYNCP000002-MSA1#2",
                                                            "text": "1 January 2099"}}})
    at = app(tmp_path, monkeypatch, stub.url)
    ask(at)
    assert any(qa_panel.QA["rejected"] in w.value for w in at.warning)
    assert "Bluebird answer" not in md(at) and "2099" not in md(at)
    assert termset_shown(at)


def test_model_down_warns_and_termset_still_works(tmp_path, monkeypatch):
    at = app(tmp_path, monkeypatch, free_port_url())
    ask(at)
    assert any(qa_panel.QA["down"] in w.value for w in at.warning)
    assert "Bluebird answer" not in md(at) and termset_shown(at)


def test_advice_question_refused_without_the_model(tmp_path, monkeypatch, stub):
    at = app(tmp_path, monkeypatch, stub.url, question="What price should we offer PFIZER for Pneumococcal?")
    ask(at)
    assert stub.requests == []
    assert "**Bluebird answer:** not in the contracts" in md(at)
    assert any("pricing or negotiation advice is out of scope" in c.value for c in at.caption)
