# @0.6 box check of a copied, stopped out-S session (no card; box only; reads, never writes). Stdlib + the v0.5 stage's evalcore.py.
# Integrity (I1-I7) of the stopped run as eval.py would resume it, then the per-batch peak curve of the stopped session from its .out
# and a projection for a FRESH session over the remaining batches. Last line: "E5S1 GO ..." or "E5S1 STOP ...".
# usage: python -B e5s1_check.py --stage <v0.5 stage> --dir <copied dir holding eval-S.out, eval-S.err, out-S/> --smoke_out <smoke-S.out>
import argparse, json, os, re, sys
ap = argparse.ArgumentParser(); ap.add_argument("--stage", required=True); ap.add_argument("--dir", required=True); ap.add_argument("--smoke_out", required=True)
ap.add_argument("--go_max", type=float, default=6.5e9); ap.add_argument("--step_max", type=float, default=1.0e9)
a = ap.parse_args(); sys.dont_write_bytecode = True; sys.path.insert(0, a.stage)
from evalcore import plan_batches, file_sha256
RUN_PIN = "0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d"; ROWS_SHA = "dd3fc66d50373f123ce4f76602658794a438f6250c0953e8fffa7c84934db899"
TAG = "qwen25-3b-base-fs"; LIMIT = 7.0e9
od = os.path.join(a.dir, "out-S"); P = os.path.join(od, f"predictions-{TAG}.jsonl"); RJ = os.path.join(od, f"run-{TAG}.json")
fails = []; info = {}
def chk(name, ok, **kw):
    print(json.dumps({"check": name, "ok": bool(ok), **kw})); 
    if not ok: fails.append(name)
rows = [json.loads(l) for l in open(os.path.join(a.stage, "eval_rows.jsonl"), encoding="utf-8")]
chk("I0 stage rows sha256 = RUN-INPUTS line", file_sha256(os.path.join(a.stage, "eval_rows.jsonl")) == ROWS_SHA)
B = plan_batches(rows, "fewshot", 8); bidx = {r["id"]: k for k, b in enumerate(B) for r in b}
names = sorted(os.listdir(od)) if os.path.isdir(od) else []
aborts = sorted((f for f in names if re.match(r"^ABORT-\d+\.json$", f)), key=lambda f: int(f[6:-5]))
chk("I1 out-S holds only the run json, predictions and ABORT-n files; no eval.lock", names and set(names) - set(aborts) == {os.path.basename(P), os.path.basename(RJ)}, files=names)
J = json.load(open(RJ)) if os.path.exists(RJ) else {}; c = J.get("cfg", {}); S = J.get("sessions", []); last = S[-1] if S else {}
chk("I2 run json: status aborted; cfg fewshot, batch 8, limit 0, all kinds, backend hf, no adapter, RUN PIN, rows sha; 3569 rows / 447 batches planned",
    J.get("status") == "aborted" and c.get("mode") == "fewshot" and c.get("batch") == 8 and c.get("limit") == 0 and c.get("kinds") == "" and c.get("backend") == "hf"
    and c.get("adapter_path") is None and c.get("manifest_sha256") == RUN_PIN and c.get("rows_sha256") == ROWS_SHA and J.get("planned_rows") == 3569 and J.get("planned_batches") == 447)
mg = last.get("merged_generation_config") or {}
chk("I3 last session: exit 3, its ABORT file is the newest, pinned 5.22.2 PINNED_UNVERIFIED, greedy merged config, processors []",
    last.get("exit") == 3 and aborts and last.get("abort_file") == aborts[-1] and last.get("transformers_pin") == "5.22.2" and last.get("transformers_check") == "PINNED_UNVERIFIED"
    and mg.get("do_sample") is False and mg.get("num_beams") == 1 and last.get("logits_processors") == [], sessions=[{k: s.get(k) for k in ("pid", "started", "ended", "exit", "abort_file", "batches_done_at_start")} for s in S])
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
complete = sorted(k for k in range(len(B)) if all(r["id"] in have for r in B[k])); partial = sorted({bidx[i] for i in have if i in bidx} - set(complete))
info["complete"] = complete; nb = len(complete)
chk("I5 predictions: no torn tail, every line a record, no duplicate or unplanned id, batch field = plan, only whole batches, batches 0..k-1 contiguous",
    nb >= 1 and not tail and not bad and len(ids) == len(have) and have <= set(bidx) and all(o.get("batch") == bidx[o["id"]] for o in recs) and not partial and complete == list(range(nb)),
    lines=len(recs), whole_batches=nb, partial=partial, bad_lines=bad[:5])
