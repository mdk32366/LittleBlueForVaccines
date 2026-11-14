"""T-0082 placeholder instance URL is not a link (F-0034): the Integration tab caption and the preview caption show the
instance URL in backticks (inline code), so Streamlit's markdown does not auto-link the placeholder; no markdown or
caption the app renders holds a bare https:// URL. Added at the Architect's request: the Integration tab renders no <a>
anchor to any salesforce.com (or force.com) host, judged by `rendered_anchors`, which finds every anchor Streamlit's
GFM markdown would make (bare-URL and www. autolinks, <url>, [text](url), raw <a href>), with code spans and code blocks
excluded. Mutations: placeholder_linked (the captions' backticks dropped), link_live (the Integration tab's
auto-link restored)."""
import datetime
import re
from pathlib import Path
from urllib.parse import urlparse

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
BARE = re.compile(r"(?<!`)https://[^\s`]+")
D = datetime.date(2026, 11, 18)
_FENCE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)
_HREF = [re.compile(r"<a\s[^>]*href\s*=\s*[\"']?([^\"'\s>]+)", re.I), re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)"),
         re.compile(r"<((?:https?|ftp)://[^>\s]+)>", re.I), re.compile(r"(?<![\w/@.])((?:https?://|www\.)[^\s<>()]+)", re.I)]
SF_HOST = re.compile(r"(^|\.)(salesforce|force)\.com$", re.I)


def rendered_anchors(md: str) -> list:
    """Every link target Streamlit's markdown (GFM) would render as an <a> for this text."""
    text = _CODE.sub(" ", _FENCE.sub(" ", md or ""))
    out = []
    for rx in _HREF:
        out += [m.rstrip(".,;:!?*_~'\"") for m in rx.findall(text)]
        text = rx.sub(" ", text)
    return out


def _host(u: str) -> str:
    return urlparse(u if "://" in u else "https://" + u).hostname or ""


def test_rendered_anchors_finds_links():  # the detector itself: the bare form links, the backticked one does not
    bare = "Instance URL default https://example.my.salesforce.com is a placeholder; API version default 62.0."
    assert [_host(u) for u in rendered_anchors(bare)] == ["example.my.salesforce.com"]
    assert rendered_anchors(bare.replace("https://example.my.salesforce.com", "`https://example.my.salesforce.com`")) == []
    assert [_host(u) for u in rendered_anchors("see [x](https://a.my.salesforce.com/y), <https://b.force.com> and "
                                                "<a href='https://c.salesforce.com'>c</a> or www.salesforce.com")] == [
        "c.salesforce.com", "a.my.salesforce.com", "b.force.com", "www.salesforce.com"]
    assert rendered_anchors("```\nhttps://example.my.salesforce.com\n```") == []


def _tab_texts(t) -> list:
    """Markdown the Integration tab renders: captions, markdown, alerts and every widget label and help text."""
    out = [e.value for kind in ("caption", "markdown", "warning", "info", "success", "error", "subheader", "header")
           for e in getattr(t, kind)]
    for kind in ("text_input", "selectbox", "button", "checkbox"):
        for w in getattr(t, kind):
            out += [w.label, getattr(w, "help", None) or ""]
    out += [w.proto.label for kind in ("download_button", "file_uploader") for w in t.get(kind)]
    return out


def test_integration_tab_no_salesforce_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv("LB_VISITS_DB", str(tmp_path / "ig.db"))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    assert not at.exception
    ig = at.tabs[-1]
    assert ig.label == "Integration (dry run)"
    texts = _tab_texts(ig)
    assert any("https://example.my.salesforce.com" in t for t in texts)  # the placeholder is on the tab, as text
    links = [u for t in texts for u in rendered_anchors(t) if SF_HOST.search(_host(u))]
    assert links == [], links


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
