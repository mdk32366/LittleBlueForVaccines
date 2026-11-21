"""@0.7 cases for tools/e5s1_check.py. Fixtures are built from the real E5-S1 copy (runs/r03/e5-s1, box) in a temp dir outside every stage.
usage: python3 -B tests/e5s1_suite.py [tool.py]   -> one JSON line per case, then 'SUITE n/m'. Exit 0 iff all pass.
A case passes iff the tool's exit code and LAST line match: expect GO -> rc 0 and last line starts 'E5S1 GO';
expect STOP(ids) -> rc 1, last line starts 'E5S1 STOP: ' and names every id listed (for 'internal', the internal-error line)."""
import json, os, shutil, subprocess, sys, tempfile
sys.dont_write_bytecode = True
V5 = "/workspace/littleblue-eval-v0.5"; R = V5 + "/runs/r03"; SRC = R + "/e5-s1"
SMOKE_OUT = R + "/smoke-S.out"; SMOKE_RUN = R + "/out-smoke-S/run-qwen25-3b-base-fs.json"
TOOL = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "e5s1_check.py")
TAG = "qwen25-3b-base-fs"
sys.path.insert(0, V5)
from evalcore import plan_batches
rows = [json.loads(l) for l in open(V5 + "/eval_rows.jsonl", encoding="utf-8")]; B = plan_batches(rows, "fewshot", 8)
pad = lambda k: max(r["fs_prompt_tokens"] for r in B[k]) - min(r["fs_prompt_tokens"] for r in B[k])
def rd(p): return open(p, encoding="utf-8").read()
def outmap(d, f):            # f(batch, peak) -> new peak, on progress lines of eval-S.out
    p = os.path.join(d, "eval-S.out"); L = rd(p).split("\n"); o = []
    for l in L:
        if l.startswith('{"batch"'):
            j = json.loads(l); j["peak_alloc"] = int(f(j["batch"], j["peak_alloc"])); l = json.dumps(j)
        o.append(l)
    open(p, "w", encoding="utf-8").write("\n".join(o))
def rj(d, f):
    p = os.path.join(d, "out-S", f"run-{TAG}.json"); j = json.load(open(p)); f(j); json.dump(j, open(p, "w"), indent=1)
def smoke_trunc(work):
    p = os.path.join(work, "smoke-S.trunc.out"); L = rd(SMOKE_OUT).split("\n"); open(p, "w").write("\n".join(L[:-4]) + "\n"); return p
def smoke_sha_only(work):
    p = os.path.join(work, "smoke-S.sha.out"); L = rd(SMOKE_OUT).split("\n"); L[0] = L[0].replace("VERSIONS ", "VERSIONS  ", 1); open(p, "w").write("\n".join(L)); return p
