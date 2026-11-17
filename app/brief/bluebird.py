"""bluebird.py (v0.2-h2 Gate 1, D-0049 (Bluebird Customer response, flagged)): the client for an OPTIONAL local model
sidecar that suggests the Customer response of a talking point. Behind a feature flag that is OFF by default
(config.bluebird_on(), env LB_BLUEBIRD); with the flag off nothing in the app imports this module.

- The model runs in its own sidecar container (a llama.cpp-style server on the app server's CPU), never inside the
  app container and never in this repository: no weights, adapters or model files live here (AS-0081).
- The sidecar's base URL comes from LB_BLUEBIRD_URL only; there is no default. It must be a plain http:// URL with a
  host and nothing else (no credentials, path, query or fragment). A missing or refused URL means "model unavailable".
- One request per talking point: POST <url>/completion, greedy, a grammar that admits exactly one of the four
  Customer response values, a few tokens of output. The notes go first and the talking point last, so the server can
  reuse the notes prefix between the points of one visit (cache_prompt).
- Any trouble (unset or refused URL, connection error, timeout, non-200, bad JSON, an answer that is not exactly one
  of the four values) raises Unavailable. The caller never turns Unavailable into a default value (AS-0083).
- Only the Customer response is ever suggested. Talking points stay templated, and the Evidence quote, Follow-up and
  Quality are untouched. No accuracy is claimed (AS-0082).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from . import config, payload as pl

LABELS = pl.RESPONSES  # Positive, Neutral, Negative, Objection
TIMEOUT_S = 30          # per talking point
N_PREDICT = 8           # the longest label is 3 tokens; the grammar stops it there
MAX_BODY = 65536        # bytes read from the sidecar's reply
NOTES_CHARS = 4000      # notes beyond this are cut before they go to the model (prompt size, context 2048)
GRAMMAR = "root ::= " + " | ".join(f'"{lab}"' for lab in LABELS)
SYSTEM = ("You read a vaccine sales representative's visit notes. For the talking point given, answer with the "
          "customer's response to that point as exactly one word: Positive, Neutral, Negative or Objection.")
GREEDY = {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "min_p": 0.0, "repeat_penalty": 1.0, "seed": 562,
          "cache_prompt": True}
STOP = ["<|im_end|>", "<|endoftext|>"]


class Unavailable(Exception):
    """The model gave no usable answer. The message is short and safe to show; it never carries the notes."""


def check_url(url: str | None) -> str:
    """The sidecar base URL without a trailing slash, or Unavailable."""
    if not url or not url.strip():
        raise Unavailable("no sidecar URL configured")
    u = urllib.parse.urlsplit(url.strip())
    if u.scheme != "http" or not u.hostname or u.username or u.password or u.query or u.fragment \
            or u.path not in ("", "/"):
        raise Unavailable("sidecar URL refused (plain http://host[:port] only)")
    return f"http://{u.netloc}"


def render_prompt(point_text: str, notes: str) -> str:
    """Qwen2.5 chat template (the Bluebird base): system, then one user turn with the notes first and the talking
    point last, then the assistant turn."""
    user = f"Visit notes:\n{(notes or '')[:NOTES_CHARS]}\n\nTalking point: {point_text}\nCustomer response:"
    return (f"<|im_start|>system\n{SYSTEM}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n")


def parse_label(content) -> str:
    """Exactly one of LABELS (surrounding whitespace allowed), else Unavailable."""
    s = content.strip() if isinstance(content, str) else None
    if s not in LABELS:
        raise Unavailable("answer was not one of the four Customer response values")
    return s


def classify(base_url: str, point_text: str, notes: str, timeout: float = TIMEOUT_S,
             opener=urllib.request.urlopen) -> str:
    body = {"prompt": render_prompt(point_text, notes), "n_predict": N_PREDICT, "grammar": GRAMMAR, "stop": STOP,
            **GREEDY}
    req = urllib.request.Request(f"{check_url(base_url)}/completion", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with opener(req, timeout=timeout) as r:
            if getattr(r, "status", 200) != 200:
                raise Unavailable(f"sidecar answered HTTP {r.status}")
            data = json.loads(r.read(MAX_BODY).decode("utf-8"))
    except Unavailable:
        raise
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:  # refused, timeout, HTTP error, bad JSON
        raise Unavailable(f"sidecar unreachable or unusable ({type(e).__name__})") from None
    return parse_label(data.get("content") if isinstance(data, dict) else None)


def provider(env=None):
    """The Customer response provider for visit_tab.render, or None when the flag is off. The provider is
    (point, text) -> label and raises Unavailable on any trouble."""
    env = os.environ if env is None else env
    if not config.bluebird_on(env):
        return None
    url = env.get(config.BLUEBIRD_URL_ENV, "")

    def suggest_response(point, text: str) -> str:
        return classify(url, point.text, text)
    return suggest_response
