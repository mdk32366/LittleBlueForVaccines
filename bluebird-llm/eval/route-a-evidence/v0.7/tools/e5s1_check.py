# @0.7 box check of a copied, stopped out-S session (no card; box only; reads, never writes). Stdlib + the v0.5 stage's evalcore.py.
# Replaces @0.6 ed4208b7, whose C1/C2 assumed gradual in-session growth (falsified by the real E5-S1 copy, ORDER@0.7 §g).
# Integrity I0-I11 (I8-I11 = N30 a-e), then C3 early curve vs smoke-S (N29), C1 step attribution, C2 zero-padding fit
# (peak = a + c*L^2 over this session's record-raising zero-padding batches), C4 per-batch projection for the remaining batches.
# N31: the ONLY pass is exit code 0 with last line starting "E5S1 GO"; anything else (exit 1, an internal-error STOP, a traceback,
# no output) is STOP. Any exception is caught and printed as an E5S1 STOP line.
# usage: python -B e5s1_check.py --stage <v0.5 stage> --dir <copied dir: eval-S.out, eval-S.err, out-S/> --smoke_out <smoke-S.out> --smoke_run <out-smoke-S run json>
import argparse, json, os, re, sys
sys.dont_write_bytecode = True
ap = argparse.ArgumentParser(); ap.add_argument("--stage", required=True); ap.add_argument("--dir", required=True)
ap.add_argument("--smoke_out", required=True); ap.add_argument("--smoke_run", required=True)
ap.add_argument("--go_max", type=float, default=6.5e9); ap.add_argument("--early_margin", type=float, default=1.0e9)
ap.add_argument("--step_min", type=float, default=1.0e8); ap.add_argument("--fit_tol", type=float, default=0.01)
a = ap.parse_args()
RUN_PIN = "0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d"; ROWS_SHA = "dd3fc66d50373f123ce4f76602658794a438f6250c0953e8fffa7c84934db899"
SMOKE_OUT_SHA = "4b8b2cab351ced18d554494e64f1af0580e2498e01d159db26f4302a0f3819b9"; SMOKE_RUN_SHA = "2b30d3fc409db148fb5027206ed14f24f1bf36d3a3614df1176e4a2b1384739f"
VERSIONS = {"bitsandbytes": "0.50.2", "cuda": "12.8", "peft": "0.21.2", "torch": "2.11.0+cu128", "transformers": "5.22.2"}
GREEDY = {"bad_words_ids": None, "begin_suppress_tokens": None, "do_sample": False, "eos_token_id": [151645, 151643], "max_new_tokens": 128,
          "min_new_tokens": None, "min_p": None, "no_repeat_ngram_size": 0, "num_beams": 1, "num_return_sequences": 1, "pad_token_id": 151643,
          "repetition_penalty": 1.0, "suppress_tokens": None, "temperature": None, "top_k": None, "top_p": None, "typical_p": 1.0}
SMOKE_FULL = [0, 64, 127, 191, 254, 318, 381, 445]; EARLY = 6       # C3 compares full batches 0, 64, 127, 191, 254, 318
TAG = "qwen25-3b-base-fs"; LIMIT = 7.0e9
fails = []
def chk(name, ok, **kw):
    print(json.dumps({"check": name, "ok": bool(ok), **kw}))
    if not ok: fails.append(name.split(" ")[0])
