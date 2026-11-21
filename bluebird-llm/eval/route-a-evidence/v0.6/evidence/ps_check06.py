# @0.6: (1) parses every ```powershell block of ORDER@0.6 §g with PowerShell 7.4.6's parser (the v0.5 stage's evidence/ps_check.ps1, read
# only; nothing is run); E8 parsed unfilled (must fail: inert) and filled. (2) Runs the E5-S1-keep / E5-S2-keep hash and Test-Path lines under
# pwsh on the box (never on Windows) with the work dir mapped to a mock dir. Get-CimInstance and nvidia-smi are not available on Linux: parsed only.
# (3) Checks the new blocks for literal style: no '...', no '…', no 'as @0.', absolute paths, the venv python, the RUN PIN.
# usage: python ps_check06.py <ORDER@0.6.md> <pwsh> <ps_check.ps1>
import os, re, subprocess, sys, tempfile, json
ORDER, PWSH, PS1 = sys.argv[1:4]; txt = open(ORDER).read(); g = txt[txt.index("## g. Where it runs"):txt.index("## h. Runtime")]
d = tempfile.mkdtemp(prefix="psparse06-"); out = []; names = []
for m in re.finditer(r"```powershell\n(.*?)```", g, re.S):
    lab = re.findall(r"\*\*(E[0-9][A-Za-z0-9-]*)\*\*", g[:m.start()]); names.append((lab[-1] if lab else "?", m.group(1)))
seen = {}
for i, (n, b) in enumerate(names):
    seen[n] = seen.get(n, 0) + 1; open(os.path.join(d, f"{i:02d}-{n}{'-' + str(seen[n]) if seen[n] > 1 else ''}.ps1"), "w").write(b)
E8 = [b for n, b in names if n == "E8"][0]
open(os.path.join(d, "99-E8-filled.ps1"), "w").write(E8.replace("<E0A_SCHEME_GUID>", "381b4222-f694-41f0-9685-ff5bb260df2e").replace("<STANDBYIDLE_AC_DECIMAL>", "0").replace("<HIBERNATEIDLE_AC_DECIMAL>", "0"))
r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", PS1, d], capture_output=True, text=True)
ver = subprocess.run([PWSH, "-NoProfile", "-c", "$PSVersionTable.PSVersion.ToString()"], capture_output=True, text=True).stdout.strip()
out.append(f"# (1) parse only: {len(names)} PowerShell blocks in @0.6 §g + E8 filled (PowerShell {ver})"); out += r.stdout.strip().splitlines()
bad = [l for l in r.stdout.splitlines() if l.startswith("PARSE ERRORS") and "E8.ps1" not in l and not re.search(r"-E8\.ps1", l)]
out.append(f"# parse errors outside unfilled E8: {len(bad)}")
W = r"C:\Users\mdk32\lb-eval-bluebird-v1.0-r03"
for name in ("E5-S1-keep", "E5-S2-keep"):
    blk = [b for n, b in names if n == name]; assert len(blk) == 1, name; blk = blk[0]
    m = tempfile.mkdtemp(prefix="mockwd-"); os.makedirs(os.path.join(m, "out-S"))
    for f, c in (("eval-S.out", "ABORT 3 x\n"), ("eval-S.err", "e\n"), ("out-S/ABORT-1.json", "{}"), ("out-S/predictions-qwen25-3b-base-fs.jsonl", "{}\n"), ("out-S/run-qwen25-3b-base-fs.json", "{}")):
        open(os.path.join(m, f), "w").write(c)
    run_lines = [l for l in blk.splitlines() if l.startswith(("Get-FileHash", "Get-ChildItem", "Test-Path"))]
    script = "\n".join(l.replace(W, m).replace("\\", "/") for l in run_lines)
    q = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-c", script], capture_output=True, text=True)
    rows = [l for l in q.stdout.splitlines() if re.match(r"^[0-9A-F]{64} ", l.strip())]
    out.append(f"# (2) {name}: {len(run_lines)} lines run under pwsh on a mock work dir: {len(rows)} hash lines (expect 5), Test-Path -> {[l.strip() for l in q.stdout.splitlines() if l.strip() in ('True', 'False')]}, stderr {q.stderr.strip()[:200]!r}")
    out.append("#    " + " | ".join(l.strip()[:16] + " " + os.path.relpath(l.split()[-1], m) for l in rows))
new = [b for n, b in names if n in ("E5-S1-keep", "E5-S2-keep", "E5-pin-resume")]
style = all("..." not in b and "…" not in b and "as @0." not in b for b in new) and all(r"C:\Users\mdk32\lb-eval-bluebird-v1.0-r03" in b for b in new)
res = [b for n, b in names if n == "E5-pin-resume"][0]
style = style and r"-FilePath C:\Users\mdk32\venvs\bia562-train\Scripts\python.exe" in res and "'0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d'" in res
same = res == [b for n, b in names if n == "E5-pin"][0]
out.append(f"# (3) new blocks literal (no '...', no '…', no 'as @0.', absolute work dir, venv python, literal RUN PIN): {style}; E5-pin-resume == E5-pin byte for byte: {same}")
o5 = open("/workspace/littleblue-specs/ORDER-bluebird-eval@0.5.md").read(); g5 = o5[o5.index("## g. Where it runs"):o5.index("## h. Runtime")]
b5 = re.findall(r"```powershell\n(.*?)```", g5, re.S); b6 = [b for n, b in names if n not in ("E5-S1-keep", "E5-S2-keep", "E5-pin-resume")]
out.append(f"# (4) @0.6 §g minus its 3 new blocks == @0.5 §g blocks, byte for byte and in order: {b6 == b5} ({len(b5)} @0.5 blocks; @0.6 adds E5-S1-keep, E5-pin-resume, E5-S2-keep)")
print("\n".join(out))
