# @0.5 (N19, N22): the E0b outcome table, run through the REAL GPU branch of eval.py on the box's CPU shim (tests/shim_eval.py), using the
# order's own E0b / E0b-pin / E0b-pin-floor / E0b-floor and E3a/E3b -pin / -pin-floor argument lists parsed from ORDER §g.
# Work dir = the laptop layout (full eval_rows.jsonl, real RUN-INPUTS.SHA256, so the literal RUN PIN matches); mapping only: Windows paths ->
# temp dir, base model -> tests/fixtures/model (tiny Qwen2 + real tokenizer), adapter -> tests/fixtures/adapter; appended for the CPU box only:
# --expect_versions <shim versions> (the shim's torch/peft are not the laptop's) and, for the smoke runs, --max_new_tokens 16 (speed).
# SHIM_TF_VERSION = reported transformers version, SHIM_FREE = reported free GPU bytes (total 8e9).
# usage: python e0b_variants.py <ORDER.md> <stage copy>
import json, os, re, shutil, subprocess, sys, tempfile
ORDER, C = sys.argv[1], sys.argv[2]; txt = open(ORDER).read(); g = txt[txt.index("## g. Where it runs"):txt.index("## h. Runtime")]
PY = "/workspace/littleblue-fullrun-review/venv/bin/python"; SHIM = os.path.join(C, "tests", "shim_eval.py")
VERS = json.dumps({"peft": "0.21.3", "torch": "2.15.0+cpu"})
W = r"C:\Users\mdk32\lb-eval-bluebird-v1.0-r03"; MODEL = r"C:\Users\mdk32\models\Qwen2.5-3B-Instruct"
def workdir():
    w = tempfile.mkdtemp(prefix="e0b05-")
    for f in ("eval.py", "evalcore.py", "eval_rows.jsonl", "fewshot.json", "RUN-INPUTS.SHA256"): shutil.copy2(os.path.join(C, f), w)
    shutil.copytree(os.path.join(C, "tests", "fixtures", "adapter"), os.path.join(w, "adapter")); return w
def mapv(v, w): return v.replace(W, w).replace(MODEL, os.path.join(C, "tests", "fixtures", "model")).replace("\\", "/")
def block(name): return re.search(r"^\*\*%s\*\*[^\n]*\n```powershell\n(.*?)```" % re.escape(name), g, re.S | re.M).group(1)
def amp(name):
    ln = [l for l in block(name).splitlines() if l.startswith("& ")][0]
    return [x[1:-1] if x.startswith("'") and x.endswith("'") else x for x in ln.split()[2:]]
def sp(name): return re.findall(r"'([^']*)'", re.search(r"-ArgumentList (.*?) -WorkingDirectory", block(name)).group(1))
def run(w, items, env, fill=None, extra=()):
    items = [fill if (x == "<MIN_FREE_BYTES>" and fill) else x for x in items]; argv = [mapv(x, w) for x in items]
    script = os.path.join(w, "eval.py") if argv[0] == "eval.py" else argv[0]
    r = subprocess.run([PY, "-B", SHIM, script] + argv[1:] + ["--expect_versions", VERS] + list(extra), cwd=w, capture_output=True, text=True,
                       env={**os.environ, **env})
    out = [l for l in r.stdout.splitlines() if not l.startswith("SHIM")]   # .out on the laptop has no shim lines
    keep = [l for l in out if l.startswith(("TRANSFORMERS", "GPU_FREE", "PREFLIGHT_DONE", "ABORT", "REFUSED", "EVAL_DONE", "REPAIRED"))]
    return r.returncode, keep, (r.stderr.strip().splitlines() or [""])[-1]
