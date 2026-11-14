"""AppTest smoke (headless, in-process): picker, brief, Q&A tab, download button, benchmark toggle. LLM off."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _app():
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception
    return at


def test_picker_brief_download():
    at = _app()
    at.selectbox(key="system").set_value("SYNCP000025").run()
    assert not at.exception
    assert any("SYNCP000025" in h.value for h in at.header)
    md = " ".join(m.value for m in at.markdown)
    assert "Size: purchases of" in md
    dl = at.get("download_button")
    assert len(dl) == 1 and "Download PDF report" in dl[0].proto.label


def test_qa_tab():
    at = _app()
    at.selectbox(key="system").set_value("SYNCP000001").run()
    at.text_input(key="qa_text").input("When does the MSA expire?").run()
    assert not at.exception
    md = " ".join(m.value for m in at.markdown)
    assert "SYN-SYNCP000001-MSA1#2" in md and "June 30, 2027" in md  # schema_v1 re-pin (was July 31, 2027)


def test_benchmark_toggle_national():
    at = _app()
    at.radio(key="benchmark").set_value("national").run()
    assert not at.exception
    assert any("national" in m.value for m in at.sidebar.markdown)
