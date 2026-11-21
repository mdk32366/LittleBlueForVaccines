"""@0.7 evidence: batches 350-364 of the real E5-S1 copy, row by row (ids, prompt lengths, padding, generated tokens, hit_max, strict parse, repetition, output head). Read-only.
usage: python3 -B evidence/batches07.py"""
import json, sys
sys.dont_write_bytecode = True
V5 = "/workspace/littleblue-eval-v0.5"; sys.path.insert(0, V5)
from evalcore import plan_batches, parse_strict
rows = [json.loads(l) for l in open(V5 + "/eval_rows.jsonl")]; B = plan_batches(rows, "fewshot", 8)
P = {json.loads(l)["id"]: json.loads(l) for l in open(V5 + "/runs/r03/e5-s1/out-S/predictions-qwen25-3b-base-fs.jsonl")}
prog = {}
for l in open(V5 + "/runs/r03/e5-s1/eval-S.out"):
    if l.startswith('{"batch"'): d = json.loads(l); prog[d["batch"]] = d
def rep(s): w = s.split(); return max([w.count(x) for x in set(w)] or [0])
for k in range(350, 365):
    L = [r["fs_prompt_tokens"] for r in B[k]]; d = prog.get(k, {})
    print(f"batch {k}: L {min(L)}-{max(L)} padding {max(L) - min(L)} sec_per_row {d.get('sec_per_row', 'n/a (abort batch)')} session_max_after {d.get('peak_alloc', '7001188352 (ABORT line)')}")
    for r in B[k]:
        p = P[r["id"]]; why = parse_strict(p["raw"])[1] or "ok"
        print(f"  {r['id']:<42} L={r['fs_prompt_tokens']} new={p['new_tokens']:>3} hit_max={p['hit_max']} strict={why} max_word_repeat={rep(p['raw'])} special={'<|' in p['raw']} raw={p['raw'][:90]!r}")
