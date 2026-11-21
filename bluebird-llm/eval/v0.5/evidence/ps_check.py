# @0.5: (1) extracts every ```powershell block of ORDER §g and parses it with PowerShell 7.4.6's parser (ps_check.ps1; nothing is run);
# E8 is parsed unfilled (must fail to parse: inert) and filled (must parse). (2) Runs two NEW lines under pwsh on the box, never on Windows:
# the E0a weights line (model path mapped to mock dirs) and the E8 restore guard (filled, with a mock `powercfg` function that only echoes).
# usage: python ps_check.py <ORDER.md> <pwsh>
import os, re, subprocess, sys, tempfile, json
ORDER, PWSH = sys.argv[1], sys.argv[2]; txt = open(ORDER).read(); g = txt[txt.index("## g. Where it runs"):txt.index("## h. Runtime")]
d = tempfile.mkdtemp(prefix="psparse05-"); out = []
blocks = re.findall(r"^(\*\*[^*]+\*\*)?[^\n]*\n```powershell\n(.*?)```", g, re.S | re.M)
# name each block by the nearest preceding bold label
names = []; pos = 0
for m in re.finditer(r"```powershell\n(.*?)```", g, re.S):
    lab = re.findall(r"\*\*(E[0-9][A-Za-z0-9-]*)\*\*", g[:m.start()]); names.append((lab[-1] if lab else "?", m.group(1)))
seen = {}
for i, (n, b) in enumerate(names):
    seen[n] = seen.get(n, 0) + 1; fn = f"{i:02d}-{n}{'-' + str(seen[n]) if seen[n] > 1 else ''}.ps1"
    open(os.path.join(d, fn), "w").write(b)
E8 = [b for n, b in names if n == "E8"][0]
FILLED = E8.replace("<E0A_SCHEME_GUID>", "381b4222-f694-41f0-9685-ff5bb260df2e").replace("<STANDBYIDLE_AC_DECIMAL>", "1800").replace("<HIBERNATEIDLE_AC_DECIMAL>", "0")
open(os.path.join(d, "99-E8-filled.ps1"), "w").write(FILLED)
r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ps_check.ps1"), d], capture_output=True, text=True)
out.append(f"# (1) parse only: {len(names)} PowerShell blocks in §g + E8 filled (PowerShell {subprocess.run([PWSH, '-NoProfile', '-c', '$PSVersionTable.PSVersion.ToString()'], capture_output=True, text=True).stdout.strip()})")
out += r.stdout.strip().splitlines() + ([r.stderr.strip()] if r.stderr.strip() else [])
# (2a) weights line on mock dirs
MODEL = r"C:\Users\mdk32\models\Qwen2.5-3B-Instruct"
wl = [l for l in [b for n, b in names if n == "E0a"][0].splitlines() if "model.safetensors.index.json" in l][0]
def mock(kind):
    m = tempfile.mkdtemp(prefix="mockmodel-"); idx = {"weight_map": {"a.w": "model-00001-of-00002.safetensors", "b.w": "model-00002-of-00002.safetensors", "c.w": "model-00001-of-00002.safetensors"}}
    if kind in ("ok", "missing", "zero"):
        json.dump(idx, open(os.path.join(m, "model.safetensors.index.json"), "w"))
        open(os.path.join(m, "model-00001-of-00002.safetensors"), "wb").write(b"x" * 10)
        if kind == "ok": open(os.path.join(m, "model-00002-of-00002.safetensors"), "wb").write(b"y" * 20)
        if kind == "zero": open(os.path.join(m, "model-00002-of-00002.safetensors"), "wb").write(b"")
    if kind == "single": open(os.path.join(m, "model.safetensors"), "wb").write(b"z" * 5)
    return m
out.append("# (2a) E0a weights line under pwsh, model path mapped to a mock dir")
for kind in ("ok", "missing", "zero", "single", "none"):
    m = mock(kind); line = wl.replace(MODEL, m)
    r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-c", line], capture_output=True, text=True)
    out.append(f"{kind:8s} -> " + " / ".join(x.strip() for x in r.stdout.strip().splitlines()) + (f"  STDERR {r.stderr.strip()[:200]}" if r.stderr.strip() else ""))
# (2b) E8 guard, filled, mock powercfg (echo only)
guard = [l for l in FILLED.splitlines() if l.startswith("if ((powercfg /getactivescheme)")][0]
def mockpc(active, arr=False):
    first = f"@('', 'Power Scheme GUID: {active}  (Balanced)')" if arr else f"'Power Scheme GUID: {active}  (Balanced)'"
    return "function powercfg { if ($args[0] -eq '/getactivescheme') { " + first + " } else { 'CALLED powercfg ' + ($args -join ' ') } }; "
out.append("# (2b) E8 restore guard under pwsh, filled (GUID 381b4222-f694-41f0-9685-ff5bb260df2e, 1800, 0), mock powercfg that only echoes")
for label, active, arr in (("same scheme", "381b4222-f694-41f0-9685-ff5bb260df2e", False), ("same scheme, 2-line output", "381b4222-f694-41f0-9685-ff5bb260df2e", True),
                           ("scheme changed", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", False), ("scheme changed, 2-line output", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", True)):
    r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-c", mockpc(active, arr) + guard], capture_output=True, text=True)
    out.append(f"{label:30s} -> " + " / ".join(x.strip() for x in r.stdout.strip().splitlines()) + (f"  STDERR {r.stderr.strip()[:200]}" if r.stderr.strip() else ""))
g2 = [l for l in E8.splitlines() if l.startswith("if ((powercfg")][0].replace("<STANDBYIDLE_AC_DECIMAL>", "1800").replace("<HIBERNATEIDLE_AC_DECIMAL>", "0")
r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-c", mockpc("381b4222-f694-41f0-9685-ff5bb260df2e") + g2], capture_output=True, text=True)
out.append(f"{'GUID left unfilled':30s} -> " + " / ".join(x.strip() for x in r.stdout.strip().splitlines()))
print("\n".join(out))