padded_late = next(k for k in range(301, 356) if pad(k) > 0)
def two_sessions(j): s = dict(j["sessions"][0]); s["pid"] = 1; j["sessions"].insert(0, s)
CASES = [  # name, fixture mutator(dir) or None, extra args, smoke_out override(work)->path or None, expect
    ("REAL copy unchanged, default go_max: STOP by C4 (projection 8.02e9 at batch 437)", None, [], None, ("STOP", ["C4"])),
    ("REAL copy, go_max 9e9 (green: every check but C4's threshold)", None, ["--go_max", "9e9"], None, ("GO", [])),
    ("P1 (Kaylee N29) flat 6.99e9 from batch 0", lambda d: outmap(d, lambda b, p: 6990000000), ["--go_max", "9e9"], None, ("STOP", ["C3"])),
    ("P2 (Kaylee N29) 6.0e9 at batch 0", lambda d: outmap(d, lambda b, p: max(p, 6.0e9)), ["--go_max", "9e9"], None, ("STOP", ["C3"])),
    ("P2b 5.04e9 first at batch 318 (last early point)", lambda d: outmap(d, lambda b, p: max(p, 5.04e9) if b >= 318 else p), ["--go_max", "9e9"], None, ("STOP", ["C3"])),
    ("P2c batches 0-15 at 3.8e9 (above smoke batch 0 + 1e9, below smoke batch 7 + 1e9)", lambda d: outmap(d, lambda b, p: 3.8e9 if b < 16 else p), ["--go_max", "9e9"], None, ("STOP", ["C3"])),
    ("P3 (Kaylee) smoke-consistent ramp to batch 318, then gradual growth to 6.99e9 at 363 (no step > 1e8)", lambda d: outmap(d, lambda b, p: p if b <= 318 else int(4526430720 + (b - 318) * (6990000000 - 4526430720) / 45)), ["--go_max", "9e9"], None, ("STOP", ["C2"])),
    ("N30a A7 two sessions", lambda d: rj(d, two_sessions), ["--go_max", "9e9"], None, ("STOP", ["I8"])),
    ("N30b A4 repetition_penalty 1.05", lambda d: rj(d, lambda j: j["sessions"][-1]["merged_generation_config"].__setitem__("repetition_penalty", 1.05)), ["--go_max", "9e9"], None, ("STOP", ["I9"])),
    ("N30b temperature 0.7", lambda d: rj(d, lambda j: j["sessions"][-1]["merged_generation_config"].__setitem__("temperature", 0.7)), ["--go_max", "9e9"], None, ("STOP", ["I9"])),
    ("N30c A1 max_new_tokens 64", lambda d: rj(d, lambda j: j["cfg"].__setitem__("max_new_tokens", 64)), ["--go_max", "9e9"], None, ("STOP", ["I10"])),
    ("N30c A2 tag changed", lambda d: rj(d, lambda j: j["cfg"].__setitem__("tag", "qwen25-3b-base-fs-x")), ["--go_max", "9e9"], None, ("STOP", ["I10"])),
    ("N30c A3 peft 0.21.3", lambda d: rj(d, lambda j: j["sessions"][-1]["versions"].__setitem__("peft", "0.21.3")), ["--go_max", "9e9"], None, ("STOP", ["I10"])),
    ("N30d A6 truncated smoke-S.out", None, ["--go_max", "9e9"], smoke_trunc, ("STOP", ["I11"])),
    ("N30d smoke-S.out content-equal but one byte added to line 1 (sha only)", None, ["--go_max", "9e9"], smoke_sha_only, ("STOP", ["I11"])),
    ("N30e A5 one progress peak decreases", lambda d: outmap(d, lambda b, p: p - 5e6 if b == 200 else p), ["--go_max", "9e9"], None, ("STOP", ["I12"])),
    ("N30e pre-abort peak above the limit", lambda d: outmap(d, lambda b, p: 7000000001 if b == 363 else p), ["--go_max", "9e9"], None, ("STOP", ["I12"])),
    ("C1 +2e8 step at a padded batch L>=1000", lambda d: outmap(d, lambda b, p: p + 2e8 if padded_late <= b < 356 else p), ["--go_max", "9e9"], None, ("STOP", ["C1"])),
    ("C2 zero-padding records off the L^2 fit (+3e8 from batch 293)", lambda d: outmap(d, lambda b, p: p + 3e8 if 293 <= b < 356 else p), ["--go_max", "9e9"], None, ("STOP", ["C2"])),
    ("I1 eval.lock present", lambda d: open(os.path.join(d, "out-S", "eval.lock"), "w").write("9448"), ["--go_max", "9e9"], None, ("STOP", ["I1"])),
    ("I4 ABORT pid differs", lambda d: (lambda p: json.dump(dict(json.load(open(p)), pid=1), open(p + ".t", "w")) or os.replace(p + ".t", p))(os.path.join(d, "out-S", "ABORT-1.json")), ["--go_max", "9e9"], None, ("STOP", ["I4"])),
    ("I5 torn predictions tail", lambda d: open(os.path.join(d, "out-S", f"predictions-{TAG}.jsonl"), "a").write('{"id": "x'), ["--go_max", "9e9"], None, ("STOP", ["I5"])),
    ("I6 last .out line not the ABORT line", lambda d: open(os.path.join(d, "eval-S.out"), "a").write("\nextra"), ["--go_max", "9e9"], None, ("STOP", ["I6"])),
    ("I7 a progress line missing", lambda d: (lambda p: open(p, "w").write("\n".join(l for l in rd(p).split("\n") if not l.startswith('{"batch": 100,'))))(os.path.join(d, "eval-S.out")), ["--go_max", "9e9"], None, ("STOP", ["I7"])),
    ("N31 run json not JSON", lambda d: open(os.path.join(d, "out-S", f"run-{TAG}.json"), "w").write("{"), ["--go_max", "9e9"], None, ("STOP", ["internal"])),
    ("N31 eval-S.out missing", lambda d: os.remove(os.path.join(d, "eval-S.out")), ["--go_max", "9e9"], None, ("STOP", ["internal"])),
    ("N31 smoke-S.out missing", None, ["--go_max", "9e9"], lambda w: os.path.join(w, "nope.out"), ("STOP", ["internal"])),
]
def run_case(work, i, case, tool):
    name, mut, extra, so, (ev, ids) = case
    d = os.path.join(work, f"c{i}"); shutil.copytree(SRC, d)
    if mut: mut(d)
    smoke = so(work) if so else SMOKE_OUT
    p = subprocess.run([sys.executable, "-B", tool, "--stage", V5, "--dir", d, "--smoke_out", smoke, "--smoke_run", SMOKE_RUN] + extra,
                       capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=120)
    last = (p.stdout.strip().splitlines() or [""])[-1]
    if ev == "GO": ok = p.returncode == 0 and last.startswith("E5S1 GO")
    elif ids == ["internal"]: ok = p.returncode == 1 and last.startswith("E5S1 STOP: internal error")
    else: ok = p.returncode == 1 and last.startswith("E5S1 STOP: ") and not last.startswith("E5S1 STOP: internal") and all(f"{x}," in last.split(" failed;")[0] + "," for x in ids)
    # a "real verdict line" for mutant kills: a GO line or a STOP naming checks; the internal-error STOP counts only on the N31 cases built for it
    real = last.startswith("E5S1 GO") or (last.startswith("E5S1 STOP: ") and (not last.startswith("E5S1 STOP: internal") or ids == ["internal"]))
    shutil.rmtree(d)
    return {"case": name, "expect": ev + (" " + "/".join(ids) if ids else ""), "rc": p.returncode, "last": last[:220], "pass": ok, "real_verdict_line": real}
def run_suite(tool):
    work = tempfile.mkdtemp(prefix="e5s1-07-", dir="/tmp")
    try: return [run_case(work, i, c, tool) for i, c in enumerate(CASES)]
    finally: shutil.rmtree(work, ignore_errors=True)
if __name__ == "__main__":
    res = run_suite(TOOL)
    for r in res: print(json.dumps(r))
    n = sum(r["pass"] for r in res); print(f"SUITE {n}/{len(res)}"); sys.exit(0 if n == len(res) else 1)
