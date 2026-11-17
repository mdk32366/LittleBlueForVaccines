"""bluebird_qa.py (v0.2-h3, D-0050 (Bluebird Contract Q&A, flagged)): Contract Q&A answered by the OPTIONAL local
Bluebird sidecar, behind the same feature flag as D-0049 (config.bluebird_on(), env LB_BLUEBIRD, OFF by default); with
the flag off nothing in the app imports this module and the Contract Q&A tab is the TermSet lookup it always was.

- Contract Q&A is the task Bluebird v1.0 was trained and evaluated on (AS-0082): a question plus the contract text of
  ONE system in, JSON {answer, spans} out, where every number or term in the answer is a slot {Sn} filled by a span
  quoted from the contract. The prompt is the training prompt exactly (SYS, user_of; the Qwen2.5 chat template), sent
  with the bench's greedy settings and JSON-slot grammar (Gate 0.B/0.C), so the 0.C measurement applies.
- The contract text is chosen from this system's documents only (system isolation, as contracts.py), never another
  system's (AS-0084): the master arrangement, amendment and proposal by default; the metrics exhibit for metric
  questions; both for questions that set the contract against the account's figures. When that is over the training
  prompt budget, exhibit sections are dropped, the least related to the question first.
- Nothing the model says is shown unchecked (AS-0085): the reply must parse to the exact schema, every {Sn} must have a
  span and every span a {Sn}, no digit may stand outside a slot, no advisory-commercial wording (the D-0009
  denylist), and every quoted span must be found word for word in a clause that was in the prompt. The citation
  anchor is the clause where the span was found, never only the model's say-so. Any failure rejects the whole answer.
- The sidecar's URL and its checks are bluebird.check_url's (AS-0081). Every failure is a result with a status, never
  an exception and never a made-up answer: "ok", "refusal" (the model says the contracts do not answer it),
  "rejected" (the answer failed a check) or "down" (no usable reply).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

from . import bluebird, config, contracts

SYS = "Answer from the contract text only. Return JSON {answer, spans}; no raw digits in answer."  # = training B1
REFUSAL = contracts.REFUSAL  # "not in the contracts", also the model's trained refusal text
UNIT_CHARS = 4300           # contract text per prompt (~1,250 tokens); training prompts kept at most 4,274 characters
N_PREDICT = 256             # the bench's cap; the longest training answer was 107 tokens
TIMEOUT_S = 120             # one question; 0.C per-question p95 was 4.1 s at 4 cpus
MAX_BODY = 65536
DOC_ORDER = ("MSA", "AMD", "PROPOSAL", "EXH")
CONTRACT_DOCS = {"MSA", "AMD", "PROPOSAL"}
STATUSES = ("ok", "refusal", "rejected", "down")
# The json-slot layout as GBNF, as the Gate 0 bench sent it. A superset of the schema: parse() re-checks it strictly.
GRAMMAR = r'''
root  ::= "{\"answer\": \"" str "\", \"spans\": {" spans? "}}"
spans ::= span (", " span)*
span  ::= "\"S" [1-9] [0-9]? "\": {\"anchor\": \"" str "\", \"text\": \"" str "\"}"
str   ::= ( [^"\\\x00-\x1F] | "\\" ( ["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] ) )*
'''
GREEDY = {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "min_p": 0.0, "repeat_penalty": 1.0, "presence_penalty": 0.0,
          "frequency_penalty": 0.0, "seed": 562, "cache_prompt": False}
STOP = ["<|im_end|>", "<|endoftext|>"]

# Routing (AS-0084), mirroring the document sets Bluebird was trained on: the master arrangement alone for its terms
# (and for questions it must refuse); master + proposal for proposal questions; the amendment (with the master for
# exclusivity) for amendment questions; a window of the exhibit for metric questions; master (+ amendment) + an
# exhibit window for questions that set the contract against the account's figures.
METRIC = re.compile(r"(?<![a-z0-9])(?:[ar]\d{1,2}(?![0-9])|exhibit|profile|figure|countrywide|nationwide|nation|"
                    r"national|same-state|in-state|state|peers?|comparators?|index|brand)", re.I)
CROSS = re.compile(r"\b(?:latest[- ]year|recent|windows?|attained|unlocked|satisfied|cleared|honou?red|gain\w*|"
                   r"los\w*|drift|met)\b", re.I)
PROPOSAL = re.compile(r"\b(?:pitch\w*|propos\w*|offer\w*|counter\w*|bid|exchange|return item|sought|seek\w*|"
                      r"20\d\d)\b", re.I)
AMEND = re.compile(r"\b(?:amend\w*|update\w*|revis\w*|later instrument|post-update|revision)\b", re.I)
EXCLUSIVE = re.compile(r"\b(?:exclusiv\w*|sole|preferred)\b", re.I)
CODE = re.compile(r"(?<![A-Za-z0-9])([AR]\d{1,2})(?![0-9])", re.I)
WORD = re.compile(r"[a-z0-9+]+")
CANON = [(re.compile(p, re.I), w) for p, w in (  # question and exhibit wording that mean the same thing
    (r"trailing twelve months|latest[- ]year|latest year", " t12 "), (r"\bvolume\b", " doses "),
    (r"\b(?:nationwide|countrywide|across the nation|nation|national)\b", " natl "),
    (r"\b(?:same-state|in-state|comparator accounts?|comparators?|peers?|state pool|state)\b", " samestate "),
    (r"\b(?:relative|index)\b", " rel "), (r"\b(?:drift|gainer|gaining|gained|led)\b", " gainer "))]
STOPWORDS = frozenset("the a an of for to in on is what and or this that please which with by at as its it be".split())

SLOT = re.compile(r"\{S\d+\}")
SPAN_KEY = re.compile(r"^S\d+$")
# D-0009 denylist, as the Bluebird validator: advisory wording together with commercial wording in one sentence.
ADVISORY = ("should", "recommend", "offer", "propose", "ask for", "push", "target", "increase", "lower", "match",
            "undercut")
COMMERCIAL = ("price", "rebate", "discount", "tier", "wac", "admin fee")


ASK_ADVICE = re.compile(r"\b(?:should|ought|recommend\w*|request|negotiat\w*|ask for|push for|aim for|best|ideal|"
                        r"target|undercut|propose|in talks|next round|price point)\b", re.I)
ASK_COMMERCIAL = re.compile(r"\b(?:price\w*|pricing|rebates?|discounts?|wac|admin fee|deal)\b", re.I)
ADVICE_REASON = "pricing or negotiation advice is out of scope; Bluebird answers only what the contracts say"


def asks_for_advice(question: str) -> bool:
    """A question that asks what to offer, ask for or negotiate on price (D-0009): answered with the refusal, and
    never sent to the model (AS-0085). Bluebird was trained to refuse these, but does not always."""
    return bool(ASK_ADVICE.search(question or "") and ASK_COMMERCIAL.search(question or ""))


class Rejected(Exception):
    """The model's reply failed a check. The message is short and safe to show."""


