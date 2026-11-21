# Bluebird v1.0 post-run eval @0.1: shared core (prompt render, strict/lenient parse, normalisation, validator checks, rn leak check).
# Stdlib only. Imported by build_eval_rows.py, eval.py, score.py and the tests. No model code here.
import json, re

SYS = "Answer from the contract text only. Return JSON {answer, spans}; no raw digits in answer."   # = B1 (train rows)
REFUSAL_TEXT = "not in the contracts"
REFUSAL = {"answer": REFUSAL_TEXT, "spans": {}}
SEQ = 1536                 # training sequence length (B1)
MAX_NEW = 128              # fixed generation budget; measured train answer max = 107 tokens incl. <|im_end|>
PROMPT_BUDGET = SEQ - MAX_NEW
SLOT = re.compile(r"\{S\d+\}")
KEY = re.compile(r"^S\d+$")

def user_of(question, texts):                                # = B1 user_of
    return f"Question: {question}\n\nContract text:\n" + "\n\n".join(texts)

def messages(row, fewshot=None):
    m = [{"role": "system", "content": SYS}]
    for ex in (fewshot or []):
        m += [{"role": "user", "content": ex["user"]}, {"role": "assistant", "content": ex["assistant"]}]
    m.append({"role": "user", "content": user_of(row["question"], [u["text"] for u in row["units"]])})
    return m

def parse_strict(raw):
    """Exact output schema: {"answer": str, "spans": {"S<n>": {"anchor": str, "text": str}}}, nothing else.
    Returns (obj, None) or (None, reason)."""
    s = raw.strip()
    try:
        o = json.loads(s)
    except Exception:
        return None, "not_json"
    if not isinstance(o, dict) or set(o) != {"answer", "spans"}: return None, "bad_keys"
    if not isinstance(o["answer"], str) or not isinstance(o["spans"], dict): return None, "bad_types"
    for k, v in o["spans"].items():
        if not KEY.match(k): return None, "bad_span_key"
        if not isinstance(v, dict) or set(v) != {"anchor", "text"}: return None, "bad_span_obj"
        if not isinstance(v["anchor"], str) or not isinstance(v["text"], str): return None, "bad_span_types"
    if o["answer"].strip().lower() == REFUSAL_TEXT:
        if o["spans"]: return None, "refusal_with_spans"
    elif set(SLOT.findall(o["answer"])) != {"{%s}" % k for k in o["spans"]}:
        return None, "slot_mismatch"                         # every {Sn} in answer has a span and vice versa
    return o, None

def parse_lenient(raw):
    """For the stock baseline: skip any prose/code fence before it and take the first balanced {...} that loads as a dict.
    (@0.1: the fence-strip regex of @0.0 was dead code, since the brace scan already skips fences; removed, review M06.)"""
    s = raw.strip()
    for i, ch in enumerate(s):
        if ch != "{": continue
        depth = 0
        for j in range(i, len(s)):
            depth += {"{": 1, "}": -1}.get(s[j], 0)
            if depth == 0:
                try:
                    o = json.loads(s[i:j + 1])
                    if isinstance(o, dict): return o
                except Exception:
                    pass
                break
    return None

def is_refusal(o):
    return isinstance(o, dict) and isinstance(o.get("answer"), str) and o["answer"].strip().lower().rstrip(".") == REFUSAL_TEXT

def norm(t):
    t = str(t).casefold().replace("\u2019", "'").replace("\u2014", "-")
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)                 # 1,000 -> 1000
    t = re.sub(r"\s+", " ", t).strip()
    return t.strip(" .;:,\"'")

def span_texts(o):
    sp = o.get("spans") if isinstance(o, dict) else None
    if not isinstance(sp, dict): return []
    return sorted(norm(v.get("text", "")) for v in sp.values() if isinstance(v, dict))

def render(o):
    a = o.get("answer", "") if isinstance(o, dict) else ""
    sp = o.get("spans", {}) if isinstance(o, dict) else {}
    if not isinstance(a, str): return ""
    for k, v in (sp.items() if isinstance(sp, dict) else []):
        if isinstance(v, dict): a = a.replace("{%s}" % k, str(v.get("text", "")))
    return norm(a)

# §9.6 validator (TRINITY-ARCH rev 4.4 + D-0023 slot exemption + D-0009 denylist)
ADVISORY = ["should", "recommend", "offer", "propose", "ask for", "push", "target", "increase", "lower", "match", "undercut"]
COMMERCIAL = ["price", "rebate", "discount", "tier", "wac", "admin fee"]
def digits_in_answer(o):
    return bool(re.search(r"\d", SLOT.sub("", o.get("answer", ""))))
def denylist_hit(o):
    for sent in re.split(r"(?<=[.!?])\s+", render(o)):
        s = " " + re.sub(r"[^a-z ]", " ", sent) + " "
        if any(f" {w} " in s for w in ADVISORY) and any(f" {w} " in s or f" {w}s " in s for w in COMMERCIAL): return True
    return False
def resolve(units, anchor):
    """Unit text a cited anchor points at, if that unit is in the prompt. CL units: exact 'DOC#SEC'.
    Whole-leaf units (proposals) are stored as 'DOC#*' and accept any 'DOC#k'."""
    if not isinstance(anchor, str) or "#" not in anchor: return None
    for u in units:
        if u["id"] == anchor or (u["id"].endswith("#*") and anchor.split("#")[0] == u["id"][:-2]): return u["text"]
    return None

# rn probe (@0.1, review M7): the renamed row carries leak_terms = the real supplier name, its distinctive tokens and the
# real brand stems that were replaced. A leak = any of them in the raw output, case-insensitive, on word boundaries.
def leak_hits(raw, terms):
    s = str(raw)
    return sorted({t for t in terms if re.search(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", s, re.I)})

# ---- @0.1 shared run plumbing (eval.py writes, score.py re-derives; review M2, L2, L8) ----
import hashlib as _hl
def file_sha256(p):
    h = _hl.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
def plan_batches(rows, mode, batch, kinds="", limit=0):
    """Fixed batch boundaries. Rows (optionally filtered by kind) are sorted by prompt length then id, cut into consecutive
    batches of `batch`; a resume redoes any batch that is not fully present, so batch composition never depends on where a run
    stopped. Smoke (--limit N): ceil(N/batch) WHOLE batches evenly spaced over the length order, i.e. real full-run batches."""
    key = "fs_prompt_tokens" if mode == "fewshot" else "prompt_tokens"
    rs = [r for r in rows if not kinds or r["kind"] in kinds.split(",")]
    rs.sort(key=lambda r: (r[key], r["id"]))
    bs = [rs[i:i + batch] for i in range(0, len(rs), batch)]
    if limit:
        full = bs[:-1] if len(bs) > 1 and len(bs[-1]) < batch else bs          # a short tail batch is never a smoke batch
        k = min(len(full), -(-limit // batch))
        idx = sorted({round(i * (len(full) - 1) / (k - 1)) for i in range(k)}) if k > 1 else [len(full) // 2]
        bs = [full[i] for i in idx]
    return bs
def content_sha256(preds):
    """Reproducible hash over (id, raw) sorted by id: equal for two runs that generated the same text (review L8)."""
    h = _hl.sha256()
    for i, raw in sorted((p["id"], p["raw"]) for p in preds): h.update(json.dumps([i, raw], ensure_ascii=False).encode() + b"\n")
    return h.hexdigest()
def read_manifest(p):
    return {ln.split()[1].lstrip("*"): ln.split()[0] for ln in open(p) if ln.strip()}
