# jf0.0: extract every ```powershell block of the order into ps-blocks-jf/NN-<label>.ps1 and parse each (never run) with the
# PowerShell parser (v0.5 evidence/ps_check.ps1). Args: <order.md> <pwsh>. Prints one line per block.
import os, re, subprocess, sys
order, pwsh = sys.argv[1], sys.argv[2]; d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ps-blocks-jf")
os.makedirs(d, exist_ok=True); [os.remove(os.path.join(d, f)) for f in os.listdir(d)]
lines = open(order, encoding="utf-8").read().split("\n"); label = "x"; n = 0; i = 0
while i < len(lines):
    m = re.match(r"^\*\*(J\d+[a-z]?(?:-floor)?)(?: = [A-Za-z0-9-]+)?\*\*", lines[i])
    if m: label = m.group(1)
    if lines[i] == "```powershell":
        j = i + 1
        while lines[j] != "```": j += 1
        n += 1; open(os.path.join(d, f"{n:02d}-{label}.ps1"), "w", encoding="utf-8").write("\n".join(lines[i + 1:j]) + "\n"); i = j
    i += 1
r = subprocess.run([pwsh, "-NoProfile", "-File", "/workspace/littleblue-eval-v0.5/evidence/ps_check.ps1", d], capture_output=True, text=True)
v = subprocess.run([pwsh, "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"], capture_output=True, text=True).stdout.strip()
print(f"# parse only: {n} PowerShell blocks in ORDER-bluebird-json-fix@0.0 (PowerShell {v})"); print(r.stdout.strip()); print(r.stderr.strip())