def route(question: str) -> str:
    """'proposal', 'amendment', 'exhibit', 'cross' or 'contract' (AS-0084)."""
    q = question or ""
    if CROSS.search(q):
        return "cross"
    if METRIC.search(q):
        return "exhibit"
    if PROPOSAL.search(q):
        return "proposal"
    if AMEND.search(q):
        return "amendment"
    return "contract"


def _canon_words(text: str) -> set:
    t = text.lower()
    for pat, w in CANON:
        t = pat.sub(w, t)
    return set(WORD.findall(t)) - STOPWORDS


def _doc_units(meta: dict, did: str, secs: dict) -> list:
    t = meta["doc_type"]
    if t == "PROPOSAL":  # a proposal goes in whole, as one unit 'DOC#*' (as in training)
        return [{"id": f"{did}#*", "doc_id": did, "anchor": "*", "heading": "Proposal (whole document)",
                 "text": "\n\n".join(s["text"] for s in secs.values()), "exhibit": False}]
    return [{"id": f"{did}#{a}", "doc_id": did, "anchor": a, "heading": s["heading"], "text": s["text"],
             "exhibit": t == "EXH"} for a, s in secs.items()]


def _exhibit_window(exh: list, question: str, budget: int) -> list:
    """A contiguous run of exhibit sections around the one most related to the question (a named metric code first,
    then shared words, then the earliest), grown on both sides while it fits the budget (as in training)."""
    if not exh or budget <= 0:
        return []
    codes = {c.upper() for c in CODE.findall(question)}
    qw = _canon_words(question)

    def line_score(line):
        code_hit = any(re.search(r"(?<![A-Za-z0-9])" + c + r"(?![0-9])", line) for c in codes)
        return (code_hit, len(qw & _canon_words(line)))

    def rank(i):
        return (max(line_score(ln) for ln in exh[i]["text"].split("\n")), -i)
    c = max(range(len(exh)), key=rank)
    lo = hi = c
    n = len(exh[c]["text"])
    if n > budget:
        return []
    grew = True
    while grew:
        grew = False
        for j in (hi + 1, lo - 1):
            if 0 <= j < len(exh) and not lo <= j <= hi and n + len(exh[j]["text"]) <= budget:
                n += len(exh[j]["text"])
                lo, hi = min(lo, j), max(hi, j)
                grew = True
    return exh[lo:hi + 1]


