"""@0.7 mutant run for tools/e5s1_check.py. Each mutant is one textual change to a temp copy of the tool (outside every stage).
A mutant is KILLED only if some suite case fails while the mutant printed a real verdict line (E5S1 GO, or E5S1 STOP naming checks);
failures where the mutant crashed or printed the internal-error STOP do not count. usage: python3 -B tests/e5s1_mutants.py"""
import json, os, sys, tempfile, shutil
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e5s1_suite import run_suite
SRC = open(os.path.join(HERE, "..", "tools", "e5s1_check.py")).read()
M = [
 ("C3 margin 1e9 -> 1e10", 'default=1.0e9)', 'default=1.0e10)'),
 ("C3 compares against smoke batch 7 instead of the same batch", 's <= q + a.early_margin for _, s, q in early', 's <= sp[-1]["peak_alloc"] + a.early_margin for _, s, q in early'),
 ("C3 only first 1 early point", 'EARLY = 6', 'EARLY = 1'),
 ("C3 always ok", 'all(s <= q + a.early_margin for _, s, q in early)', 'True'),
 ("I8 single-session dropped", 'len(S) == 1 and d0 == 0', 'd0 == 0'),
 ("I9 greedy reduced to do_sample/num_beams", 'last.get("merged_generation_config") == GREEDY and', '(lambda g: g.get("do_sample") is False and g.get("num_beams") == 1)(last.get("merged_generation_config")) and'),
 ("I9 session greedy not compared", 'last.get("merged_generation_config") == GREEDY and ss.get', 'True and ss.get'),
 ("I10 cfg diff ignored", 'diff == ["limit"] and', 'True and'),
 ("I10 versions not compared", 'and last.get("versions") == VERSIONS and', 'and'),
 ("I11 smoke sha pin dropped", 'file_sha256(a.smoke_out) == SMOKE_OUT_SHA and', ''),
 ("I11 progress-count check dropped", '[p["batch"] for p in sp] == list(range(8)) and', ''),
 ("I11 EVAL_DONE dropped", 'and bool(sl) and sl[-1].startswith("EVAL_DONE qwen25-3b-base-fs 64 complete ")', ''),
 ("I12 monotone dropped", 'all(peaks[i] >= peaks[i - 1] for i in range(1, len(peaks))) and', ''),
 ("I12 <= limit dropped", 'all(p <= LIMIT for p in peaks[:-1]) and', ''),
 ("C1 threshold 1e8 -> 1e9", 'default=1.0e8)', 'default=1.0e9)'),
 ("C1 always ok", 'all(p == 0 for k, s, l, p in big if l >= 1000)', 'True'),
 ("C2 tolerance 1% -> 20%", 'default=0.01)', 'default=0.20)'),
 ("C2 fit on L instead of L^2", 'X = [l * l for l, _ in rec]', 'X = [l for l, _ in rec]'),
 ("C4 zero-padding batches use the padded bound", 'if pad(k) == 0: proj.append', 'if False: proj.append'),
 ("C4 compares with >= flipped (p < go_max)", 'if p > a.go_max]', 'if p < 0]'),
 ("C4 default go_max 6.5e9 -> 8.5e9", 'default=6.5e9)', 'default=8.5e9)'),
 ("I1 eval.lock allowed", 'set(names) - set(aborts) == {', 'set(names) - set(aborts) - {"eval.lock"} == {'),
 ("I4 pid not compared", 'and A.get("pid") == last.get("pid")', ''),
 ("I5 torn tail ignored", 'nb >= 1 and not tail and', 'nb >= 1 and'),
 ("I6 dropped", 'm and lastline == f"ABORT 3 {A.get(\'abort\')}" and int(m.group(2)) == rows_done', 'True'),
 ("I7 dropped", 'ks == list(range(d0, nb - 1))', 'True'),
 ("N31 exception prints GO", 'print(f"E5S1 STOP: internal error', 'print(f"E5S1 GO: internal error'),
 ("N31 exception exit 0", '[:200]}; no relaunch, Trinity re-plans"); sys.exit(1)', '[:200]}; no relaunch, Trinity re-plans"); sys.exit(0)'),
 ("verdict ignores fails (always GO line)", 'if not fails else f"E5S1 STOP', 'if True else f"E5S1 STOP'),
]
res = []; work = tempfile.mkdtemp(prefix="e5s1-mut-", dir="/tmp")
try:
    for name, old, new in M:
        n = SRC.count(old); assert n == 1, (name, n)
        p = os.path.join(work, "m.py"); open(p, "w").write(SRC.replace(old, new))
        r = run_suite(p); real = [x["case"] for x in r if not x["pass"] and x["real_verdict_line"]]; crash = [x["case"] for x in r if not x["pass"] and not x["real_verdict_line"]]
        res.append({"mutant": name, "killed": bool(real), "killed_by": real[:3], "crash_only_failures": crash[:3]}); print(json.dumps(res[-1]), flush=True)
finally: shutil.rmtree(work, ignore_errors=True)
k = sum(r["killed"] for r in res); print(f"MUTANTS killed {k}/{len(res)}"); sys.exit(0 if k == len(res) else 1)
