"""T-0095 Bluebird sidecar client (D-0049, AS-0081, AS-0083): the URL must be plain http://host[:port]; the request
is greedy, grammar-bound to the four Customer response values, notes first and the talking point last; anything but
exactly one of the four values, and any transport trouble, is Unavailable (never a default value).
Mutations: bb_label_lax, bb_url_lax."""
import pytest

from brief import bluebird as bb, payload as pl
from tests.bluebird_stub import Stub, free_port_url

POINT = pl.TalkingPoint("must.A2.1", "Must cover: dollar share of RSV against the pooled national file.")


@pytest.fixture
def stub():
    s = Stub()
    yield s
    s.close()


@pytest.mark.parametrize("url", ["http://127.0.0.1:8080", "http://lb-bluebird:8080/", "http://sidecar"])
def test_url_accepted(url):
    assert bb.check_url(url) == url.rstrip("/")


@pytest.mark.parametrize("url", [None, "", "  ", "https://127.0.0.1:8080", "ftp://x", "http://u:p@127.0.0.1:1",
                                 "http://127.0.0.1:1/completion", "http://127.0.0.1:1/?a=b", "http://127.0.0.1:1/#f",
                                 "127.0.0.1:8080", "http://"])
def test_url_refused(url):
    with pytest.raises(bb.Unavailable):
        bb.check_url(url)


def test_labels_and_grammar_are_the_four_values():
    assert bb.LABELS == pl.RESPONSES == ("Positive", "Neutral", "Negative", "Objection")
    assert bb.GRAMMAR == 'root ::= "Positive" | "Neutral" | "Negative" | "Objection"'


@pytest.mark.parametrize("content", ["Positive", " Neutral\n", "Negative", "Objection"])
def test_parse_label_exact(content):
    assert bb.parse_label(content) == content.strip()


@pytest.mark.parametrize("content", ["positive", "Positive.", "Neutral, mostly", "", None, 3, "Maybe"])
def test_parse_label_refuses_anything_else(content):
    with pytest.raises(bb.Unavailable):
        bb.parse_label(content)


def test_request_shape(stub):
    notes = "The pharmacy lead liked the RSV numbers. " * 3
    assert bb.classify(stub.url, POINT.text, notes) == "Positive"
    (req,) = stub.requests
    b = req["body"]
    assert req["path"] == "/completion"
    assert b["grammar"] == bb.GRAMMAR and b["temperature"] == 0.0 and b["top_k"] == 1 and b["cache_prompt"] is True
    assert b["n_predict"] == bb.N_PREDICT <= 8
    p = b["prompt"]
    assert p.startswith("<|im_start|>system\n") and p.endswith("<|im_start|>assistant\n")
    assert p.index(notes.strip()) < p.index(POINT.text)  # notes first (shared prefix), talking point last


def test_notes_cut_before_the_model():
    p = bb.render_prompt("point", "x" * (bb.NOTES_CHARS + 500))
    assert "x" * bb.NOTES_CHARS in p and "x" * (bb.NOTES_CHARS + 1) not in p


@pytest.mark.parametrize("answer", ["Positive.", "I think Neutral", ""])
def test_bad_answer_is_unavailable(answer):
    s = Stub(answer=lambda body: answer)
    try:
        with pytest.raises(bb.Unavailable):
            bb.classify(s.url, POINT.text, "notes")
    finally:
        s.close()


def test_http_error_is_unavailable():
    s = Stub(status=500)
    try:
        with pytest.raises(bb.Unavailable):
            bb.classify(s.url, POINT.text, "notes")
    finally:
        s.close()


def test_refused_and_timeout_are_unavailable():
    with pytest.raises(bb.Unavailable):
        bb.classify(free_port_url(), POINT.text, "notes", timeout=2)
    s = Stub(delay=2.0)
    try:
        with pytest.raises(bb.Unavailable):
            bb.classify(s.url, POINT.text, "notes", timeout=0.3)
    finally:
        s.close()


def test_provider_off_unless_flag_on(stub):
    assert bb.provider({}) is None
    assert bb.provider({"LB_BLUEBIRD": "off", "LB_BLUEBIRD_URL": stub.url}) is None
    assert bb.provider({"LB_BLUEBIRD": "1", "LB_BLUEBIRD_URL": stub.url}) is None
    prov = bb.provider({"LB_BLUEBIRD": "on", "LB_BLUEBIRD_URL": stub.url})
    assert prov(POINT, "notes") == "Positive"
    with pytest.raises(bb.Unavailable):  # flag on, no URL: unavailable, not a default
        bb.provider({"LB_BLUEBIRD": "on"})(POINT, "notes")
