# Bluebird JSON-fix @0.0: in-tree schema-constrained decoding for the answer/spans schema (ORDER-bluebird-json-fix@0.0 §2).
# Core (automaton, vocab byte table) is stdlib only; torch is used only inside JsonSlotConstraint.__call__ (tensors it is given).
# No new dependency. The accepted language is EXACTLY what evalcore.parse_strict accepts, in json.dumps' canonical layout:
#   {"answer": <S>, "spans": {<slot>: {"anchor": <S>, "text": <S>}, ...}}
#   <S>      = a JSON string: any byte except '"', '\\' and 0x00-0x1F, or an escape \" \\ \/ \b \f \n \r \t \uXXXX
#   slots    = set(evalcore.SLOT.findall(decoded answer)) with the braces removed; the span keys are exactly that set,
#              each once, in any order ("refusal" answers carry no slot, so their spans are forced to {})
#   then one stop token (<|im_end|> or <|endoftext|>); nothing else is allowed once the object is closed.
# Greedy only: the processor keeps the model's own argmax when that token is allowed, else the highest-scoring allowed token
# (stable descending order, so ties go to the lowest id, as torch.argmax does). That is the token argmax would pick after
# masking every disallowed token to -inf, computed lazily. It never forces a close when the token budget runs out: a row that
# reaches max_new_tokens stays truncated and is reported (hit_max), never silently repaired.
import json, re, hashlib
SCHEMA_ID = "bluebird-answer-spans-slot@0.0"
TOKENIZER_SHA256 = "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539"   # Qwen2.5-3B-Instruct tokenizer.json (BUILD.json, run cfg)
SLOT = re.compile(r"\{S\d+\}")      # = evalcore.SLOT (asserted equal in the tests)
_ESC = b'"\\/bfnrt'
_HEX = b"0123456789abcdefABCDEF"

class State:
    """Byte-level acceptor. feed(b) -> True (consumed) / False (rejected; the state is then undefined: use clone() first)."""
    __slots__ = ("ph", "lit", "i", "esc", "buf", "field", "left", "cand", "key")
    # ph: 'L' literal, 'S' string, 'K' span-key, 'D' done
    def __init__(self):
        self.ph = "L"; self.lit = b'{"answer": "'; self.i = 0; self.esc = 0; self.buf = bytearray(); self.field = "answer"
        self.left = None; self.cand = b""; self.key = None
    def clone(self):
        s = State.__new__(State)
        s.ph, s.lit, s.i, s.esc, s.field, s.left, s.cand, s.key = self.ph, self.lit, self.i, self.esc, self.field, self.left, self.cand, self.key
        s.buf = bytearray(self.buf) if self.field == "answer" else self.buf
        return s
    def done(self): return self.ph == "D"
    def _after_literal(self):
        lit = self.lit
        if lit == b'{"answer": "': self.ph = "S"; self.field = "answer"; self.buf = bytearray()
        elif lit == b', "spans": {':
            self._open_keys()
        elif lit == b': {"anchor": "': self.ph = "S"; self.field = "anchor"
        elif lit == b', "text": "': self.ph = "S"; self.field = "text"
        elif lit == b"}":                                   # closes one span object
            if self.left: self._lit(b", ")
            else: self._lit(b"}}")
        elif lit == b", ": self._open_keys()
        elif lit == b"}}": self.ph = "D"
        else: raise AssertionError(lit)
    def _open_keys(self):
        if not self.left: self._lit(b"}}")             # no slot: spans must be {}
        else: self.ph = "K"; self.cand = b""
    def _lit(self, lit): self.ph = "L"; self.lit = lit; self.i = 0
    def _close_string(self):                                  # the closing '"' has been consumed
        if self.field == "answer":
            ans = json.loads('"' + bytes(self.buf).decode("utf-8", "replace") + '"')
            self.left = frozenset(m[1:-1] for m in SLOT.findall(ans)); self.buf = bytearray(); self._lit(b', "spans": {')
        elif self.field == "anchor": self._lit(b', "text": "')
        else: self._lit(b"}")
    def feed(self, b):
        ph = self.ph
        if ph == "L":
            if b != self.lit[self.i]: return False
            self.i += 1
            if self.i == len(self.lit): self._after_literal()
            return True
        if ph == "S":
            e = self.esc
            if e == 0:
                if b == 0x22: self._close_string(); return True
                if b < 0x20: return False
                if b == 0x5C: self.esc = 1
            elif e == 1:
                if b == 0x75: self.esc = 5                  # \u + 4 hex
                elif b in _ESC: self.esc = 0
                else: return False
            else:
                if b not in _HEX: return False
                self.esc = 0 if e == 2 else e - 1
            if self.field == "answer": self.buf.append(b)
            return True
        if ph == "K":
            c = self.cand + bytes((b,))
            full = [k for k in self.left if (b'"' + k.encode("utf-8") + b'"').startswith(c)]
            if not full: return False
            done = [k for k in full if b'"' + k.encode("utf-8") + b'"' == c]
            if done:
                k = done[0]; self.left = self.left - {k}; self.key = k; self._lit(b': {"anchor": "')
            else: self.cand = c
            return True
        return False                                          # 'D': no byte is allowed after the closing brace
    def feed_bytes(self, bs):
        for b in bs:
            if not self.feed(b): return False
        return True

