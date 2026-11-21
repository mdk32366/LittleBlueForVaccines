# @0.6: replays the out-S abort-3 + resume path through the REAL eval.py GPU branch on the box CPU shim (tests/shim_eval.py of the
# v0.5 stage, unmodified), with the order's own E5-pin-resume argument list (read from ORDER §g) and the real 3,569 rows / fewshot.json.
# Mapping only: Windows work dir -> temp dir, base model -> tests/fixtures/model (pinned real tokenizer), backslash -> slash.
# Appended to every launch (shim only, the same on every session so the run identity is unchanged): --expect_versions <shim torch/peft>
# (the shim's libraries are not the laptop's) and --max_new_tokens 16 (CPU speed).
# Shim env: transformers reported as 5.22.2 (set P needs --pin_transformers 5.22.2), free 7385120768 (E0b PREFLIGHT), peak values below.
# Session 1 reproduces Emma's reported abort: peak 7001188352 reported from the 365th generate on -> exit 3 after row 2920.
# usage: python resume_replay.py <ORDER.md> <v0.5 stage (read only)> <shim python>
import hashlib, json, os, re, shutil, subprocess, sys, tempfile
ORDER, C, SPY = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, C); from evalcore import plan_batches
txt = open(ORDER).read(); g = txt[txt.index("## g. Where it runs"):txt.index("## h. Runtime")]
W = r"C:\Users\mdk32\lb-eval-bluebird-v1.0-r03"; MODEL = r"C:\Users\mdk32\models\Qwen2.5-3B-Instruct"
def block(name):
    m = re.search(r"^\*\*%s\*\*[^\n]*\n```powershell\n(.*?)```" % re.escape(name), g, re.S | re.M); assert m, name; return m.group(1)
def items(name):
    al = re.search(r"-ArgumentList (.*?) -WorkingDirectory (\S+)", block(name)); assert al.group(2) == W; return re.findall(r"'([^']*)'", al.group(1))
VERS = json.dumps({"peft": "0.21.3", "torch": "2.15.0+cpu"})
R = items("E5-pin-resume"); P = items("E5-pin")
res = [{"check": "E5-pin-resume argument list == E5-pin argument list (identical line)", "ok": R == P},
       {"check": "E5-pin-resume block text == E5-pin block text", "ok": block("E5-pin-resume") == block("E5-pin")}]
rows = [json.loads(l) for l in open(os.path.join(C, "eval_rows.jsonl"))]
B = plan_batches(rows, "fewshot", 8); bidx = {r["id"]: k for k, b in enumerate(B) for r in b}
def workdir():
    w = tempfile.mkdtemp(prefix="resume06-")
    for f in ("eval.py", "evalcore.py", "eval_rows.jsonl", "fewshot.json", "RUN-INPUTS.SHA256"): shutil.copy2(os.path.join(C, f), w)
    return w
LAST = {}
def run(w, argv, env, label, expect):
    a = [x.replace(W, w).replace(MODEL, os.path.join(C, "tests", "fixtures", "model")).replace("\\", "/") for x in argv]
    e = dict(os.environ, SHIM_TF_VERSION="5.22.2", SHIM_FREE="7385120768", PYTHONDONTWRITEBYTECODE="1", **env)
    r = subprocess.run([SPY, "-B", os.path.join(C, "tests", "shim_eval.py"), os.path.join(w, a[0])] + a[1:] + ["--expect_versions", VERS, "--max_new_tokens", "16"], cwd=w, env=e, capture_output=True, text=True)
    out = r.stdout.strip().splitlines()
    LAST.update(stdout=r.stdout, stderr=r.stderr)
    rec = {"step": label, "rc": r.returncode, "expect": expect, "ok": r.returncode == expect, "last_out": out[-1] if out else None,
           "argv_from_order": argv}
    if r.returncode not in (0, 3, 7): rec["stderr_tail"] = r.stderr.strip().splitlines()[-5:]
    res.append(rec); return rec
