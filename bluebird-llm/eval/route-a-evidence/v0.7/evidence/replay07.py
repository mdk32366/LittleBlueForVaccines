# @0.7: route A and route B lines of ORDER@0.7 §g through the REAL eval.py GPU branch on the box CPU shim (v0.5 tests/shim_eval.py, unmodified),
# with the order's own argument lists and the real 3,569 rows. Same mapping and shim-only appendix as @0.6's resume_replay.py
# (--expect_versions <shim libs> --max_new_tokens 16; SHIM_TF_VERSION 5.22.2; SHIM_FREE 7385120768). Box scoring lines run with the fixture adapter sha.
# usage: python3 -B replay07.py <ORDER@0.7.md> <v0.5 stage> <shim python>
import hashlib, json, os, re, shutil, subprocess, sys, tempfile
sys.dont_write_bytecode = True
ORDER, C, SPY = sys.argv[1:4]
txt = open(ORDER).read(); g = txt[txt.index("## g. Where it runs"):txt.index("## h. Runtime")]
W = r"C:\Users\mdk32\lb-eval-bluebird-v1.0-r03"; MODEL = r"C:\Users\mdk32\models\Qwen2.5-3B-Instruct"
def block(name):
    m = re.search(r"^\*\*%s\*\*[^\n]*\n```powershell\n(.*?)```" % re.escape(name), g, re.S | re.M); assert m, name; return m.group(1)
def items(name):
    al = re.search(r"-ArgumentList (.*?) -WorkingDirectory (\S+)", block(name)); assert al.group(2) == W; return re.findall(r"'([^']*)'", al.group(1))
def redirects(name): return re.findall(r"-Redirect\S+ (\S+)", block(name))
VERS = json.dumps({"peft": "0.21.3", "torch": "2.15.0+cpu"}); res = []
def workdir(p):
    w = tempfile.mkdtemp(prefix=p)
    for f in ("eval.py", "evalcore.py", "eval_rows.jsonl", "fewshot.json", "RUN-INPUTS.SHA256"): shutil.copy2(os.path.join(C, f), w)
    return w
def run(w, argv, env, label, expect, check=None):
    a = [x.replace(W, w).replace(MODEL, os.path.join(C, "tests", "fixtures", "model")).replace("\\", "/") for x in argv]
    e = dict(os.environ, SHIM_TF_VERSION="5.22.2", SHIM_FREE="7385120768", PYTHONDONTWRITEBYTECODE="1", **env)
    r = subprocess.run([SPY, "-B", os.path.join(C, "tests", "shim_eval.py"), os.path.join(w, a[0])] + a[1:] + ["--expect_versions", VERS, "--max_new_tokens", "16"], cwd=w, env=e, capture_output=True, text=True)
    out = r.stdout.strip().splitlines(); rec = {"step": label, "rc": r.returncode, "expect": expect, "last_out": out[-1] if out else None}
    rec["ok"] = r.returncode == expect and (check(rec["last_out"] or "", w) if check else True)
    if r.returncode not in (0, 3, 7): rec["stderr_tail"] = r.stderr.strip().splitlines()[-5:]
    res.append(rec); return rec
def rj(w, od): return json.load(open(os.path.join(w, od, "run-qwen25-3b-base-fs.json")))
def nlines(w, od): return sum(1 for _ in open(os.path.join(w, od, "predictions-qwen25-3b-base-fs.jsonl")))
A, AF, BL, P = items("E5-b4-pin"), items("E5-b4-pin-floor"), items("E5-pin-limit"), items("E5-pin")
res.append({"check": "E5-b4-pin = E5-pin with out_dir out-S-b4 + '--batch','4'; redirects eval-S4.out/.err", "ok": A == [x if x != "out-S" else "out-S-b4" for x in P] + ["--batch", "4"]
            and redirects("E5-b4-pin") == [W + r"\eval-S4.out", W + r"\eval-S4.err"]})
res.append({"check": "E5-b4-pin-floor = E5-b4-pin + '--min_free','<MIN_FREE_BYTES>'", "ok": AF == A + ["--min_free", "<MIN_FREE_BYTES>"]})
res.append({"check": "E5-pin-limit = E5-pin + '--peak_limit','8500000000'; redirects eval-S.out/.err", "ok": BL == P + ["--peak_limit", "8500000000"] and redirects("E5-pin-limit") == redirects("E5-pin")})
# ---- route A: T (E4-pin) + fresh S at batch 4, box scoring route A
w = workdir("r07A-"); shutil.copytree(os.path.join(C, "tests", "fixtures", "adapter"), os.path.join(w, "adapter"))
run(w, items("E4-pin"), {"SHIM_PEAK": "4400000000"}, "T: E4-pin argv (fixture adapter)", 0)
run(w, A, {"SHIM_PEAK": "5300000000"}, "route A: E5-b4-pin, fresh out-S-b4, peak 5.3e9", 0,
    lambda l, w: l.startswith("EVAL_DONE qwen25-3b-base-fs 3569 complete ") and rj(w, "out-S-b4")["cfg"]["batch"] == 4 and rj(w, "out-S-b4")["planned_batches"] == 893 and nlines(w, "out-S-b4") == 3569)
