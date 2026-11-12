"""narrative.py: digit-free talking points from fact tokens. LLM is off in this build (config.LLM_MODE).

compose() accepts an optional `llm` callable ONLY so tests can prove the fallback (T-0005); nothing in the app passes
one, and there is no network client in this package. Rule (§0 item 4): a rejected LLM output gets one retry, then the
templated points are used; any error or timeout falls back too.
"""
from dataclasses import dataclass

from . import templates, validator
from .fmt import fmt_fact

LLM_TIMEOUT_S = 20
MAX_ATTEMPTS = 2  # first try + one retry


@dataclass
class Narrative:
    tokens: list      # validated token text
    rendered: list    # substituted, display text
    source: str       # "templated" | "llm"
    notes: list


def render_tokens(text: str, fs) -> str:
    return validator.TOKEN.sub(lambda m: fmt_fact(fs.facts[m.group(1)]), text)


def _templated(fs, notes):
    pts = templates.points(fs)
    for p in pts:
        r = validator.validate(p, fs.scalar_ids())
        if not r.ok:
            raise AssertionError(f"template failed validation: {p!r}: {r.reasons}")
    return Narrative(pts, [render_tokens(p, fs) for p in pts], "templated", notes)


def compose(fs, llm=None) -> Narrative:
    notes = []
    if llm is None:
        return _templated(fs, ["LLM off"])
    for attempt in range(MAX_ATTEMPTS):
        try:
            out = llm(fs.to_json(), timeout=LLM_TIMEOUT_S)
        except Exception as e:  # unreachable, timeout, anything: fall back (T-0005)
            notes.append(f"attempt {attempt + 1}: {type(e).__name__}")
            break
        pts = [p for p in (out or "").split("\n") if p.strip()]
        bad = [validator.validate(p, fs.scalar_ids()) for p in pts]
        if pts and all(b.ok for b in bad):
            return Narrative(pts, [render_tokens(p, fs) for p in pts], "llm", notes)
        notes.append(f"attempt {attempt + 1}: rejected {[r for b in bad for r in b.reasons][:3]}")
    return _templated(fs, notes + ["fell back to templated points"])
