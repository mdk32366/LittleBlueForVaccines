"""validator.py (§0 item 4, D-0009 (advisory verb + commercial term) denylist, D-0023 (slot-token exemption) applied to fact tokens).

Rejects narrative text that has: a raw digit outside {Fn.id} fact tokens; an unknown or malformed fact token;
clinical-claim words (D-0022 (fake data) keeps "no efficacy/safety claims"); "should charge"; or an advisory word in the same
sentence as a commercial term (D-0009 (advisory verb + commercial term)).
"""
import re
from dataclasses import dataclass, field

TOKEN = re.compile(r"\{(F(?:[1-9]|1[0-4])\.[a-z0-9_]+)\}")  # F1..F14 (v0.2 widening, T-0053); F0, F15+ are malformed
ANY_BRACE = re.compile(r"\{[^}]*\}")
DIGIT = re.compile(r"\d")
CLINICAL = re.compile(r"\b(efficacy|efficacious|safe|safer|safest|safety|effective|effectiveness|outcomes?|superior|inferior)\b", re.I)
SHOULD_CHARGE = re.compile(r"\bshould\s+charge\b", re.I)
ADVISORY = re.compile(r"\b(should|recommend\w*|offer\w*|propos(?:e|es|ed|ing)|ask(?:ing)?\s+for|push\w*|target\w*|increas\w*|lower\w*|match\w*|undercut\w*)\b", re.I)
COMMERCIAL = re.compile(r"\b(prices?|pricing|rebates?|discounts?|tiers?|WAC|admin\s+fees?|administrative\s+fees?)\b", re.I)
SENT = re.compile(r"(?<=[.!?;])\s+|\n+")


@dataclass
class Result:
    ok: bool
    reasons: list = field(default_factory=list)


def validate(text: str, known_ids) -> Result:
    reasons = []
    known = set(known_ids)
    for tok in ANY_BRACE.findall(text):
        m = TOKEN.fullmatch(tok)
        if not m:
            reasons.append(f"malformed token {tok}")
        elif m.group(1) not in known:
            reasons.append(f"unknown fact id {tok}")
    stripped = ANY_BRACE.sub("", text)
    if DIGIT.search(stripped):
        reasons.append(f"raw digit: {DIGIT.search(stripped).group(0)!r}")
    for m in CLINICAL.finditer(text):
        reasons.append(f"clinical claim word {m.group(0)!r}")
    if SHOULD_CHARGE.search(text):
        reasons.append("'should charge'")
    for s in SENT.split(text):
        a, c = ADVISORY.search(s), COMMERCIAL.search(s)
        if a and c:
            reasons.append(f"advice: {a.group(0)!r} with {c.group(0)!r} in one sentence")
    return Result(not reasons, reasons)
