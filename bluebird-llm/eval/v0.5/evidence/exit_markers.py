# @0.5 (N20): checks the order's last-.out-line rule against real exits of eval.py on the box (stub path and the CPU shim of the GPU branch,
# via the suite's own helpers, temp dirs outside every stage). stdout = what -RedirectStandardOutput writes to .out (shim-only 'SHIM' lines
# dropped); stderr = .err. Also a static check: every sys.exit in eval.py sits in abort()/refuse() right after its print, or is main()'s return.
import ast, json, os, re, shutil, subprocess, sys, tempfile
C = sys.argv[1]; sys.argv = [sys.argv[0]]; sys.path.insert(0, C); sys.path.insert(0, os.path.join(C, "tests")); os.chdir(C)
import test_eval as T
def rule(out, err, lock_alive=False):
    lines = [l for l in out.splitlines() if l.strip() and not l.startswith("SHIM")]
    if not lines:
        e = [l for l in err.splitlines() if l.strip()]
        return 2 if e and e[-1].startswith("eval.py: error:") else ("running" if lock_alive else "no exit code")
    last = lines[-1]
    if re.match(r"^EVAL_DONE \S+ \d+ complete [0-9a-f]{64}$", last): return 0
    m = re.match(r"^ABORT (\d+) ", last)
    if m: return int(m.group(1))
    if last.startswith("REFUSED (exit 7, nothing written):"): return 7
    return "running" if lock_alive else "no exit code"
res = []
def rec(label, rc, out, err, expect_rule=None):
    got = rule(out, err); want = rc if expect_rule is None else expect_rule
    lines = [l for l in out.splitlines() if l.strip() and not l.startswith("SHIM")]
    res.append({"case": label, "rc": rc, "rule": got, "ok": got == want, "last_out": lines[-1][:160] if lines else "", "last_err": (err.strip().splitlines() or [""])[-1][:160]})
def stub(w, out, extra=(), pin=None):
    cmd = [sys.executable, "-B", os.path.join(w, "eval.py"), "--rows", os.path.join(w, "eval_rows.jsonl"), "--expect_manifest_sha", pin or T.sha(os.path.join(w, "RUN-INPUTS.SHA256")),
           "--out_dir", os.path.join(w, out), "--tag", "t", "--backend", "stub:gold"] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=w); return r.returncode, r.stdout, r.stderr
w = T.stage_sub()
rc, o, e = stub(w, "a", ["--limit", "16"]); rec("stub run complete", rc, o, e)
rc, o, e = stub(w, "a", ["--limit", "16"]); rec("same launch into the completed dir", rc, o, e)
rc, o, e = stub(w, "b", ["--replay_b1", "8"]); rec("--replay_b1 without --limit (fresh dir)", rc, o, e)
rc, o, e = stub(w, "c", pin="0" * 64); rec("wrong RUN PIN (fresh dir)", rc, o, e)
rc, o, e = stub(w, "d", ["--min_free", "<MIN_FREE_BYTES>"]); rec("unfilled '<MIN_FREE_BYTES>'", rc, o, e)
for label, env, extra in (("shim ok", {}, []), ("shim peak > limit", {"SHIM_PEAK_AT": "1"}, []), ("shim OOM at load", {"SHIM_OOM_LOAD": "1"}, []),
                          ("shim OOM in generate", {"SHIM_OOM_AT": "2"}, []), ("shim no CUDA", {"SHIM_CUDA": "0"}, []), ("shim GPU free < floor", {"SHIM_FREE": "1e9"}, []),
                          ("shim RuntimeError", {"SHIM_RAISE_AT": "2"}, []), ("shim KeyboardInterrupt", {"SHIM_INTERRUPT_AT": "1"}, []),
                          ("shim transformers 5.22.2 unpinned", {"SHIM_TF_VERSION": "5.22.2"}, []), ("shim merged config not greedy", {"SHIM_TAMPER_MERGED": "1"}, [])):
    r = T.shim(w, "s-" + re.sub(r"\W", "", label), env=env, extra=extra); rec(label, r["rc"], r["out"], r["err"])
r = T.shim(w, "kill", env={"SHIM_KILL_AT": "2"}); rec("shim hard kill (os._exit 137): no marker", r["rc"], r["out"], r["err"], expect_rule="no exit code")
# against the stopped (killed) run dir: exit 8 and exit 6 print 'ABORT n ... (NOT recorded in out_dir ...)'
r = T.shim(w, "kill", extra=["--mode", "fewshot"]); rec("exit 8 against a run dir (NOT recorded)", r["rc"], r["out"], r["err"])
r = T.shim(w, "kill", env={}, extra=["--expect_manifest_sha", "0" * 64]) if False else None
cmd = [T.SHIM_PY, os.path.join(T.H, "tests", "shim_eval.py"), os.path.join(w, "eval.py"), "--rows", os.path.join(w, "eval_rows.jsonl"), "--expect_manifest_sha", "0" * 64,
       "--model", os.path.join(T.FX, "model"), "--out_dir", os.path.join(w, "kill"), "--tag", "t", "--max_new_tokens", "16", "--adapter", T.AD, "--expect_versions", T.SHIM_VERS]
p = subprocess.run(cmd, capture_output=True, text=True, cwd=w); rec("exit 6 against a run dir (NOT recorded)", p.returncode, p.stdout, p.stderr)
r = T.shim(w, "kill"); rec("resume of the killed run", r["rc"], r["out"], r["err"])
# static: sys.exit sites
src = open(os.path.join(C, "eval.py")).read(); tree = ast.parse(src); sites = []
for n in ast.walk(tree):
    if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "exit" and getattr(getattr(n.func, "value", None), "id", "") == "sys": sites.append(n.lineno)
L = src.splitlines(); sites = sorted(sites)
static = {"sys_exit_lines": sites, "lines": [L[i - 1].strip()[:140] for i in sites]}
res.append({"case": "static: sys.exit only in abort() L118/L127, refuse() L130 (each after its print) and __main__ sys.exit(main()) L400",
            "ok": sites == [118, 127, 130, 400] and "print(\"ABORT\"" in L[117] and "print(\"ABORT\"" in L[126] and "print(\"REFUSED" in L[129], **static})
for x in res: print(json.dumps(x))
print(json.dumps({"summary": f"{sum(x['ok'] for x in res)}/{len(res)} ok"}))