def main():
    sys.path.insert(0, a.stage)
    from evalcore import plan_batches, file_sha256
    od = os.path.join(a.dir, "out-S"); P = os.path.join(od, f"predictions-{TAG}.jsonl"); RJ = os.path.join(od, f"run-{TAG}.json")
    rows = [json.loads(l) for l in open(os.path.join(a.stage, "eval_rows.jsonl"), encoding="utf-8")]
    chk("I0 stage rows sha256 = RUN-INPUTS line", file_sha256(os.path.join(a.stage, "eval_rows.jsonl")) == ROWS_SHA)
    B = plan_batches(rows, "fewshot", 8); bidx = {r["id"]: k for k, b in enumerate(B) for r in b}
    Lk = lambda k: max(r["fs_prompt_tokens"] for r in B[k]); pad = lambda k: Lk(k) - min(r["fs_prompt_tokens"] for r in B[k])
    names = sorted(os.listdir(od)) if os.path.isdir(od) else []
    aborts = sorted((f for f in names if re.match(r"^ABORT-\d+\.json$", f)), key=lambda f: int(f[6:-5]))
    chk("I1 out-S holds only the run json, predictions and ABORT-n files; no eval.lock", names and set(names) - set(aborts) == {os.path.basename(P), os.path.basename(RJ)}, files=names)
    J = json.load(open(RJ)); c = J["cfg"]; S = J["sessions"]; last = S[-1]
    chk("I2 run json: status aborted; cfg fewshot, batch 8, limit 0, all kinds, backend hf, no adapter, RUN PIN, rows sha; 3569 rows / 447 batches planned",
        J.get("status") == "aborted" and c.get("mode") == "fewshot" and c.get("batch") == 8 and c.get("limit") == 0 and c.get("kinds") == "" and c.get("backend") == "hf"
        and c.get("adapter_path") is None and c.get("manifest_sha256") == RUN_PIN and c.get("rows_sha256") == ROWS_SHA and J.get("planned_rows") == 3569 and J.get("planned_batches") == 447)
    chk("I3 last session: exit 3, its ABORT file is the newest, pinned 5.22.2 PINNED_UNVERIFIED, processors [], min_free 7000000000.0",
        last.get("exit") == 3 and aborts and last.get("abort_file") == aborts[-1] and last.get("transformers_pin") == "5.22.2" and last.get("transformers_check") == "PINNED_UNVERIFIED"
        and last.get("logits_processors") == [] and last.get("min_free") == 7.0e9)
    A = json.load(open(os.path.join(od, aborts[-1]))) if aborts else {}
    m = re.match(r"^peak_alloc (\d+) > 7000000000\.0 after row (\d+)$", A.get("abort", ""))
    chk("I4 newest ABORT: exit 3, pid = last session pid, cause peak_alloc > 7000000000.0", A.get("exit") == 3 and A.get("pid") == last.get("pid") and m, abort=A.get("abort"))
    raw = open(P, "rb").read() if os.path.exists(P) else b""; lines = raw.split(b"\n"); tail = lines.pop() if lines else b""
    recs, bad = [], []
    for n, ln in enumerate(lines):
        try:
            o = json.loads(ln); assert isinstance(o, dict) and isinstance(o.get("id"), str) and isinstance(o.get("raw"), str); recs.append(o)
        except Exception: bad.append(n + 1)
    ids = [o["id"] for o in recs]; have = set(ids)
    complete = sorted(k for k in range(len(B)) if all(r["id"] in have for r in B[k])); partial = sorted({bidx[i] for i in have if i in bidx} - set(complete)); nb = len(complete)
    chk("I5 predictions: no torn tail, every line a record, no duplicate or unplanned id, batch field = plan, only whole batches, batches 0..k-1 contiguous",
        nb >= 1 and not tail and not bad and len(ids) == len(have) and have <= set(bidx) and all(o.get("batch") == bidx[o["id"]] for o in recs) and not partial and complete == list(range(nb)),
        lines=len(recs), whole_batches=nb, partial=partial, bad_lines=bad[:5])
    out = [l.rstrip("\r") for l in open(os.path.join(a.dir, "eval-S.out"), encoding="utf-8", errors="replace").read().splitlines()]
    prog = [json.loads(l) for l in out if l.startswith('{"batch"')]; lastline = out[-1] if out else ""
    d0 = last.get("batches_done_at_start", 0) or 0; rows_done = sum(len(B[k]) for k in range(d0, nb))
    chk("I6 eval-S.out last line = the ABORT 3 line of the newest ABORT, after row = rows this session wrote",
        m and lastline == f"ABORT 3 {A.get('abort')}" and int(m.group(2)) == rows_done, last_line=lastline, rows_this_session=rows_done)
    ks = [p["batch"] for p in prog]
    chk("I7 progress lines: one per batch of this session, consecutive from batches_done_at_start, ending one batch before the abort batch",
        ks == list(range(d0, nb - 1)), first=ks[:1], last=ks[-1:], n=len(ks))
    # ---- N30 a-e
    chk("I8 (N30a) exactly one session in the run json, started from batch 0 (the curve is one process from load)", len(S) == 1 and d0 == 0, sessions=len(S))
    SJ = json.load(open(a.smoke_run)); sc = SJ["cfg"]; ss = SJ["sessions"][-1]
    chk("I9 (N30b) full greedy: merged generation config = the literal greedy config = smoke-S's", last.get("merged_generation_config") == GREEDY and ss.get("merged_generation_config") == GREEDY)
    diff = sorted(k for k in set(c) | set(sc) if c.get(k) != sc.get(k))
    chk("I10 (N30c) full cfg = smoke-S cfg except limit (0 vs 64); library versions = literal = smoke-S's", diff == ["limit"] and c.get("limit") == 0 and sc.get("limit") == 64
        and last.get("versions") == VERSIONS and ss.get("versions") == VERSIONS, cfg_diff=diff, versions=last.get("versions"))
    sraw = open(a.smoke_out, "rb").read(); sl = [l.rstrip("\r") for l in sraw.decode("utf-8", "replace").splitlines()]
    sp = [json.loads(l) for l in sl if l.startswith('{"batch"')]
    chk("I11 (N30d) smoke-S.out sha = 4b8b2cab...19b9 pin, 8 progress lines batches 0-7 of 8, last line EVAL_DONE qwen25-3b-base-fs 64 complete; smoke run json sha pin, status complete",
        file_sha256(a.smoke_out) == SMOKE_OUT_SHA and [p["batch"] for p in sp] == list(range(8)) and all(p["of"] == 8 for p in sp)
        and bool(sl) and sl[-1].startswith("EVAL_DONE qwen25-3b-base-fs 64 complete ") and file_sha256(a.smoke_run) == SMOKE_RUN_SHA and SJ.get("status") == "complete")
    peaks = [p["peak_alloc"] for p in prog] + ([int(m.group(1))] if m else []); bat = ks + [nb - 1]
    chk("I12 (N30e) curve never decreases; every progress-line peak <= 7000000000; the ABORT value > 7000000000",
        bool(m) and all(peaks[i] >= peaks[i - 1] for i in range(1, len(peaks))) and all(p <= LIMIT for p in peaks[:-1]) and peaks[-1] > LIMIT)
    if fails: return "no curve checks (integrity failed)"
    # ---- C3 (N29) early curve vs smoke-S
    full = B[:-1]; idx = sorted({round(i * (len(full) - 1) / 7) for i in range(8)})
    assert idx == SMOKE_FULL, idx
    at = dict(zip(bat, peaks)); early = [(k, at[k], sp[j]["peak_alloc"]) for j, k in enumerate(SMOKE_FULL[:EARLY])]
    chk("C3 (N29) session peak at full batches 0,64,127,191,254,318 <= smoke-S peak at that batch + 1.0e9", all(s <= q + a.early_margin for _, s, q in early),
        early=[{"batch": k, "session": s, "smoke": q} for k, s, q in early])
    # ---- C1 step attribution: every increase > step_min at a batch with L >= 1000 is at a zero-padding batch
    steps = [(bat[i], peaks[i] - peaks[i - 1]) for i in range(1, len(peaks))]
    big = [(k, s, Lk(k), pad(k)) for k, s in steps if s > a.step_min]
    chk("C1 every single-batch increase > 1e8 at a batch with L >= 1000 is at a zero-padding batch", all(p == 0 for k, s, l, p in big if l >= 1000),
        steps=[{"batch": k, "bytes": s, "L": l, "pad": p} for k, s, l, p in big])
    # ---- C2 zero-padding fit over record-raising zero-padding batches (own peak exact), L >= 900
    rec = []; prev = 0
    for k, p in zip(bat, peaks):
        if p > prev and pad(k) == 0 and len(B[k]) == 8 and Lk(k) >= 900: rec.append((Lk(k), p))
        prev = max(prev, p)
    ok2 = len(rec) >= 3 and max(l for l, _ in rec) - min(l for l, _ in rec) >= 500
    if ok2:
        X = [l * l for l, _ in rec]; Y = [p for _, p in rec]; mx, my = sum(X) / len(X), sum(Y) / len(Y)
        cc = sum((x - mx) * (y - my) for x, y in zip(X, Y)) / sum((x - mx) ** 2 for x in X); aa = my - cc * mx
        res = max(abs(y - aa - cc * x) / y for x, y in zip(X, Y))
        over = [k for k in bat if pad(k) == 0 and len(B[k]) == 8 and aa + cc * Lk(k) ** 2 > at[k] * (1 + 2 * a.fit_tol)]
        ok2 = cc > 0 and res <= a.fit_tol and not over
        chk("C2 zero-padding records fit peak = a + c*L^2 within 1%; no done zero-padding batch above the session max by > 2%", ok2,
            points=len(rec), a=round(aa), c=round(cc, 2), max_rel_resid=round(res, 4), over=over[:5])
    else: chk("C2 zero-padding records fit (>= 3 points spanning >= 500 tokens)", False, points=len(rec))
    if not ok2: return "no projection (C2 fit failed)"
    # ---- C4 per-batch projection for the remaining batches in a fresh session
    pb = max(q["peak_alloc"] for j, q in enumerate(sp) if pad(SMOKE_FULL[j]) > 0)      # fresh smoke-S, padded batches only
    proj = []
    for k in range(nb, len(B)):
        if pad(k) == 0: proj.append((k, aa + cc * Lk(k) ** 2 * len(B[k]) / 8, "zero-padding fit"))
        else: proj.append((k, pb if Lk(k) <= max(Lk(j) for j in SMOKE_FULL if pad(j) > 0) else float("inf"), "padded: smoke-S fresh bound"))
    top = max(proj, key=lambda t: t[1]); over = [(k, round(p)) for k, p, _ in proj if p > a.go_max]
    print(json.dumps({"remaining_batches": len(proj), "remaining_zero_padding": [(k, Lk(k), round(p)) for k, p, w in proj if w == "zero-padding fit"],
                      "padded_bound_from_smoke_S": pb, "max_projected": {"batch": top[0], "bytes": round(top[1])}, "over_go_max": over, "go_max": a.go_max, "peak_limit": LIMIT}))
    chk("C4 every remaining batch's projected own peak <= go_max", not over, first_over=over[:1], n_over=len(over))
    return f"max projected per-batch peak {round(top[1])} B at batch {top[0]} (go_max {a.go_max:.0f}, limit 7000000000)"
try:
    txt = main()
    print(f"E5S1 GO: I0-I12, C1-C4 pass; {txt}" if not fails else f"E5S1 STOP: {', '.join(fails)} failed; {txt}; no relaunch, Trinity re-plans")
    sys.exit(0 if not fails else 1)
except SystemExit: raise
except BaseException as e:
    print(f"E5S1 STOP: internal error {type(e).__name__}: {str(e)[:200]}; no relaunch, Trinity re-plans"); sys.exit(1)