out = [l.rstrip("\r") for l in open(os.path.join(a.dir, "eval-S.out"), encoding="utf-8", errors="replace").read().splitlines()]
prog = [json.loads(l) for l in out if l.startswith('{"batch"')]
lastline = out[-1] if out else ""
rows_done = sum(len(B[k]) for k in range(last.get("batches_done_at_start", 0) or 0, nb))
chk("I6 eval-S.out last line = the ABORT 3 line of the newest ABORT, after row = rows this session wrote",
    m and lastline == f"ABORT 3 {A.get('abort')}" and int(m.group(2)) == rows_done, last_line=lastline, rows_this_session=rows_done)
ks = [p["batch"] for p in prog]; d0 = last.get("batches_done_at_start", 0) or 0
chk("I7 progress lines: one per batch of this session, consecutive from batches_done_at_start, ending one batch before the abort batch",
    ks == list(range(d0, nb - 1)), first=ks[:1], last=ks[-1:], n=len(ks))
# ---- curve and projection (only meaningful if I1-I7 hold)
if not fails and m:
    peaks = [p["peak_alloc"] for p in prog] + [int(m.group(1))]; bat = ks + [nb - 1]
    steps = [(bat[i], peaks[i] - peaks[i - 1]) for i in range(1, len(peaks))]; big = max(steps, key=lambda s: s[1])
    sm = [json.loads(l) for l in open(a.smoke_out, encoding="utf-8").read().splitlines() if l.startswith('{"batch"')]; base = sm[-1]["peak_alloc"]
    L = lambda k: max(r["fs_prompt_tokens"] for r in B[k]) * len(B[k])
    rem = list(range(nb, len(B))); lrem = sum(map(L, rem)) / max(1, len(rem))
    def fit(lo):                       # least-squares slope of peak vs batch index over batches >= lo of this session
        pts = [(b, p) for b, p in zip(bat, peaks) if b >= lo]; n = len(pts); mx = sum(b for b, _ in pts) / n; my = sum(p for _, p in pts) / n
        return sum((b - mx) * (p - my) for b, p in pts) / max(1e-9, sum((b - mx) ** 2 for b, _ in pts)), sum(L(b) for b, _ in pts) / n
    s_all = (peaks[-1] - base) / len(bat); l_all = sum(L(b) for b in bat) / len(bat)
    s_200, l_200 = fit(bat[-1] - 199); s_50, l_50 = fit(bat[-1] - 49)
    g_all = s_all * (lrem / l_all) * len(rem); g_200 = s_200 * (lrem / l_200) * len(rem); g_50 = s_50 * (lrem / l_50) * len(rem)
    proj = base + max(g_all, g_200, g_50, 0)
    grid = {str(b): p for b, p in zip(bat, peaks) if b % 50 == 0 or b >= bat[-1] - 2}
    print(json.dumps({"curve": grid, "largest_single_batch_increase": {"batch": big[0], "bytes": big[1]}, "fresh_session_base_from_smoke_S": base,
                      "slope_from_smoke_base_B_per_batch": round(s_all), "slope_last200_B_per_batch": round(s_200), "slope_last50_B_per_batch": round(s_50), "remaining_batches": len(rem),
                      "token_factor_all": round(lrem / l_all, 3), "token_factor_last200": round(lrem / l_200, 3), "token_factor_last50": round(lrem / l_50, 3),
                      "growth_all": round(g_all), "growth_last200": round(g_200), "growth_last50": round(g_50), "projected_peak_fresh_session": round(proj), "go_max": a.go_max, "peak_limit": LIMIT}))
    if big[1] > a.step_max: fails.append(f"C1 single-batch increase {big[1]} B at batch {big[0]} > {a.step_max:.0f}: not gradual growth")
    if proj > a.go_max: fails.append(f"C2 projected fresh-session peak {round(proj)} > {a.go_max:.0f}")
    proj_txt = f"projected fresh-session peak {round(proj)} B (limit 7000000000)"
else: proj_txt = "no projection (integrity failed)"
print(f"E5S1 GO: integrity I0-I7 pass; {proj_txt}; resume = E5-pin-resume" if not fails else f"E5S1 STOP: {'; '.join(fails)}; no relaunch, Trinity re-plans")
sys.exit(0 if not fails else 1)