def units(system_id: str, question: str) -> list:
    """The clauses that go in the prompt, in document order: [{id, doc_id, anchor, heading, text, exhibit}], all of
    ONE system, at most UNIT_CHARS of text."""
    by_type = {}
    for did, (meta, secs, _path) in sorted(contracts.system_docs(system_id).items()):
        if meta["system_id"] == system_id and meta["doc_type"] in DOC_ORDER:
            by_type.setdefault(meta["doc_type"], []).extend(_doc_units(meta, did, secs))
    r = route(question)
    msa, amd, prop, exh = (by_type.get(t, []) for t in DOC_ORDER)
    if r == "proposal":
        base = msa + prop
    elif r == "amendment":
        base = (amd + msa if EXCLUSIVE.search(question) else amd) if amd else msa
    elif r == "cross":
        base = msa + amd
    elif r == "exhibit":
        base = []
    else:
        base = msa
    used = sum(len(u["text"]) for u in base)
    if used > UNIT_CHARS:
        return []
    window = _exhibit_window(exh, question, UNIT_CHARS - used) if r in ("exhibit", "cross") else []
    return sorted(base + window, key=lambda u: u["doc_id"])  # documents in id order (as in training), sections in order


def user_of(question: str, texts: list) -> str:
    return f"Question: {question}\n\nContract text:\n" + "\n\n".join(texts)  # = training B1 user_of


def render_prompt(question: str, us: list) -> str:
    """Qwen2.5 chat template with the training system prompt and user turn, add_generation_prompt."""
    return (f"<|im_start|>system\n{SYS}<|im_end|>\n<|im_start|>user\n{user_of(question, [u['text'] for u in us])}"
            f"<|im_end|>\n<|im_start|>assistant\n")


def parse(raw) -> dict:
    """The exact schema {"answer": str, "spans": {"S<n>": {"anchor": str, "text": str}}} or Rejected."""
    try:
        o = json.loads(raw.strip()) if isinstance(raw, str) else None
    except ValueError:
        o = None
    if not isinstance(o, dict) or set(o) != {"answer", "spans"}:
        raise Rejected("the reply was not an answer in the expected form")
    if not isinstance(o["answer"], str) or not isinstance(o["spans"], dict):
        raise Rejected("the reply was not an answer in the expected form")
    for k, v in o["spans"].items():
        if not SPAN_KEY.match(k) or not isinstance(v, dict) or set(v) != {"anchor", "text"} \
                or not all(isinstance(x, str) for x in v.values()):
            raise Rejected("the reply was not an answer in the expected form")
    return o


def is_refusal(o: dict) -> bool:
    return o["answer"].strip().lower().rstrip(".") == REFUSAL


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def _denylist_hit(text: str) -> bool:
    for sent in re.split(r"(?<=[.!?])\s+", text.lower()):
        s = " " + re.sub(r"[^a-z ]", " ", sent) + " "
        if any(f" {w} " in s for w in ADVISORY) and any(f" {w} " in s or f" {w}s " in s for w in COMMERCIAL):
            return True
    return False


def locate(span: str, anchor: str, us: list):
    """The prompt clause holding `span` word for word: the model's cited clause when it holds it, else the first one
    that does; None when no clause in the prompt holds it. A proposal unit resolves to the section holding it."""
    if not span.strip():
        return None
    ordered = sorted(us, key=lambda u: u["id"] != anchor and not (u["anchor"] == "*" and anchor.split("#")[0] ==
                                                                    u["doc_id"]))
    for u in ordered:
        hit = span in u["text"] or _norm(span) in _norm(u["text"])
        if not hit:
            continue
        if u["anchor"] != "*":
            return u
        secs = contracts.system_docs(u["doc_id"].split("-")[1])[u["doc_id"]][1]
        for a, s in secs.items():
            if span in s["text"] or _norm(span) in _norm(s["text"]):
                return {**u, "id": f"{u['doc_id']}#{a}", "anchor": a, "heading": s["heading"], "text": s["text"]}
        return u
    return None


NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def stray_numbers(answer: str, question: str = "") -> list:
    """Numbers in the answer outside its {Sn} slots. D-0023: slot tokens are exempt from the digit rule and nothing
    else is; "Band 2" in answer prose is rejected even when the question said "Band 2" (`question` is unused)."""
    return NUMBER.findall(SLOT.sub("", answer))


def verify(o: dict, us: list, question: str = "") -> dict:
    """Checked answer: {"status": "ok"|"refusal", "answer", "template", "citations": [...]} or Rejected."""
    if is_refusal(o):
        if o["spans"]:
            raise Rejected("a 'not in the contracts' reply also quoted spans")
        return {"status": "refusal", "answer": REFUSAL, "template": o["answer"], "citations": []}
    if set(SLOT.findall(o["answer"])) != {"{%s}" % k for k in o["spans"]} or not o["spans"]:
        raise Rejected("the answer's slots and quoted spans do not match")
    if stray_numbers(o["answer"], question):
        raise Rejected("a number in the answer is not quoted from the contract")
    cites, text = [], o["answer"]
    for k in sorted(o["spans"], key=lambda s: int(s[1:])):
        sp = o["spans"][k]
        u = locate(sp["text"], sp["anchor"], us)
        if u is None:
            raise Rejected("a quoted span is not in this system's contract text")
        cites.append({"slot": k, "span": sp["text"], "anchor": u["id"], "heading": u["heading"],
                      "clause_text": u["text"], "doc_id": u["doc_id"], "model_anchor": sp["anchor"]})
        text = text.replace("{%s}" % k, sp["text"])
    if _denylist_hit(text):
        raise Rejected("the answer reads as commercial advice")
    return {"status": "ok", "answer": text, "template": o["answer"], "citations": cites}


def ask(base_url: str, system_id: str, question: str, timeout: float = TIMEOUT_S,
        opener=urllib.request.urlopen) -> dict:
    """One question for one system. Always a dict with "status" in STATUSES and a short "reason" when not ok."""
    t0 = time.monotonic()
    base = {"route": route(question), "units": [], "seconds": None}
    if asks_for_advice(question):  # D-0009: never sent to the model
        return {**base, "status": "refusal", "answer": REFUSAL, "citations": [], "seconds": 0.0,
                "reason": ADVICE_REASON}
    try:
        url = bluebird.check_url(base_url)
        us = units(system_id, question)
        base["units"] = [u["id"] for u in us]
        if not us:
            return {**base, "status": "refusal", "answer": REFUSAL, "citations": [],
                    "reason": "this system has no contract text to read"}
        body = {"prompt": render_prompt(question, us), "n_predict": N_PREDICT, "grammar": GRAMMAR, "stop": STOP,
                **GREEDY}
        req = urllib.request.Request(f"{url}/completion", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with opener(req, timeout=timeout) as r:
                if getattr(r, "status", 200) != 200:
                    raise bluebird.Unavailable(f"sidecar answered HTTP {r.status}")
                data = json.loads(r.read(MAX_BODY).decode("utf-8"))
        except bluebird.Unavailable:
            raise
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            raise bluebird.Unavailable(f"sidecar unreachable or unusable ({type(e).__name__})") from None
        content = data.get("content") if isinstance(data, dict) else None
        if isinstance(data, dict) and data.get("stop_type") == "limit":
            raise Rejected("the answer was cut off at the length limit")
        res = verify(parse(content), us, question)
        return {**base, **res, "seconds": round(time.monotonic() - t0, 1)}
    except bluebird.Unavailable as e:
        return {**base, "status": "down", "reason": str(e), "citations": [], "seconds": round(time.monotonic() - t0, 1)}
    except Rejected as e:
        return {**base, "status": "rejected", "reason": str(e), "citations": [],
                "seconds": round(time.monotonic() - t0, 1)}


def provider(env=None):
    """The Contract Q&A provider for the Contract Q&A tab, or None when the flag is off: (system_id, question) ->
    result dict (see ask)."""
    env = os.environ if env is None else env
    if not config.bluebird_on(env):
        return None
    url = env.get(config.BLUEBIRD_URL_ENV, "")

    def ask_contracts(system_id: str, question: str) -> dict:
        return ask(url, system_id, question)
    return ask_contracts
