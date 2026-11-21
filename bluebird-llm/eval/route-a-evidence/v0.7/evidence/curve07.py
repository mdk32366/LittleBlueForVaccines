"""@0.7 evidence: per-batch analysis of the real e5-s1 copy (box). Read-only. Run: python3 -B evidence/curve07.py"""
import json, sys, re, hashlib
sys.dont_write_bytecode = True
V5 = "/workspace/littleblue-eval-v0.5"; sys.path.insert(0, V5)
from evalcore import plan_batches
R = V5 + "/runs/r03"
rows = [json.loads(l) for l in open(V5 + "/eval_rows.jsonl")]
B = plan_batches(rows, "fewshot", 8)
prog = [json.loads(l) for l in open(R + "/e5-s1/eval-S.out") if l.startswith('{"progress"') or '"batch"' in l and '"peak_alloc"' in l]
P = {}
for l in open(R + "/e5-s1/eval-S.out"):
    try: d = json.loads(l)
    except Exception: continue
    if isinstance(d, dict) and "peak_alloc" in d and "batch" in d: P[d["batch"]] = d
import re as _re
_ab = [l for l in open(R + "/e5-s1/eval-S.out") if l.startswith("ABORT 3 peak_alloc ")]
if _ab:
    _m = _re.match(r"ABORT 3 peak_alloc (\d+) > \S+ after row (\d+)", _ab[-1]); _row = int(_m.group(2))
    assert _row % 8 == 0; P[_row // 8 - 1] = {"peak_alloc": int(_m.group(1)), "sec_per_row": "n/a (ABORT line; batch written, no progress line)"}
L = lambda k: max(r["fs_prompt_tokens"] for r in B[k]); pad = lambda k: L(k) - min(r["fs_prompt_tokens"] for r in B[k])
ks = sorted(P); prev = None; rec = []
for k in ks:
    v = P[k]["peak_alloc"]
    if prev is None or v > prev: rec.append((k, L(k), pad(k), v, v - (prev or 0)))
    prev = v
print("progress lines", len(ks), "batches", ks[0], "..", ks[-1])
print("record-raising batches (own peak exact): batch L pad peak step")
for r in rec: print("  %4d %5d %4d %d %+d" % r)
pts = [(l, v) for k, l, p, v, s in rec if p == 0 and l >= 900]
n = len(pts); X = [l * l for l, _ in pts]; Y = [v for _, v in pts]
mx, my = sum(X) / n, sum(Y) / n
c = sum((x - mx) * (y - my) for x, y in zip(X, Y)) / sum((x - mx) ** 2 for x in X); a = my - c * mx
print("fit pad-0 records (L>=900, n=%d): peak = %.4e + %.2f * L^2" % (n, a, c))
for l, v in pts: print("   L=%d obs=%d fit=%.4e resid=%+.2f%%" % (l, v, a + c * l * l, 100 * (v - a - c * l * l) / v))
# bound check: every pad-0 batch done must have own peak <= session max at that time
bad = [(k, L(k)) for k in ks if pad(k) == 0 and len(B[k]) == 8 and a + c * L(k) ** 2 > P[k]["peak_alloc"] * 1.02]
print("pad-0 done batches where fit exceeds the recorded session max by >2%:", bad)
pad0_done = sum(1 for k in ks if pad(k) == 0 and len(B[k]) == 8)
print("pad-0 batches done:", pad0_done)
print("remaining batches 365-446:", len(B) - 365, "rows", sum(len(B[k]) for k in range(365, len(B))))
rem0 = [(k, L(k), a + c * L(k) ** 2) for k in range(365, len(B)) if pad(k) == 0 and len(B[k]) == 8]
for k, l, p in rem0: print("  remaining pad-0 batch %d L=%d predicted own peak %.3e" % (k, l, p))
print("first remaining pad-0 batch:", rem0[0][0] if rem0 else None)
# zero-shot T cross-check (fit from S only)
BT = plan_batches(rows, "zero", 8)
t0 = max(((k, max(r["prompt_tokens"] for r in b)) for k, b in enumerate(BT) if len(b) == 8 and len({r["prompt_tokens"] for r in b}) == 1), key=lambda x: x[1])
print("T longest pad-0 batch %d L=%d -> S-fit predicts %.3e (Emma-reported full-T peak ~5.28e9)" % (t0[0], t0[1], a + c * t0[1] ** 2))
full = B[:-1]; idx = sorted({round(i * (len(full) - 1) / 7) for i in range(8)})
print("smoke-S full indices", idx, "L/pad", [(L(i), pad(i)) for i in idx])
print("smoke ran 356:", 356 in idx)
for k in (355, 356, 357, 361, 362, 364):
    d = P[k]; pass
    print("batch %d L=%d pad=%d peak=%d sec=%s" % (k, L(k), pad(k), d["peak_alloc"], d.get("sec_per_row", d.get("sec"))))
