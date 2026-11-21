# @0.5: replay every eval.py argument list written in ORDER §g through the real eval.py on the box (stub backend), Windows paths mapped
# to a temp work dir (outside every stage). Mapping only: C:\...\lb-eval-bluebird-v1.0-r03 -> temp dir, base model -> tests/fixtures/model,
# backslash -> slash, adapter = tests/fixtures/adapter; '--backend stub:gold' appended. '<MIN_FREE_BYTES>' is replayed both unfilled and filled.
# usage: python argv05.py <ORDER.md> <stage copy>
import json, os, re, shutil, subprocess, sys, tempfile
ORDER, C = sys.argv[1], sys.argv[2]; PY = sys.executable; txt = open(ORDER).read()
g = txt[txt.index("## g. Where it runs"):txt.index("## h. Runtime")]
W = r"C:\Users\mdk32\lb-eval-bluebird-v1.0-r03"; MODEL = r"C:\Users\mdk32\models\Qwen2.5-3B-Instruct"
def workdir():
    w = tempfile.mkdtemp(prefix="argv05-")
    for f in ("eval.py", "evalcore.py", "eval_rows.jsonl", "fewshot.json", "RUN-INPUTS.SHA256"): shutil.copy2(os.path.join(C, f), w)
    shutil.copytree(os.path.join(C, "tests", "fixtures", "adapter"), os.path.join(w, "adapter")); return w
def mapv(v, w): return v.replace(W, w).replace(MODEL, os.path.join(C, "tests", "fixtures", "model")).replace("\\", "/")
def block(name):   # the powershell block right after a line starting **name**
    m = re.search(r"^\*\*%s\*\*[^\n]*\n```powershell\n(.*?)```" % re.escape(name), g, re.S | re.M); assert m, name; return m.group(1)
def sp_items(name):
    b = block(name); al = re.search(r"-ArgumentList (.*?) -WorkingDirectory (\S+)", b); assert al.group(2) == W, (name, al.group(2))
    return re.findall(r"'([^']*)'", al.group(1))
def amp_items(name):
    ln = [l for l in block(name).splitlines() if l.startswith("& ")]; assert len(ln) == 1, name
    return [x[1:-1] if x.startswith("'") and x.endswith("'") else x for x in ln[0].split()[2:]]
res = []
def run(label, items, w=None, expect=0, check_nothing=False):
    w = w or workdir(); argv = [mapv(x, w) for x in items]
    script = os.path.join(w, "eval.py") if argv[0] == "eval.py" else argv[0]
    before = sorted(os.listdir(w))
    r = subprocess.run([PY, "-B", script] + argv[1:] + ["--backend", "stub:gold"], cwd=w, capture_output=True, text=True)
    out = r.stdout.strip().splitlines(); err = r.stderr.strip().splitlines()
    rec = {"cmd": label, "rc": r.returncode, "expect": expect, "ok": r.returncode == expect, "argv_from_order": items,
           "last_out": out[-1:] if out else [], "last_err": err[-1:] if err else []}
    if check_nothing: rec["nothing_written"] = sorted(os.listdir(w)) == before; rec["ok"] = rec["ok"] and rec["nothing_written"]
    res.append(rec); return w
FILL = "5000000000"
for step in ("E3a", "E3b", "E4", "E5"):
    for var in ("", "-pin", "-pin-floor", "-floor"):
        items = sp_items(step + var)
        if "<MIN_FREE_BYTES>" in items:
            run(f"{step}{var} unfilled '<MIN_FREE_BYTES>'", items, expect=2, check_nothing=True)
            items = [FILL if x == "<MIN_FREE_BYTES>" else x for x in items]
            run(f"{step}{var} filled {FILL}", items, expect=0)
        else:
            run(f"{step}{var}", items, expect=0)
for name in ("E0b", "E0b-pin", "E0b-pin-floor", "E0b-floor"):
    items = amp_items(name)
    if "<MIN_FREE_BYTES>" in items:
        run(f"{name} unfilled '<MIN_FREE_BYTES>' (stub)", items, expect=2, check_nothing=True)
        items = [FILL if x == "<MIN_FREE_BYTES>" else x for x in items]
        run(f"{name} filled {FILL} (stub: preflight path, no GPU)", items, expect=0)
    else:
        run(f"{name} (stub: preflight path, no GPU)", items, expect=0)
# set U lines must be byte-identical to @0.4's (argv level)
o4 = open("/workspace/littleblue-specs/ORDER-bluebird-eval@0.4.md").read()
for step in ("E3a", "E3b", "E4", "E5"):
    m4 = re.search(r"^\*\*%s\*\*[^\n]*\n```powershell\n(.*?)```" % step, o4, re.S | re.M).group(1)
    res.append({"cmd": f"{step} set U == @0.4 {step} (block text)", "ok": m4 == block(step)})
# every Start-Process line: same -FilePath, -WorkingDirectory, absolute redirects under the work dir; pins literal
sps = re.findall(r"^Start-Process .*$", g, re.M)
chk = all(l.startswith(r"Start-Process -FilePath C:\Users\mdk32\venvs\bia562-train\Scripts\python.exe -ArgumentList 'eval.py',") and f"-WorkingDirectory {W} " in l
          and re.search(r"-RedirectStandardOutput C:\\Users\\mdk32\\lb-eval-bluebird-v1\.0-r03\\(smoke-T|smoke-S|eval-T|eval-S)\.out -RedirectStandardError C:\\Users\\mdk32\\lb-eval-bluebird-v1\.0-r03\\\1\.err -WindowStyle Hidden -PassThru$", l)
          and "'--expect_manifest_sha','0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d'" in l and " " not in "".join(re.findall(r"'([^']*)'", l)) for l in sps)
res.append({"cmd": f"all {len(sps)} Start-Process lines: python path, work dir, absolute redirects, literal RUN PIN, no item with a space", "ok": chk and len(sps) == 16})
for x in res: print(json.dumps(x))
print(json.dumps({"summary": f"{sum(x['ok'] for x in res)}/{len(res)} ok"}))
