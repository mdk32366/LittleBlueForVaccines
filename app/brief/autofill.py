"""autofill.py (v0.2-h1, D-0048 (auto-fill visit fields, rules part)): rule-based suggestions for two fields of every
Raised or Partially talking point, from the visit notes (or, for a point an addendum lifted, from the addendum only).
Pure: no Streamlit, no store, no network, no model; visit_tab only renders what this module decides.

- `evidence(point, text)`: AS-0077 (evidence quote rule). The sentence of `text` (g's splitter, payload.SENTENCE) with
  the highest (K hits, C hits), earliest on a tie, quoted VERBATIM. K = the point's content words (payload.keywords);
  for the size point, which has none, K = its template anchor phrases (payload.ANCHORS, AS-0073). C = its cue words
  (payload.cues) plus RANK_CUES_EXTRA when the point's own text has it (ranking only; the hint is unchanged). A
  sentence with no K hit is never picked. Over CAP characters it is cut at the last whitespace at or before CAP - 1
  and "…" is added; it is never paraphrased or normalised.
- `follow_up(point, text)`: AS-0078 (follow-up cue rule). The evidence sentence, else the sentence after it, when it
  matches FOLLOW_CUE or DATE_CUE (case-insensitive); the same verbatim cap. Otherwise "". Every non-empty follow-up
  becomes one Task in the payload (payload._tasks), so 7 points give at most 16 of the 25 Composite subrequests.
- `suggest(point, status, text)`: both values for an eligible status (Raised, Partially); {} for Not raised.
Customer response and Quality are never suggested (D-0048; h2 holds the response). No accuracy is claimed (AS-0079).
"""
from __future__ import annotations

import re

from . import payload as pl

CAP = 280
ELLIPSIS = "…"
ELIGIBLE = (pl.ADDRESSED[0], pl.ADDRESSED[1])  # Raised, Partially; Not raised goes to g's gap panel only
FIELDS = ("evidence", "follow_up")
LABEL = "auto (rule-based)"
CAPTION = "Suggestions from keyword rules. Review every value before saving. Accuracy has not been measured."
SRC_AUTO, SRC_EDITED, SRC_NONE = "auto-rule", "edited", "none"  # AS-0080 (provenance is app-side)

_WEEKDAYS = "monday|tuesday|wednesday|thursday|friday|saturday|sunday"
_MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december|"
           "jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec")
FOLLOW_CUE = re.compile(r"\b(follow[- ]up|send|next visit|call back)\b", re.IGNORECASE)
DATE_CUE = re.compile(rf"\bby ({_WEEKDAYS}|\d{{1,2}}/\d{{1,2}}|(?:{_MONTHS}) \d{{1,2}})\b", re.IGNORECASE)
# Ranking only: `share` is a FUNC word in g's hint (AS-0073), but the h1 fixture ranks it as a cue (03 must.A2.1).
RANK_CUES_EXTRA = frozenset({"share"})
__all__ = ["CAP", "ELIGIBLE", "FIELDS", "LABEL", "CAPTION", "sentences", "cap", "evidence", "follow_up", "suggest",
           "has_cue"]


def sentences(text: str) -> list:
    """g's sentence splitter S(text) (payload.SENTENCE) on the original text, each sentence stripped of the
    surrounding whitespace only; empty pieces dropped."""
    return [s.strip() for s in pl.SENTENCE.split(text or "") if s and s.strip()]


def cap(s: str) -> str:
    """Verbatim, or cut at the last whitespace at or before CAP - 1 with "…" added (at most CAP characters)."""
    if len(s) <= CAP:
        return s
    cut = max((i for i, ch in enumerate(s[:CAP]) if ch.isspace()), default=CAP - 1)
    return s[:cut] + ELLIPSIS


def _score(point, sentence: str) -> tuple:
    low = sentence.casefold()
    words = set(pl.WORD.findall(low))
    k = pl.keywords(point)
    if k:
        kh = len(k & words)
    else:
        kh = sum(pl._has_phrase(a, low) for a in pl.ANCHORS if pl._has_phrase(a, point.text.casefold()))
    own = set(pl.WORD.findall(point.text.casefold()))
    return kh, len((pl.cues(point) | (RANK_CUES_EXTRA & own)) & words)


def _best(point, text: str) -> int | None:
    """Index of the evidence sentence: highest (K, C), earliest on a tie, and only with K >= 1."""
    best, idx = (0, 0), None
    for i, s in enumerate(sentences(text)):
        sc = _score(point, s)
        if sc[0] >= 1 and sc > best:
            best, idx = sc, i
    return idx


def has_cue(sentence: str) -> bool:
    return bool(FOLLOW_CUE.search(sentence) or DATE_CUE.search(sentence))


def evidence(point, text: str) -> str:
    i = _best(point, text)
    return "" if i is None else cap(sentences(text)[i])


def follow_up(point, text: str) -> str:
    i = _best(point, text)
    if i is None:
        return ""
    ss = sentences(text)
    for s in ss[i:i + 2]:  # the evidence sentence, then the one after it; nothing further
        if has_cue(s):
            return cap(s)
    return ""


def suggest(point, status: str, text: str) -> dict:
    """{"evidence": ..., "follow_up": ...} for a Raised or Partially point; {} for any other status."""
    if status not in ELIGIBLE:
        return {}
    return {"evidence": evidence(point, text), "follow_up": follow_up(point, text)}
