# @0.6: runs tools/e5s1_check.py (read-only box check) against stopped out-S sessions made by the REAL eval.py GPU branch on the box CPU shim
# with the order's own E5-pin argument list and the real rows (same mapping and shim settings as resume_replay.py), then against copies
# whose eval-S.out progress peaks are rewritten (only those numbers) or whose out-S is tampered. Expected verdict per case is stated up front.
# The stopped session is the one resume_replay.py made (RESUME06_KEEP_S1), so both evidence files rest on the same shim session.
# usage: python check_replay.py <ORDER.md> <v0.5 stage (read only)> <python> <e5s1_check.py> <kept session dir>
import json, os, re, shutil, subprocess, sys, tempfile
ORDER, C, SPY, CHK = sys.argv[1:5]
txt = open(ORDER).read(); g = txt[txt.index("## g. Where it runs"):txt.index("## h. Runtime")]
W = r"C:\Users\mdk32\lb-eval-bluebird-v1.0-r03"; MODEL = r"C:\Users\mdk32\models\Qwen2.5-3B-Instruct"
VERS = json.dumps({"peft": "0.21.3", "torch": "2.15.0+cpu"})
b = re.search(r"^\*\*E5-pin\*\*[^\n]*\n```powershell\n(.*?)```", g, re.S | re.M).group(1)
P = re.findall(r"'([^']*)'", re.search(r"-ArgumentList (.*?) -WorkingDirectory", b).group(1))
w = sys.argv[5]                                      # stopped session kept by resume_replay.py (RESUME06_KEEP_S1): out-S/ + session1.stdout/.stderr
class _R: pass
r = _R(); r.stdout = open(os.path.join(w, "session1.stdout")).read(); r.stderr = open(os.path.join(w, "session1.stderr")).read(); r.returncode = 3
print(json.dumps({"session1_rc": r.returncode, "last_out": r.stdout.strip().splitlines()[-1]}))
def case(name, expect, edit_out=None, tamper=None):
    d = tempfile.mkdtemp(prefix="chk06-case-"); os.makedirs(os.path.join(d, "out-S"))
    for f in os.listdir(os.path.join(w, "out-S")): shutil.copy2(os.path.join(w, "out-S", f), os.path.join(d, "out-S", f))
    lines = r.stdout.splitlines()[1:]                       # drop the shim's own "SHIM_EVAL script sha256" line (not printed by eval.py)
    if edit_out:
        k = 0; new = []
        for l in lines:
            if l.startswith('{"batch"'): o = json.loads(l); o["peak_alloc"] = edit_out(o["batch"]); l = json.dumps(o)
            new.append(l)
        lines = new
    open(os.path.join(d, "eval-S.out"), "w").write("\n".join(lines) + "\n"); open(os.path.join(d, "eval-S.err"), "w").write(r.stderr)
    if tamper: tamper(d)
    q = subprocess.run([SPY, "-B", CHK, "--stage", C, "--dir", d, "--smoke_out", os.path.join(C, "runs", "r03", "smoke-S.out")], capture_output=True, text=True)
    outl = q.stdout.strip().splitlines(); verdict = outl[-1] if outl else q.stderr[-300:]
    curve = next((json.loads(x) for x in outl if x.startswith('{"curve"')), None)
    rec = {"case": name, "expect": expect, "rc": q.returncode, "verdict": verdict, "ok": verdict.startswith("E5S1 " + expect),
           "projection": curve and curve["projected_peak_fresh_session"], "largest_step": curve and curve["largest_single_batch_increase"],
           "failed_checks": [json.loads(x)["check"][:2] for x in outl if x.startswith('{"check"') and not json.loads(x)["ok"]]}
    print(json.dumps(rec)); shutil.rmtree(d); return rec
B0, P363 = 4030207488, 6990548992
ramp = lambda k: round(B0 + (P363 - B0) * k / 363)          # linear growth from the fresh level to Emma's batch-363 value (7001188352 stays the ABORT value)
res = [case("shim session as made (flat 4.03e9, then 7.0e9 at batch 364: a jump, not growth)", "STOP"),
       case("reported numbers: linear growth 4.03e9 -> 6990548992 at batch 363, ABORT 7001188352 after row 2920", "GO", edit_out=ramp),
       case("steep late growth: flat to batch 300, then to 6990548992 at 363", "STOP", edit_out=lambda k: B0 if k <= 300 else round(B0 + (P363 - B0) * (k - 300) / 63)),
       case("reported numbers + a torn last predictions line", "STOP", edit_out=ramp, tamper=lambda d: open(os.path.join(d, "out-S", "predictions-qwen25-3b-base-fs.jsonl"), "ab").write(b'{"id": "x')),
       case("reported numbers + last batch cut to 7 rows (partial batch)", "STOP", edit_out=ramp,
            tamper=lambda d: (lambda p, b: open(p, "wb").write(b"".join(l + b"\n" for l in b.split(b"\n")[:-2])))(os.path.join(d, "out-S", "predictions-qwen25-3b-base-fs.jsonl"), open(os.path.join(d, "out-S", "predictions-qwen25-3b-base-fs.jsonl"), "rb").read())),
       case("reported numbers + an empty predictions file", "STOP", edit_out=ramp, tamper=lambda d: open(os.path.join(d, "out-S", "predictions-qwen25-3b-base-fs.jsonl"), "wb").close()),
       case("reported numbers + a stray eval.lock in out-S", "STOP", edit_out=ramp, tamper=lambda d: open(os.path.join(d, "out-S", "eval.lock"), "w").write('{"pid": 1}')),
       case("reported numbers + .out truncated by a relaunch (only the header lines)", "STOP", edit_out=ramp,
            tamper=lambda d: open(os.path.join(d, "eval-S.out"), "w").write("".join(l + "\n" for l in r.stdout.splitlines()[1:5])))]
print(json.dumps({"summary": f"{sum(x['ok'] for x in res)}/{len(res)} cases as expected", "stage_pycache": os.path.isdir(os.path.join(C, "__pycache__"))}))
