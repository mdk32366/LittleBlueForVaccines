# JSON-fix @0.0 measurement (box, CPU, read-only on the v0.5 stage). Prints evidence for ORDER-bluebird-json-fix@0.0 §1.
# Run: PYTHONDONTWRITEBYTECODE=1 <venv-with-tokenizers>/bin/python -B evidence/measure_jf.py
import json, sys, os, re, statistics, collections
V05 = "/workspace/littleblue-eval-v0.5"; R03 = V05 + "/runs/r03"
sys.dont_write_bytecode = True; sys.path.insert(0, V05)
from evalcore import plan_batches, parse_strict, SEQ
from tokenizers import Tokenizer
tk = Tokenizer.from_file(V05 + "/tests/fixtures/model/tokenizer.json")
def ntok(s): return len(tk.encode(s, add_special_tokens=False).ids)
rows = [json.loads(l) for l in open(V05 + "/eval_rows.jsonl", encoding="utf-8")]; byid = {r["id"]: r for r in rows}
P = [json.loads(l) for l in open(R03 + "/out-T/predictions-bluebird-v1.0-e2.jsonl", encoding="utf-8")]; pb = {p["id"]: p for p in P}
out = {}
# A. re-encode agreement (decode->encode token count vs recorded new_tokens)
agree = sum(ntok(p["raw"]) == p["new_tokens"] for p in P); diffs = [ntok(p["raw"]) - p["new_tokens"] for p in P]
out["A_reencode_agree"] = [agree, len(P)]; out["A_reencode_diff_minmax"] = [min(diffs), max(diffs)]
# B. the 7 truncated test rows: completion length
trunc = sorted(p["id"] for p in P if p["hit_max"] and p["id"].startswith("test:"))
B = []; HYP = {"primary": {}, "upper": {}}
for i in trunc:
    p = pb[i]; r = byid[i]; raw = p["raw"]; u = {x["id"]: x["text"] for x in r["units"]}
    sysid = r["system_id"] if "system_id" in r else None
    if i.endswith("Q12"):
        doc = [k for k in u if k.endswith("#4.1")][0][:-4]
        bands = [u[doc + "#4.1"], u[doc + "#4.2"], u[doc + "#4.3"]]
        start = raw.rindex('"text": "') + len('"text": "'); have = raw[start:]
        BS2N = "\\\\n"                                        # the two characters backslash-backslash + n as they stand in the JSON source
        sep = (BS2N + BS2N) if (BS2N + "\\\\") in have else (BS2N if BS2N in have else " ")
        full_src = sep.join(bands)                               # band text has no quotes/backslashes, so source == text
        assert full_src.startswith(have), (i, have[-40:], sep)
        comp = raw + full_src[len(have):] + '"}}}'
        HYP["primary"][i] = comp
        o, err = parse_strict(comp); B.append({"id": i, "prompt_tokens": r["prompt_tokens"], "hyp": f"S2 = bands 4.1+4.2+4.3 joined by {sep!r}", "complete_tokens": ntok(comp), "valid": err is None})
        # upper bound: 3 bands + unit 5.x appended (the cited anchor was #5)
        five = [k for k in u if k.startswith(doc + "#5")]
        comp2 = raw + sep.join(bands + [u[k] for k in five])[len(have):] + '"}}}'
        HYP["upper"][i] = comp2
        B.append({"id": i, "prompt_tokens": r["prompt_tokens"], "hyp": "upper: bands + all #5.x units", "complete_tokens": ntok(comp2), "valid": parse_strict(comp2)[1] is None})
    else:  # Q28: cut inside S3's anchor
        cut = raw.rindex('"anchor": "') + len('"anchor": "'); doc = raw[cut:]
        exh = [k for k in u if "-EXH1#" in k]
        cands = {"short value '430'": '430', "a whole EXH1 line": max((t for k in exh for t in u[k].split("\n")), key=len), "longest whole EXH1 unit": max((u[k] for k in exh), key=len)}
        for name, txt in cands.items():
            comp = raw[:cut] + (doc if doc.endswith("#2") or "#" in doc else doc) + '", "text": ' + json.dumps(txt) + "}}}"
            if name == "a whole EXH1 line": HYP["primary"][i] = comp
            if name == "longest whole EXH1 unit": HYP["upper"][i] = comp
            B.append({"id": i, "prompt_tokens": r["prompt_tokens"], "hyp": f"S3 text = {name}", "complete_tokens": ntok(comp), "valid": parse_strict(comp)[1] is None})
out["B_truncated"] = B
# C. tails
nt = sorted(p["new_tokens"] for p in P)
q = lambda xs, f: xs[min(len(xs) - 1, int(f * len(xs)))]
out["C_new_tokens_all"] = {"n": len(nt), "p50": q(nt, .5), "p90": q(nt, .9), "p99": q(nt, .99), "p999": q(nt, .999), "max": nt[-1], "ge100": sum(x >= 100 for x in nt), "ge120": sum(x >= 120 for x in nt), "eq128": sum(x == 128 for x in nt), "top12": nt[-12:]}
valid_nt = sorted(p["new_tokens"] for p in P if parse_strict(p["raw"])[1] is None)
out["C_new_tokens_valid_max"] = valid_nt[-1]
g = sorted(ntok(json.dumps(r["gold"])) for r in rows)
out["C_gold_json_tokens"] = {"p50": q(g, .5), "p99": q(g, .99), "max": g[-1]}
# D. batch plan (zero-shot, batch 8) and the per-batch cap clamp min(cap, SEQ - L)
bs = plan_batches(rows, "zero", 8)
D = []
for k, b in enumerate(bs):
    Ls = [r["prompt_tokens"] for r in b]; D.append({"k": k, "n": len(b), "L": max(Ls), "pad": max(Ls) - min(Ls), "maxnew128": max(pb[r["id"]]["new_tokens"] for r in b),
                                                    "hit": sum(pb[r["id"]]["hit_max"] for r in b), "batch_rec": {pb[r["id"]]["batch"] for r in b}})