res = []
def step(sid, label, w, name_or_items, env, expect, fill=None, extra=(), d="pre-T"):
    items = amp(name_or_items) if isinstance(name_or_items, str) and name_or_items.startswith("E0b") else (sp(name_or_items) if isinstance(name_or_items, str) else name_or_items)
    before = sorted(os.listdir(os.path.join(w, d))) if os.path.isdir(os.path.join(w, d)) else []
    rc, keep, lerr = run(w, items, env, fill, extra)
    after = sorted(os.listdir(os.path.join(w, d))) if os.path.isdir(os.path.join(w, d)) else []
    res.append({"step": sid, "what": label, "env": env, "rc": rc, "expect": expect, "ok": rc == expect, "lines": keep, "last_err": lerr if rc == 2 else "",
                "new_files": sorted(set(after) - set(before))})
# PF: 5.22.2, 6e9 free (both (b) and (c))
e = {"SHIM_TF_VERSION": "5.22.2", "SHIM_FREE": "6e9"}; w = workdir()
step("PF1", "E0b as written", w, "E0b", e, 13)
step("PF2", "E0b-pin (wrong variant for this outcome: no floor)", w, "E0b-pin", e, 10)
step("PF3", "E0b-pin-floor, '<MIN_FREE_BYTES>' unfilled", w, "E0b-pin-floor", e, 2)
step("PF4", "E0b-pin-floor, floor 6500000000 > measured 6e9", w, "E0b-pin-floor", e, 10, fill="6500000000")
step("PF5", "E0b-pin-floor, floor 5000000000", w, "E0b-pin-floor", e, 0, fill="5000000000")
# P: 5.22.2, 7.5e9 free ((b) only)
e = {"SHIM_TF_VERSION": "5.22.2", "SHIM_FREE": "7.5e9"}; w = workdir()
step("P1", "E0b as written", w, "E0b", e, 13)
step("P2", "E0b-pin", w, "E0b-pin", e, 0)
# F: 5.23.0, 6e9 ((c) only)
e = {"SHIM_TF_VERSION": "5.23.0", "SHIM_FREE": "6e9"}; w = workdir()
step("F1", "E0b as written", w, "E0b", e, 10)
step("F2", "E0b-floor, floor 5000000000", w, "E0b-floor", e, 0, fill="5000000000")
# U: 5.23.0, 7.5e9
e = {"SHIM_TF_VERSION": "5.23.0", "SHIM_FREE": "7.5e9"}; w = workdir()
step("U1", "E0b as written", w, "E0b", e, 0)
# PF set, smoke, GPU branch: E3a-pin without the floor fails at the start check; the PF lines run
e = {"SHIM_TF_VERSION": "5.22.2", "SHIM_FREE": "6e9"}; w = workdir()
step("S1", "E3a-pin at 6e9 free (set P where PF was due)", w, "E3a-pin", e, 10, extra=("--max_new_tokens", "16"), d="out-smoke-T")
w = workdir()
step("S2", "E3a-pin-floor, floor 5000000000", w, "E3a-pin-floor", e, 0, fill="5000000000", extra=("--max_new_tokens", "16"), d="out-smoke-T")
step("S3", "E3b-pin-floor, floor 5000000000", w, "E3b-pin-floor", e, 0, fill="5000000000", extra=("--max_new_tokens", "16"), d="out-smoke-S")
# R-floor: a run killed mid-way, resumed with a DIFFERENT --min_free: eval.py does not refuse (floor not part of the run identity)
w = workdir()
step("R1", "E3a-pin-floor (5000000000), hard kill after 2 batches", w, "E3a-pin-floor", {**e, "SHIM_KILL_AT": "2"}, 137, fill="5000000000", extra=("--max_new_tokens", "16"), d="out-smoke-T")
step("R2", "resume with E3a-pin-floor but floor 4000000000 (not the identical line)", w, "E3a-pin-floor", e, 0, fill="4000000000", extra=("--max_new_tokens", "16"), d="out-smoke-T")
for x in res: print(json.dumps(x))
print(json.dumps({"summary": f"{sum(x['ok'] for x in res)}/{len(res)} ok"}))