def state(w):
    od = os.path.join(w, "out-S"); pred = os.path.join(od, "predictions-qwen25-3b-base-fs.jsonl"); rj = os.path.join(od, "run-qwen25-3b-base-fs.json")
    L = [json.loads(l) for l in open(pred)] if os.path.exists(pred) else []
    done = sorted({bidx[o["id"]] for o in L}); full = [k for k in done if all(any(o["id"] == r["id"] for o in L) for r in B[k])] if len(L) < 50 else None
    J = json.load(open(rj)) if os.path.exists(rj) else {}
    return {"files": sorted(os.listdir(od)), "pred_lines": len(L), "batches_present": [done[0], done[-1]] if done else [], "n_batches_present": len(done),
            "status": J.get("status"), "sessions": [{k: s.get(k) for k in ("exit", "abort_file", "batches_done_at_start", "repairs", "transformers_check", "transformers_pin")} for s in J.get("sessions", [])],
            "content_sha256": J.get("content_sha256"), "pred_sha256": hashlib.sha256(open(pred, "rb").read()).hexdigest() if L else None}
def snap(w): return {f: hashlib.sha256(open(os.path.join(w, "out-S", f), "rb").read()).hexdigest() for f in sorted(os.listdir(os.path.join(w, "out-S")))}
# --- 1. session 1 = the reported E5-pin abort (exit 3 after row 2920)
w = workdir()
r1 = run(w, P, {"SHIM_PEAK": "4030207488", "SHIM_PEAK_AT": "365", "SHIM_PEAK_HI": "7001188352"}, "session 1: E5-pin, peak 7001188352 from generate 365 on", 3)
s1 = state(w); r1["state"] = s1
r1["ok"] = r1["ok"] and r1["last_out"] == "ABORT 3 peak_alloc 7001188352 > 7000000000.0 after row 2920" and s1["pred_lines"] == 2920 and s1["batches_present"] == [0, 364] \
    and s1["n_batches_present"] == 365 and s1["status"] == "aborted" and s1["files"] == ["ABORT-1.json", "predictions-qwen25-3b-base-fs.jsonl", "run-qwen25-3b-base-fs.json"]
pred1 = open(os.path.join(w, "out-S", "predictions-qwen25-3b-base-fs.jsonl"), "rb").read()
KEEP = os.environ.get("RESUME06_KEEP_S1")             # optional: keep the stopped session (stdout + out-S) for check_replay.py
if KEEP:
    os.makedirs(os.path.join(KEEP, "out-S")); [shutil.copy2(os.path.join(w, "out-S", f), os.path.join(KEEP, "out-S", f)) for f in os.listdir(os.path.join(w, "out-S"))]
    open(os.path.join(KEEP, "session1.stdout"), "w").write(LAST["stdout"]); open(os.path.join(KEEP, "session1.stderr"), "w").write(LAST["stderr"])
base = tempfile.mkdtemp(prefix="resume06-s1-"); shutil.rmtree(base); shutil.copytree(w, base)
# --- 2. refused variants against the aborted dir (nothing written)
for label, argv in (("option (b): E5-pin + --batch 4 against out-S", P + ["--batch", "4"]),
                    ("option (b): E5-pin + --batch 1 against out-S", P + ["--batch", "1"])):
    w2 = tempfile.mkdtemp(prefix="resume06-b-"); shutil.rmtree(w2); shutil.copytree(base, w2); before = snap(w2)
    rec = run(w2, argv, {"SHIM_PEAK": "1000"}, label, 7); rec["nothing_written"] = snap(w2) == before; rec["ok"] = rec["ok"] and rec["nothing_written"] and "batch" in (rec["last_out"] or "")
# --- 3. option (a): --peak_limit is not part of the run identity (not refused); shown, not proposed
w3 = tempfile.mkdtemp(prefix="resume06-a-"); shutil.rmtree(w3); shutil.copytree(base, w3)
rec = run(w3, P + ["--peak_limit", "7300000000"], {"SHIM_PEAK": "4700000000"}, "option (a): E5-pin + --peak_limit 7300000000 (identity check only)", 0)
# --- 4. the recommended resume: identical line, fresh session
r4 = run(w, R, {"SHIM_PEAK": "4700000000"}, "E5-pin-resume (identical line), fresh session, peak 4.7e9", 0)
s4 = state(w); r4["state"] = s4
pred4 = open(os.path.join(w, "out-S", "predictions-qwen25-3b-base-fs.jsonl"), "rb").read()
r4["done_rows_kept_byte_identical_prefix"] = pred4[:len(pred1)] == pred1
r4["ok"] = r4["ok"] and r4["last_out"].startswith("EVAL_DONE qwen25-3b-base-fs 3569 complete ") and s4["status"] == "complete" and s4["pred_lines"] == 3569 \
    and len(s4["sessions"]) == 2 and s4["sessions"][0]["exit"] == 3 and s4["sessions"][1]["exit"] == 0 and s4["sessions"][1]["batches_done_at_start"] == 365 \
    and s4["sessions"][1]["repairs"] == [] and r4["done_rows_kept_byte_identical_prefix"] and s4["files"] == ["ABORT-1.json", "EVAL.SHA256", "predictions-qwen25-3b-base-fs.jsonl", "run-qwen25-3b-base-fs.json"]
