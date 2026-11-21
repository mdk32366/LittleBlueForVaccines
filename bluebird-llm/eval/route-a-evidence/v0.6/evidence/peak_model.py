# @0.6: remaining-batch prompt lengths (real rows, M2 plan) and the peak model from the copied smoke runs + Emma-reported full-run numbers.
# Stdlib + the v0.5 stage's evalcore.py (no bytecode written). usage: python -B peak_model.py <v0.5 stage>
import json, sys; sys.dont_write_bytecode = True; C = sys.argv[1]; sys.path.insert(0, C)
from evalcore import plan_batches
rows = [json.loads(l) for l in open(f"{C}/eval_rows.jsonl", encoding="utf-8")]
o = []; p = o.append
for mode, key, tag in (("fewshot", "fs_prompt_tokens", "S"), ("zero", "prompt_tokens", "T")):
    B = plan_batches(rows, mode, 8); mx = [max(r[key] for r in b) for b in B]
    full = B[:-1] if len(B[-1]) < 8 else B; idx = sorted({round(i * (len(full) - 1) / 7) for i in range(8)})
    sm = plan_batches(rows, mode, 8, limit=64)
    assert [[r["id"] for r in b] for b in sm] == [[r["id"] for r in full[i]] for i in idx]
    p(f"## {tag} ({mode}, batch 8): {len(B)} batches, last batch {len(B[-1])} row(s)")
    p(f"- smoke batches (full-run index: max prompt tokens): " + ", ".join(f"{i}: {mx[i]}" for i in idx))
    if tag == "S":
        done = sum(len(B[k]) for k in range(365)); rem = list(range(365, len(B)))
        p(f"- rows in batches 0-364: {done} (= 'after row 2920'); remaining batches {rem[0]}-{rem[-1]}: {len(rem)} batches, {sum(len(B[k]) for k in rem)} rows")
        p(f"- max prompt tokens: batch 363 {mx[363]}, 364 {mx[364]}, remaining {min(mx[k] for k in rem)}-{max(mx[k] for k in rem)}")
        p("- remaining batches, max prompt tokens per batch: " + " ".join(str(mx[k]) for k in rem))
        pad = lambda ks: sum(mx[k] * len(B[k]) for k in ks)
        f = (pad(rem) / len(rem)) / (pad(range(365)) / 365); p(f"- padded prompt tokens per batch, remaining / batches 0-364: {f:.3f}")
def peaks(path): return [json.loads(l)["peak_alloc"] for l in open(path) if l.startswith('{"batch"')]
sS, sT = peaks(f"{C}/runs/r03/smoke-S.out"), peaks(f"{C}/runs/r03/smoke-T.out")
rS = json.load(open(f"{C}/runs/r03/out-smoke-S/run-qwen25-3b-base-fs.json"))["sessions"][-1]; rT = json.load(open(f"{C}/runs/r03/out-smoke-T/run-bluebird-v1.0-e2.json"))["sessions"][-1]
p("## Measured peaks (box copies)")
p(f"- smoke S per-batch cumulative peak_alloc: {sS}; session peak_alloc {rS['peak_alloc_bytes']}, peak_reserved {rS['peak_reserved_bytes']} (reserved/alloc {rS['peak_reserved_bytes']/rS['peak_alloc_bytes']:.3f})")
p(f"- smoke T per-batch cumulative peak_alloc: {sT}; session peak_alloc {rT['peak_alloc_bytes']}, peak_reserved {rT['peak_reserved_bytes']} (reserved/alloc {rT['peak_reserved_bytes']/rT['peak_alloc_bytes']:.3f})")
pf = json.load(open(f"{C}/runs/r03/pre-T/PREFLIGHT-bluebird-v1.0-e2-2.json"))
p(f"- PREFLIGHT-2: gpu_free_at_start {pf['session']['gpu_free_at_start']}, gpu_total {pf['session']['gpu_total']}, preflight peak_alloc {pf['peak_alloc_bytes']}, peak_reserved {pf['peak_reserved_bytes']}")
p("## Emma-reported (laptop, 7:40 PM PT; not on the box)")
p("- full S: peak_alloc 6990548992 after batch 363; ABORT 3 peak_alloc 7001188352 after row 2920 (batch 364); full T (E4): about 5.28e9")
p("## Model")
B0 = sS[-1]; s = (7001188352 - B0) / 365
p(f"- length model rejected: smoke S ran full-run batches 381 and 445 (the longest full batch, 1994 tokens) in a fresh session at <= {B0}; under a length model batch 445 would need >= 7.0e9")
p(f"- in-session growth: (7001188352 - {B0}) / 365 = {s:.0f} B per batch on average (T: (5.28e9 - {sT[-1]}) / 447 = {(5.28e9 - sT[-1]) / 447:.0f}, Emma-reported endpoint)")
for lab, fac in (("per batch", 1.0), ("per padded prompt token", f)):
    g = s * fac * 82; p(f"- fresh-session projection, growth {lab}: {B0} + {g:.0f} = {B0 + g:.0f}; margin to 7.0e9 {7.0e9 - B0 - g:.0f}")
p(f"- growth rate needed to reach 7.0e9 within 82 batches from {B0}: {(7.0e9 - B0) / 82:.0f} B per batch = {(7.0e9 - B0) / 82 / s:.2f} x the observed average")
p(f"- VRAM: free at start {pf['session']['gpu_free_at_start']} of {pf['session']['gpu_total']}; at 7.0e9 allocated the reserved pool is >= 7.0e9, i.e. within {pf['session']['gpu_free_at_start'] - 7.0e9:.0f} B of all free memory")
p("- not fitted: the per-batch curve of the stopped session (only in the laptop's eval-S.out; E5-S1-keep copies it and e5s1_check.py fits it)")
print("\n".join(o))
