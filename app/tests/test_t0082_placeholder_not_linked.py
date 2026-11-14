"""T-0082 placeholder instance URL is not a link (F-0034): the Integration tab caption and the preview caption show the
instance URL in backticks (inline code), so Streamlit's markdown does not auto-link the placeholder; no markdown or
caption the app renders holds a bare https:// URL."""
import datetime
import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
BARE = re.compile(r"(?<!`)https://[^\s`]+")
D = datetime.date(2026, 11, 18)


def test_instance_url_in_backticks(tmp_path, monkeypatch):
    monkeypatch.setenv("LB_VISITS_DB", str(tmp_path / "ui.db"))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    at.selectbox(key="system").set_value("SYNCP000025").run()
    at.text_input(key="vr_rep").input("Demo Rep").run()
    at.date_input(key="vr_date").set_value(D).run()
    at.button(key="vr_save").click().run()
    assert not at.exception
    texts = [c.value for c in at.caption] + [m.value for m in at.markdown]
    assert any("`https://example.my.salesforce.com` is a placeholder" in t for t in texts)
    assert any("instance `https://example.my.salesforce.com` (placeholder" in t for t in texts)
    assert not [t for t in texts if BARE.search(t)], [t for t in texts if BARE.search(t)]