ev = subprocess.run(["sha256sum", "-c", "EVAL.SHA256"], cwd=os.path.join(w, "out-S"), capture_output=True, text=True)
res.append({"step": "resumed out-S: sha256sum -c EVAL.SHA256", "ok": ev.returncode == 0, "rc": ev.returncode})
# --- 4b. full scoring accepts the two-session S (ABORT-1.json in out-S) next to a T run: E4-pin argv on the shim, box scoring line
shutil.copytree(os.path.join(C, "tests", "fixtures", "adapter"), os.path.join(w, "adapter"))
rt = run(w, items("E4-pin"), {"SHIM_PEAK": "4400000000"}, "T for scoring: E4-pin argv (fixture adapter)", 0)
sc = re.search(r"\*\*Box scoring \(no card\):\*\*\n```bash\n(.*?)\n```", g, re.S).group(1)
fx = hashlib.sha256(open(os.path.join(C, "tests", "fixtures", "adapter", "ADAPTER.SHA256"), "rb").read()).hexdigest()
so = tempfile.mkdtemp(prefix="resume06-score-")
argv = sc.split(" && ", 1)[1].split()[2:]          # after 'PYTHONDONTWRITEBYTECODE=1 <python>'
argv = [x.replace("35589c33dcc605024b44f6cadecae002998ffff4ecb75a7c52d5432f2988251b", fx).replace("runs/r03/out-T/", w + "/out-T/").replace("runs/r03/out-S/", w + "/out-S/").replace("runs/r03/score", so + "/score") for x in argv]
r = subprocess.run([SPY, "-B"] + argv, cwd=C, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
res.append({"step": "box scoring line (adapter sha -> fixture's) on T + resumed two-session S", "rc": r.returncode, "ok": r.returncode == 0,
            "tail": (r.stdout + r.stderr).strip().splitlines()[-3:], "pycache_in_stage": os.path.isdir(os.path.join(C, "__pycache__"))})
shutil.rmtree(so, ignore_errors=True)
# --- 5. stop rule: resume aborts 3 again on its first batch -> batch 365 written and kept, ABORT-2; the next identical resume completes
w5 = tempfile.mkdtemp(prefix="resume06-again-"); shutil.rmtree(w5); shutil.copytree(base, w5)
r5 = run(w5, R, {"SHIM_PEAK": "4030207488", "SHIM_PEAK_AT": "1", "SHIM_PEAK_HI": "7100000000"}, "E5-pin-resume aborts 3 again at its first batch", 3)
s5 = state(w5); r5["state"] = s5
r5["ok"] = r5["ok"] and r5["last_out"] == "ABORT 3 peak_alloc 7100000000 > 7000000000.0 after row 8" and s5["pred_lines"] == 2928 and s5["batches_present"] == [0, 365] \
    and "ABORT-2.json" in s5["files"] and s5["sessions"][-1]["abort_file"] == "ABORT-2.json"
r6 = run(w5, R, {"SHIM_PEAK": "4700000000"}, "after a second abort 3: identical line again (only if Trinity re-plans so; shown for safety)", 0)
s6 = state(w5); r6["state"] = s6; r6["ok"] = r6["ok"] and s6["status"] == "complete" and s6["pred_lines"] == 3569
# --- 6. comparability: one uninterrupted session gives the same content hash as abort + resume
w7 = workdir(); r7 = run(w7, P, {"SHIM_PEAK": "4700000000"}, "uninterrupted single-session E5-pin (reference)", 0); s7 = state(w7)
res.append({"check": "content_sha256: abort+resume == uninterrupted == abort+abort+resume", "ok": s4["content_sha256"] == s7["content_sha256"] == s6["content_sha256"] and s7["content_sha256"] is not None,
            "values": [s4["content_sha256"], s7["content_sha256"], s6["content_sha256"]]})
for d in (w, base, w3, w5, w7): shutil.rmtree(d, ignore_errors=True)
for x in res: print(json.dumps(x))
print(json.dumps({"summary": f"{sum(bool(x['ok']) for x in res)}/{len(res)} ok"}))
