"""T-0101 talking-point labels (bug 3, AS-0088): the talking points are templated in every build, Bluebird on or off,
and their labels say so without "LLM off": the Brief tab's source caption, the Talking points tab heading and the PDF
heading. With the flag off the page caption still says LLM off (T-0098). AppTest, SYNCP000002; no request is sent.
Mutation: talk_llm_off_label."""
import matplotlib.pyplot as plt
import pytest
from streamlit.testing.v1 import AppTest

from brief import config, narrative, render
from tests import narratives_fixture as nf
from tests.bluebird_stub import free_port_url

SID = "SYNCP000002"


def app(tmp_path, monkeypatch, flag):
    monkeypatch.setenv("LB_VISITS_DB", str(tmp_path / "ui.db"))
    if flag:
        monkeypatch.setenv("LB_BLUEBIRD", "on")
        monkeypatch.setenv("LB_BLUEBIRD_URL", free_port_url())  # nothing listens; nothing is clicked
    else:
        monkeypatch.delenv("LB_BLUEBIRD", raising=False)
        monkeypatch.delenv("LB_BLUEBIRD_URL", raising=False)
    at = AppTest.from_file(nf.APP, default_timeout=240).run()
    at.selectbox(key="system").set_value(SID).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@pytest.mark.parametrize("flag", [False, True])
def test_talking_point_labels_do_not_say_llm_off(tmp_path, monkeypatch, flag):
    at = app(tmp_path, monkeypatch, flag)
    captions = [c.value for c in at.caption]
    assert f"source: {config.TALK_SOURCE}" in captions
    assert config.TALK_TAB in [s.value for s in at.subheader]
    talk = [c for c in captions if c.startswith("source: ")] + [s.value for s in at.subheader
                                                                if s.value.startswith("Talking points")]
    assert talk and not any("LLM off" in t for t in talk)
    assert any("LLM off" in c for c in captions) is (not flag)  # the page caption: LLM off only with the flag off


def test_pdf_heading_does_not_say_llm_off(fixture_facts):
    fs = next(iter(fixture_facts.values()))
    fig = render.build_figure(fs, narrative.compose(fs))
    try:
        texts = [t.get_text() for t in fig.texts]
    finally:
        plt.close(fig)
    assert config.TALK_PDF in texts
    assert not any(t.startswith("Talking points") and "LLM off" in t for t in texts)
