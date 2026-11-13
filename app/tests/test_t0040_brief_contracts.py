"""T-0040 (pending Trinity's numbering) Brief tab 'Contracts on file' shows the contract marker (AppTest, headless)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from brief import contracts

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _brief_text(sid):
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.selectbox(key="system").set_value(sid).run()
    assert not at.exception
    brief = at.tabs[0]
    return [s.value for s in brief.subheader], " ".join(m.value for m in brief.markdown)


def test_brief_tab_markers():
    heads, md = _brief_text("SYNCP000036")
    assert "Contracts on file" in heads
    assert contracts.AUTO_RENEW_MARKER in md and contracts.EXPIRED_MARKER not in md
    heads, md = _brief_text("SYNCP000025")
    assert "Contracts on file" in heads
    assert contracts.AUTO_RENEW_MARKER not in md and contracts.EXPIRED_MARKER not in md
    heads, md = _brief_text("SYNCP000014")
    assert "Contracts on file" in heads and contracts.EXPIRED_MARKER in md and contracts.AUTO_RENEW_MARKER not in md
