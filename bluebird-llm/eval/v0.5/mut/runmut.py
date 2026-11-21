# Runs mut/spec.py against copies of the @0.2 stage. usage: runmut.py [ids...]   -> mut/MUTATION-RESULTS.jsonl + .md
# Per mutant: copy stage -> apply (each old string must occur exactly once) -> reissue EVAL-INPUTS.SHA256 -> py_compile ->
# stage A: non-shim suite (LBE_SKIP_SHIM=1). Survivors in eval.py -> stage B: Shim class. build_eval_rows.py -> Build with LBE_REBUILD=1.
# Data mutants: rows rewritten in the copy, then stage A (Build.test_probe_rows_well_formed is the intended guard).
import concurrent.futures as cf, json, os, shutil, subprocess, sys, tempfile, time
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(H, "mut"))
from spec import M, D
PY = os.environ.get("LBE_PY", "/workspace/littleblue-fullrun-review/venv/bin/python")
IGN = shutil.ignore_patterns("mut", "sim", "RESULTS.txt", "__pycache__", "*.log")
def copy():
    d = tempfile.mkdtemp(prefix="lbe-mut-"); w = os.path.join(d, "s"); shutil.copytree(H, w, ignore=IGN); os.makedirs(os.path.join(w, "sim"))
    for f in ("stub_harness.py", "simulate.py"): shutil.copy(os.path.join(H, "sim", f), os.path.join(w, "sim", f))
    return d, w
def run(w, tests, env, timeout=1500):
    t = time.time(); tmp = os.path.join(os.path.dirname(w), "tmp"); os.makedirs(tmp, exist_ok=True)
    env = {**env, "TMPDIR": tmp}                                  # every temp dir the suite makes lives inside this mutant's copy and is removed with it
    try:
        r = subprocess.run([PY, "-W", "ignore", "-m", "unittest", *tests], cwd=w, capture_output=True, text=True, env={**os.environ, **env}, timeout=timeout)
        out = r.stderr; rc = r.returncode                         # @0.2 (review I2): full stderr, so every killing test is named
    except subprocess.TimeoutExpired: out, rc = "TIMEOUT", -1
    failed = [l.split(" ", 1)[1].strip() for l in out.splitlines() if l.startswith(("FAIL: ", "ERROR: "))]
    return {"rc": rc, "failed": failed, "sec": round(time.time() - t), "tail": out[-600:] if rc else ""}
def one(entry, stage_b=False):
    d, w = copy()
    try:
        if len(entry) == 3:                                       # data mutant
            mid, guard, fn = entry; p = os.path.join(w, "eval_rows.jsonl"); R = [json.loads(l) for l in open(p)]; fn(R)
            open(p, "w").write("".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in R)); f = "eval_rows.jsonl"; origin = "K" if mid <= "D06" else "new"
        else:
            mid, origin, f, reps, guard = entry
            if f is None: return {"id": mid, "origin": origin, "guard": guard, "status": "NOT_PORTED"}
            p = os.path.join(w, f); s = open(p).read()
            for old, new in reps:
                n = s.count(old)
                if n != 1: return {"id": mid, "origin": origin, "guard": guard, "status": "SITE_ERROR", "detail": f"{old[:60]!r} occurs {n}x"}
                s = s.replace(old, new)
            open(p, "w").write(s)
            c = subprocess.run([PY, "-m", "py_compile", p], capture_output=True, text=True)
            if c.returncode: return {"id": mid, "origin": origin, "guard": guard, "status": "SYNTAX_ERROR", "detail": c.stderr[-300:]}
        subprocess.run([PY, "mkmanifest.py"], cwd=w, capture_output=True, check=True)
        res = {"id": mid, "origin": origin, "file": f, "guard": guard}
        if f == "build_eval_rows.py":
            res["B"] = run(w, ["tests.test_eval.Build"], {"LBE_REBUILD": "1", "LBE_SKIP_SHIM": "1"})
            res["status"] = "KILLED" if res["B"]["rc"] else "SURVIVED"; return res
        res["A"] = run(w, ["tests.test_eval"], {"LBE_SKIP_SHIM": "1"})
        if res["A"]["rc"] == 0 and f == "eval.py" and stage_b:
            res["B"] = run(w, ["tests.test_eval.Shim"], {"LBE_SHIM_JOBS": os.environ.get("LBE_SHIM_JOBS_B", "4")})
        res["status"] = "KILLED" if res["A"]["rc"] or res.get("B", {}).get("rc") else ("SURVIVED" if f != "eval.py" or stage_b else "SURVIVED_A")
        return res
    finally: shutil.rmtree(d, ignore_errors=True)
if __name__ == "__main__":
    want = set(sys.argv[1:]); ents = [e for e in M + D if not want or e[0] in want]
    out = os.path.join(H, "mut", "MUTATION-RESULTS.jsonl"); prev = {}
    if os.path.exists(out): prev = {r["id"]: r for r in (json.loads(l) for l in open(out))}
    with cf.ThreadPoolExecutor(int(os.environ.get("LBE_MUT_JOBS", "4"))) as ex:
        for r in ex.map(one, ents):
            prev[r["id"]] = r; print(r["id"], r["status"], r.get("A", {}).get("failed", [])[:3], flush=True)
    late = [e for e in ents if prev[e[0]]["status"] == "SURVIVED_A"]          # eval.py survivors of stage A -> Shim stage, one at a time
    for e in late:
        r = one(e, stage_b=True); prev[r["id"]] = r; print(r["id"], r["status"], "(shim)", r.get("B", {}).get("failed", [])[:3], flush=True)
    order = [e[0] for e in M + D]
    open(out, "w").write("".join(json.dumps(prev[i], sort_keys=True) + "\n" for i in order if i in prev))
