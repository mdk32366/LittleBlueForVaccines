# @0.7: (1) parses every ```powershell block of ORDER@0.7 §g with PowerShell 7.4.6 (v0.5 evidence/ps_check.ps1, read only; nothing run on Windows);
# E8 unfilled (must fail: inert) and filled; E5-gpu-pid filled with 1344. (2) Runs the hash/Test-Path lines of E5-S2-keep and E5-S4-keep under pwsh
# on a mock dir (Linux). (3) Literal style of the @0.7 blocks. (4) Every @0.6 §g block is present byte-identical in @0.7 except none removed.
# usage: python3 -B ps_check07.py <ORDER@0.7.md> <pwsh> <ps_check.ps1>
import os, re, subprocess, sys, tempfile
ORDER, PWSH, PS1 = sys.argv[1:4]; txt = open(ORDER).read(); g = txt[txt.index("## g. Where it runs"):txt.index("## h. Runtime")]
d = tempfile.mkdtemp(prefix="psparse07-"); out = []; names = []
for m in re.finditer(r"```powershell\n(.*?)```", g, re.S):
    lab = re.findall(r"\*\*(E[0-9][A-Za-z0-9-]*)\*\*", g[:m.start()]); names.append((lab[-1] if lab else "?", m.group(1)))
seen = {}
for i, (n, b) in enumerate(names):
    seen[n] = seen.get(n, 0) + 1; open(os.path.join(d, f"{i:02d}-{n}{'-' + str(seen[n]) if seen[n] > 1 else ''}.ps1"), "w").write(b)
E8 = [b for n, b in names if n == "E8"][0]
open(os.path.join(d, "98-E8-filled.ps1"), "w").write(E8.replace("<E0A_SCHEME_GUID>", "381b4222-f694-41f0-9685-ff5bb260df2e").replace("<STANDBYIDLE_AC_DECIMAL>", "0").replace("<HIBERNATEIDLE_AC_DECIMAL>", "0"))
PIDB = [b for n, b in names if n == "E5-gpu-pid"][0]; open(os.path.join(d, "99-E5-gpu-pid-filled.ps1"), "w").write(PIDB.replace("<PID>", "1344"))
r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", PS1, d], capture_output=True, text=True)
ver = subprocess.run([PWSH, "-NoProfile", "-c", "$PSVersionTable.PSVersion.ToString()"], capture_output=True, text=True).stdout.strip()
out.append(f"# (1) parse only: {len(names)} PowerShell blocks in @0.7 §g + E8 filled + E5-gpu-pid filled (PowerShell {ver})"); out += r.stdout.strip().splitlines()
bad = [l for l in r.stdout.splitlines() if l.startswith("PARSE ERRORS") and not re.search(r"\d\d-E8\.ps1", l)]
out.append(f"# parse errors outside unfilled E8: {len(bad)}")
W = r"C:\Users\mdk32\lb-eval-bluebird-v1.0-r03"
EXPECT0 = "Get-CimInstance -ClassName Win32_Process | Where-Object { ($_.Name -like 'python*' -or $_.CommandLine -like '*eval.py*') -and $_.ProcessId -ne $PID } | Select-Object ProcessId,Name,CreationDate,CommandLine"
for name in ("E5-S-gate", "E5-S2-keep", "E5-S4-keep"):
    proc = [l for l in [b for n, b in names if n == name][0].splitlines() if "Win32_Process" in l]
    out.append(f"# (2a) {name} process line = the ruling's Name/CommandLine gate: {proc == [EXPECT0]}")
for name, od, log in (("E5-S2-keep", "out-S", "eval-S"), ("E5-S4-keep", "out-S-b4", "eval-S4")):
    blk = [b for n, b in names if n == name]; assert len(blk) == 1, name; blk = blk[0]
    m = tempfile.mkdtemp(prefix="mockwd-"); os.makedirs(os.path.join(m, od))
    for f, c in ((f"{log}.out", "ABORT 3 x\n"), (f"{log}.err", "e\n"), (f"{od}/ABORT-1.json", "{}"), (f"{od}/predictions-qwen25-3b-base-fs.jsonl", "{}\n"), (f"{od}/run-qwen25-3b-base-fs.json", "{}")):
        open(os.path.join(m, f), "w").write(c)
    run_lines = [l for l in blk.splitlines() if l.startswith(("Get-FileHash", "Get-ChildItem", "Test-Path"))]
    q = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-c", "\n".join(l.replace(W, m).replace("\\", "/") for l in run_lines)], capture_output=True, text=True)
    rows = [l for l in q.stdout.splitlines() if re.match(r"^[0-9A-F]{64} ", l.strip())]
    out.append(f"# (2) {name}: {len(run_lines)} lines run under pwsh on a mock work dir: {len(rows)} hash lines (expect 5), Test-Path -> {[l.strip() for l in q.stdout.splitlines() if l.strip() in ('True', 'False')]}, stderr {q.stderr.strip()[:200]!r}")
    proc = [l for l in blk.splitlines() if "Win32_Process" in l]
    EXPECT = "Get-CimInstance -ClassName Win32_Process | Where-Object { ($_.Name -like 'python*' -or $_.CommandLine -like '*eval.py*') -and $_.ProcessId -ne $PID } | Select-Object ProcessId,Name,CreationDate,CommandLine"
    out.append(f"#    process line = the 9:00 PM PT ruling's Name/CommandLine gate: {proc == [EXPECT]}")
NEW = ("E5-gpu-pid", "E5-free", "E5-S-gate", "E5-b4-pin", "E5-b4-pin-floor", "E6-S4", "E5-S4-keep", "E7-A", "E5-pin-limit", "E5-S2-keep")
nb = [b for n, b in names if n in NEW]
style = len(nb) == len(NEW) and all("..." not in b and "…" not in b and "as @0." not in b for b in nb) and all(W in b for n, b in names if n in NEW and n not in ("E5-gpu-pid", "E5-free", "E5-S-gate"))
sp = [b for n, b in names if n in ("E5-b4-pin", "E5-b4-pin-floor", "E5-pin-limit")]
style = style and all(r"-FilePath C:\Users\mdk32\venvs\bia562-train\Scripts\python.exe" in b and "'0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d'" in b for b in sp)
out.append(f"# (3) @0.7 blocks literal (no '...', no '…', no 'as @0.', absolute work dir, venv python, literal RUN PIN): {style}; new blocks: {[n for n, b in names if n in NEW]}")
same = [b for n, b in names if n == "E5-pin-resume"][0] == [b for n, b in names if n == "E5-pin"][0]
out.append(f"# (3b) E5-pin-resume == E5-pin byte for byte: {same}")
o6 = open("/workspace/littleblue-specs/ORDER-bluebird-eval@0.6.md").read(); g6 = o6[o6.index("## g. Where it runs"):o6.index("## h. Runtime")]
b6 = re.findall(r"```powershell\n(.*?)```", g6, re.S); b7 = [b for n, b in names if n not in NEW]
out.append(f"# (4) @0.7 §g minus its {len(NEW)} new blocks == @0.6 §g's {len(b6)} blocks minus its last (the old E5-S2-keep, replaced by the @0.7 one), byte for byte and in order: {b7 == b6[:-1]} (@0.6 E5-S2-keep is its last block: {b6[-1].count(chr(10)) == 5})")
print("\n".join(out))