assert all(d["batch_rec"] == {d["k"]} for d in D), "plan != recorded batch index"
for d in D: del d["batch_rec"]
for cap in (192, 256, 320, 384):
    capped = [d for d in D if SEQ - d["L"] < cap]
    out[f"D_cap{cap}"] = {"batches_clamped": len(capped), "rows_clamped": sum(d["n"] for d in capped), "min_effective_cap": min(min(cap, SEQ - d["L"]) for d in D),
                          "rows_over_SEQ_unclamped": sum(1 for r in rows if r["prompt_tokens"] + cap > SEQ)}
out["D_batches"] = len(D); out["D_hit_batches"] = [d["k"] for d in D if d["hit"]]
zp = [d for d in D if d["pad"] == 0 and d["n"] == 8]; out["D_zero_pad_full_batches"] = len(zp); out["D_longest_zero_pad"] = max(zp, key=lambda d: d["L"])
# E. T memory curve from eval-T.out
prog = [json.loads(l) for l in open(R03 + "/eval-T.out", encoding="utf-8") if l.startswith('{"batch"')]
assert [x["batch"] for x in prog] == list(range(len(D)))
E = []; prev = 0
for x in prog:
    if x["peak_alloc"] > prev: E.append({"k": x["batch"], "L": D[x["batch"]]["L"], "pad": D[x["batch"]]["pad"], "n": D[x["batch"]]["n"], "peak": x["peak_alloc"], "step": x["peak_alloc"] - prev})
    prev = x["peak_alloc"]
out["E_record_batches"] = len(E); out["E_last_records"] = E[-8:]
pts = [e for e in E if e["pad"] == 0 and e["n"] == 8 and e["L"] >= 900]
if len(pts) >= 3:
    xs = [e["L"] ** 2 for e in pts]; ys = [e["peak"] for e in pts]; mx, my = statistics.mean(xs), statistics.mean(ys)
    c = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs); a0 = my - c * mx
    out["E_T_fit"] = {"points": len(pts), "L_range": [pts[0]["L"], pts[-1]["L"]], "a": round(a0), "c": round(c, 2), "max_resid_pct": round(max(abs(y - (a0 + c * x)) / y * 100 for x, y in zip(xs, ys)), 3)}
Sfit = lambda L: 2.5358e9 + 1410.88 * L * L
out["E_S_fit_at_T_longest_zero_pad"] = round(Sfit(out["D_longest_zero_pad"]["L"]))
out["E_T_peak_measured"] = max(x["peak_alloc"] for x in prog)
KV = 36 * 2 * 2 * 128 * 2   # Qwen2.5-3B: 36 layers, K+V, 2 KV heads, head_dim 128, bf16 bytes  (published config; config.json not on the box)
out["E_kv_bytes_per_token_row"] = KV
for cap in (256,):
    worst = max(D, key=lambda d: d["n"] * (d["L"] + min(cap, SEQ - d["L"])))
    out[f"E_kv_extra_cap{cap}_max"] = max(d["n"] * (min(cap, SEQ - d["L"]) - 128) * KV for d in D)
    out[f"E_kv_extra_at_longest_zero_pad_cap{cap}"] = 8 * (min(cap, SEQ - out["D_longest_zero_pad"]["L"]) - 128) * KV
# F. runtime: per-batch seconds ~ a + b*maxnew (decode steps), padded and zero-pad separately
secs = [x["sec_per_row"] * D[x["batch"]]["n"] for x in prog]
out["F_gen_seconds_recorded"] = json.load(open(R03 + "/out-T/run-bluebird-v1.0-e2.json"))["sessions"][0]["gen_seconds"]; out["F_sum_batch_seconds"] = round(sum(secs), 1)
def fit(ix):
    xs = [D[k]["maxnew128"] for k in ix]; ys = [secs[k] for k in ix]; mx, my = statistics.mean(xs), statistics.mean(ys)
    b = sum((a - mx) * (y - my) for a, y in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs); return my - b * mx, b
padded = [d["k"] for d in D if d["pad"] > 0 and d["n"] == 8 and d["k"] > 0]; zpk = [d["k"] for d in zp]
for name, ix in (("padded", padded), ("zero_pad", zpk)):
    a0, b = fit(ix); out[f"F_fit_{name}"] = {"n": len(ix), "intercept_s": round(a0, 2), "s_per_decode_step": round(b, 4)}
step = max(out["F_fit_padded"]["s_per_decode_step"], out["F_fit_zero_pad"]["s_per_decode_step"])
hit = out["D_hit_batches"]
out["F_extra_if_hit_batches_run_to_cap256_s"] = round(sum((min(256, SEQ - D[k]["L"]) - 128) * step for k in hit), 1)
out["F_upper_every_batch_to_cap_s"] = round(sum(secs) + sum((min(256, SEQ - d["L"]) - d["maxnew128"]) * step for d in D), 1)
HYP["_note"] = "Hypothetical complete outputs for the 7 truncated test rows (box-constructed, NOT model outputs): primary = the quote the model had started, finished (Q12: bands 4.1-4.3; Q28: S3 = one whole EXH1 line); upper = a longer quote (Q12: + the #5.x units; Q28: the longest whole EXH1 unit)."
HYP["_tokens"] = {k: {i: ntok(v) for i, v in HYP[k].items()} for k in ("primary", "upper")}
json.dump(HYP, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "truncation-hypotheses.json"), "w"), indent=1, sort_keys=True)
print(json.dumps(out, indent=1, default=str))
