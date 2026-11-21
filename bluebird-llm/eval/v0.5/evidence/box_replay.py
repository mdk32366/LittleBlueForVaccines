# @0.5 (N23c, N23e): replays the order's box bash lines (landing mkdir, E3c, box scoring) in a temp copy of the stage, against stub runs made
# by the order's own E3a/E3b/E4/E5 argument lists (stub backend). Mapping: /workspace/littleblue-eval-v0.5 -> temp copy; '--allow_stub' appended
# to score.py lines (stub runs); for box scoring also with --expect_adapter_sha swapped to the fixture adapter's sha (the stub used it).
# Checks exit codes and that no __pycache__/ appears in the stage copy (PYTHONDONTWRITEBYTECODE=1), and the contrast without it.
# usage: python box_replay.py <ORDER.md> <stage copy (read only)>
import json, os, re, shutil, subprocess, sys, tempfile
ORDER, C = sys.argv[1], sys.argv[2]; txt = open(ORDER).read(); g = txt[txt.index("## g. Where it runs"):txt.index("## h. Runtime")]
ST = "/workspace/littleblue-eval-v0.5"; W = r"C:\Users\mdk32\lb-eval-bluebird-v1.0-r03"; MODEL = r"C:\Users\mdk32\models\Qwen2.5-3B-Instruct"
S = tempfile.mkdtemp(prefix="boxst05-"); shutil.rmtree(S); shutil.copytree(C, S, ignore=shutil.ignore_patterns("__pycache__"))
res = []
def pyc(): return sorted(os.path.relpath(os.path.join(d), S) for d, ds, fs in os.walk(S) if os.path.basename(d) == "__pycache__")
def bash(label, line, expect):
    line = line.replace(ST, S); r = subprocess.run(["bash", "-c", line], capture_output=True, text=True)
    res.append({"line": label, "rc": r.returncode, "expect": expect, "ok": r.returncode == expect, "pycache": pyc(), "tail": (r.stdout + r.stderr).strip().splitlines()[-1:] })
blocks = {m.group(1): m.group(2).strip().splitlines() for m in re.finditer(r"\*\*(Box landing step|Box scoring|E3c|E7)[^*]*\*\*.*?```bash\n(.*?)```", g, re.S)}
bash("landing mkdir", blocks["Box landing step"][0], 0)
# stub runs from the order's argv (set U), landed where E3c/E7 copy them
wd = tempfile.mkdtemp(prefix="boxwd05-")
for f in ("eval.py", "evalcore.py", "eval_rows.jsonl", "fewshot.json", "RUN-INPUTS.SHA256"): shutil.copy2(os.path.join(C, f), wd)
shutil.copytree(os.path.join(C, "tests", "fixtures", "adapter"), os.path.join(wd, "adapter"))
for step, od in (("E3a", "out-smoke-T"), ("E3b", "out-smoke-S"), ("E4", "out-T"), ("E5", "out-S")):
    b = re.search(r"^\*\*%s\*\*[^\n]*\n```powershell\n(.*?)```" % step, g, re.S | re.M).group(1)
    items = [x.replace(MODEL, os.path.join(C, "tests", "fixtures", "model")).replace("\\", "/") for x in re.findall(r"'([^']*)'", re.search(r"-ArgumentList (.*?) -WorkingDirectory", b).group(1))]
    r = subprocess.run([sys.executable, "-B", os.path.join(wd, "eval.py")] + items[1:] + ["--backend", "stub:gold"], cwd=wd, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-500:]
    for f in os.listdir(os.path.join(wd, od)): shutil.copy2(os.path.join(wd, od, f), os.path.join(S, "runs", "r03", od, f))
e3c = blocks["E3c"]
bash("E3c sha256sum -c out-smoke-T", e3c[0], 0); bash("E3c sha256sum -c out-smoke-S", e3c[1], 0)
bash("E3c smoke score T (+--allow_stub)", e3c[2] + " --allow_stub", 0); bash("E3c smoke score S (+--allow_stub)", e3c[3] + " --allow_stub", 0)
e7 = blocks["E7"]; bash("E7 sha256sum -c out-T", e7[0], 0); bash("E7 sha256sum -c out-S", e7[1], 0)
sc = blocks["Box scoring"][0]
bash("box scoring as written (+--allow_stub): real adapter sha vs stub's fixture adapter -> 15", sc + " --allow_stub", 15)
fx = __import__("hashlib").sha256(open(os.path.join(C, "tests", "fixtures", "adapter", "ADAPTER.SHA256"), "rb").read()).hexdigest()
bash("box scoring, adapter sha swapped to the fixture's (+--allow_stub)", sc.replace("35589c33dcc605024b44f6cadecae002998ffff4ecb75a7c52d5432f2988251b", fx).replace("runs/r03/score", "runs/r03/score2") + " --allow_stub", 0)
res.append({"line": "no __pycache__ anywhere in the stage copy after all box lines (PYTHONDONTWRITEBYTECODE=1)", "ok": pyc() == [], "pycache": pyc()})
# contrast: the same smoke score line without PYTHONDONTWRITEBYTECODE=1 writes __pycache__/ into the stage
bash("contrast: smoke score T without PYTHONDONTWRITEBYTECODE=1", e3c[2].replace("PYTHONDONTWRITEBYTECODE=1 ", "").replace("smoke-score-T", "smoke-score-T2") + " --allow_stub", 0)
res[-1]["ok"] = res[-1]["ok"] and res[-1]["pycache"] == ["__pycache__"]
shutil.rmtree(S); shutil.rmtree(wd)
for x in res: print(json.dumps(x))
print(json.dumps({"summary": f"{sum(x['ok'] for x in res)}/{len(res)} ok"}))