ev = subprocess.run(["sha256sum", "-c", "EVAL.SHA256"], cwd=os.path.join(w, "out-S-b4"), capture_output=True, text=True); res.append({"step": "out-S-b4: sha256sum -c EVAL.SHA256", "ok": ev.returncode == 0})
fx = hashlib.sha256(open(os.path.join(C, "tests", "fixtures", "adapter", "ADAPTER.SHA256"), "rb").read()).hexdigest()
sc = re.search(r"\*\*Box scoring, route A \(no card\):\*\*\n```bash\n(.*?)\n```", g, re.S).group(1); so = tempfile.mkdtemp(prefix="r07-score-")
argv = [x.replace("35589c33dcc605024b44f6cadecae002998ffff4ecb75a7c52d5432f2988251b", fx).replace("runs/r03/out-T/", w + "/out-T/").replace("runs/r03/out-S-b4/", w + "/out-S-b4/").replace("runs/r03/score", so + "/score") for x in sc.split(" && ", 1)[1].split()[2:]]
r = subprocess.run([SPY, "-B"] + argv, cwd=C, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
res.append({"step": "box scoring route A line (adapter sha -> fixture's) on T (batch 8) + S (batch 4)", "rc": r.returncode, "ok": r.returncode == 0, "tail": (r.stdout + r.stderr).strip().splitlines()[-2:]})
shutil.rmtree(so, ignore_errors=True); shutil.rmtree(w, ignore_errors=True)
# ---- route A stop + resume: exit 3 at generate 500, then the same E5-b4-pin line resumes; floor line (filled) also resumes
w = workdir("r07A2-")
run(w, A, {"SHIM_PEAK": "4000000000", "SHIM_PEAK_AT": "500", "SHIM_PEAK_HI": "7100000000"}, "route A: E5-b4-pin aborts 3 at batch 499", 3, lambda l, w: l == "ABORT 3 peak_alloc 7100000000 > 7000000000.0 after row 2000" and nlines(w, "out-S-b4") == 2000)
w2 = tempfile.mkdtemp(prefix="r07A3-"); shutil.rmtree(w2); shutil.copytree(w, w2)
run(w, A, {"SHIM_PEAK": "5000000000"}, "route A: same E5-b4-pin line again resumes from batch 500", 0, lambda l, w: l.startswith("EVAL_DONE qwen25-3b-base-fs 3569 complete ") and rj(w, "out-S-b4")["sessions"][-1]["batches_done_at_start"] == 500)
run(w2, [x.replace("<MIN_FREE_BYTES>", "7000000000") for x in AF], {"SHIM_PEAK": "5000000000"}, "route A: E5-b4-pin-floor (filled 7000000000) resumes the same dir", 0, lambda l, w: l.startswith("EVAL_DONE qwen25-3b-base-fs 3569 complete "))
run(w2, [x.replace("<MIN_FREE_BYTES>", "7000000000") for x in AF], {"SHIM_PEAK": "5000000000"}, "route A: relaunch against the completed out-S-b4 is refused", 7)
for d in (w, w2): shutil.rmtree(d, ignore_errors=True)
# ---- route B: the reported abort (exit 3 after row 2920), then E5-pin-limit
w = workdir("r07B-")
run(w, P, {"SHIM_PEAK": "4030207488", "SHIM_PEAK_AT": "365", "SHIM_PEAK_HI": "7001188352"}, "session 1: E5-pin, the reported abort", 3, lambda l, w: l == "ABORT 3 peak_alloc 7001188352 > 7000000000.0 after row 2920")
wb = tempfile.mkdtemp(prefix="r07B2-"); shutil.rmtree(wb); shutil.copytree(w, wb)
pre = open(os.path.join(w, "out-S", "predictions-qwen25-3b-base-fs.jsonl"), "rb").read()
run(w, BL, {"SHIM_PEAK": "8016885034"}, "route B: E5-pin-limit resumes out-S, peak 8016885034 < 8.5e9", 0,
    lambda l, w: l.startswith("EVAL_DONE qwen25-3b-base-fs 3569 complete ") and open(os.path.join(w, "out-S", "predictions-qwen25-3b-base-fs.jsonl"), "rb").read()[:len(pre)] == pre and rj(w, "out-S")["sessions"][-1]["batches_done_at_start"] == 365)
run(wb, BL, {"SHIM_PEAK": "8600000000"}, "route B: E5-pin-limit with a peak above 8.5e9 stops with exit 3 after its first batch", 3, lambda l, w: l == "ABORT 3 peak_alloc 8600000000 > 8500000000.0 after row 8")
for d in (w, wb): shutil.rmtree(d, ignore_errors=True)
res.append({"check": "no __pycache__ in the v0.5 stage", "ok": not os.path.isdir(os.path.join(C, "__pycache__")) and not os.path.isdir(os.path.join(C, "tests", "__pycache__"))})
for x in res: print(json.dumps(x))
print(json.dumps({"summary": f"{sum(bool(x['ok']) for x in res)}/{len(res)} ok"}))