def accepts(raw):
    """(alive_through_all_bytes, done, reject_offset) for a raw output string."""
    s = State(); bs = raw.encode("utf-8")
    for n, b in enumerate(bs):
        if not s.feed(b): return False, False, n
    return True, s.done(), None

def _byte_decoder():
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]; n = 0
    for b in range(256):
        if b not in bs: bs.append(b); cs.append(256 + n); n += 1
    return {chr(c): b for b, c in zip(bs, cs)}

def token_bytes_from_tokenizer_json(path, vocab_size):
    """id -> bytes for every ordinary BPE token; None for added/special tokens and for ids the tokenizer does not define.
    Refuses a tokenizer.json whose sha256 is not the pinned one (the byte table is only verified for that file)."""
    raw = open(path, "rb").read(); h = hashlib.sha256(raw).hexdigest()
    if h != TOKENIZER_SHA256: raise ValueError(f"tokenizer.json sha256 {h} != pinned {TOKENIZER_SHA256}")
    t = json.loads(raw); dec = _byte_decoder(); tb = [None] * vocab_size
    if t["model"]["type"] != "BPE" or t["decoder"]["type"] != "ByteLevel": raise ValueError("not a byte-level BPE tokenizer")
    for s, i in t["model"]["vocab"].items():
        if i < vocab_size: tb[i] = bytes(dec[ch] for ch in s)
    for a in t["added_tokens"]:
        if a["id"] < vocab_size: tb[a["id"]] = None
    return tb

class JsonSlotConstraint:
    """transformers logits processor (callable (input_ids, scores) -> scores). One instance per generate() call (per batch).
    Rows are left-padded prompts; the first call sees the prompt only. A row is finished once it emits a stop token; after that
    its scores are passed through untouched (generate() replaces its tokens with pad). forced[i] counts the steps at which the
    model's own argmax was not allowed for row i."""
    def __init__(self, token_bytes, stop_ids, n_rows):
        self.tb = token_bytes; self.stop = frozenset(stop_ids); self.n = n_rows
        self.states = [State() for _ in range(n_rows)]; self.fin = [False] * n_rows; self.forced = [0] * n_rows
        self.L0 = None; self.steps = 0
    def allowed(self, st, t):
        if t in self.stop: return st.done()
        if t < 0 or t >= len(self.tb): return False
        b = self.tb[t]
        if b is None or st.done(): return False
        return st.clone().feed_bytes(b)
    def __call__(self, input_ids, scores):
        import torch
        B, cur = input_ids.shape
        if B != self.n: raise RuntimeError(f"jsonslot: batch {B} != {self.n}")
        if self.L0 is None: self.L0 = cur
        else:
            if cur != self.L0 + self.steps + 1: raise RuntimeError("jsonslot: input_ids length out of step")
            self.steps += 1
            last = input_ids[:, -1].tolist()
            for i, t in enumerate(last):
                if self.fin[i]: continue
                if t in self.stop:
                    if not self.states[i].done(): raise RuntimeError(f"jsonslot: row {i} stopped before the object was complete")
                    self.fin[i] = True; continue
                if not self.states[i].feed_bytes(self.tb[t] or b"\xff\xff"): raise RuntimeError(f"jsonslot: row {i} emitted disallowed token {t}")
        top = scores.argmax(dim=-1).tolist()                 # one device sync per step
        out = torch.full_like(scores, float("-inf")); keep = []; rows = []; toks = []
        for i in range(B):
            if self.fin[i]: keep.append(i); continue
            st = self.states[i]; t = top[i]
            if not self.allowed(st, t):
                t = None; order = torch.sort(scores[i], descending=True, stable=True).indices
                for lo in range(0, order.shape[0], 2048):
                    for c in order[lo:lo + 2048].tolist():
                        if self.allowed(st, c): t = c; break
                    if t is not None: break
                if t is None: raise RuntimeError(f"jsonslot: no allowed token for row {i}")
                self.forced[i] += 1
            rows.append(i); toks.append(t)
        if rows:                                              # the chosen token keeps its score (0.0 if it was not finite): the row's only finite entry
            ri = torch.tensor(rows, device=scores.device); ti = torch.tensor(toks, device=scores.device); v = scores[ri, ti]
            out[ri, ti] = torch.where(torch.isfinite(v), v, torch.zeros_like(v))
        if keep: out[keep] = scores[keep]
        return out
