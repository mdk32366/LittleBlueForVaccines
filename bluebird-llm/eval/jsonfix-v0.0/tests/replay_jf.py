# jf0.0 replay (box, CPU): the REAL jf eval.py + real transformers generate() + jsonslot, via tests/shim_jf.py (tiny Qwen2, teacher-forced
# to "want" a scripted output per row). Whole out-T batches are replayed, so batch composition equals the laptop run's.
# Usage: PYTHONDONTWRITEBYTECODE=1 <review venv>/bin/python -B tests/replay_jf.py <out.jsonl> [all]
#   default: the batches that hold the 13 strict-invalid out-T rows + 12 evenly spaced other batches; "all": every batch (3569 rows).
# Per scenario it prints/records rc, last stdout line, and per row: raw, strict validity/reason, hit_max, forced, equal-to-out-T.
import hashlib, json, os, shutil, subprocess, sys, tempfile, collections
J = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); V05 = "/workspace/littleblue-eval-v0.5"; R03 = V05 + "/runs/r03"
sys.path.insert(0, J); from evalcore import parse_strict, plan_batches
PY = os.environ.get("LBE_SHIM_PY", "/workspace/littleblue-fullrun-review/venv/bin/python")
FX = V05 + "/tests/fixtures"; AD = FX + "/adapter/final-adapter"
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
rows = [json.loads(l) for l in open(J + "/eval_rows.jsonl", encoding="utf-8")]; byid = {r["id"]: r for r in rows}
T = {json.loads(l)["id"]: json.loads(l) for l in open(R03 + "/out-T/predictions-bluebird-v1.0-e2.jsonl", encoding="utf-8")}
bs = plan_batches(rows, "zero", 8)
bad = sorted(i for i, p in T.items() if parse_strict(p["raw"])[1] is not None)
want_b = sorted({T[i]["batch"] for i in bad})
mode_all = len(sys.argv) > 2 and sys.argv[2] == "all"
if mode_all: sel_b = list(range(len(bs)))
else:
    others = [k for k in range(len(bs)) if k not in want_b and len(bs[k]) == 8]
    sel_b = sorted(set(want_b) | {others[round(i * (len(others) - 1) / 11)] for i in range(12)})
sub = [r for k in sel_b for r in bs[k]]
assert [[r["id"] for r in b] for b in plan_batches(sub, "zero", 8)] == [[r["id"] for r in bs[k]] for k in sel_b], "subset batches != laptop batches"
HYP = json.load(open(J + "/evidence/truncation-hypotheses.json")) if os.path.exists(J + "/evidence/truncation-hypotheses.json") else {}
def stage(script):
    w = tempfile.mkdtemp(prefix="jf-replay-")
    for f in ("eval.py", "evalcore.py", "jsonslot.py", "fewshot.json"): shutil.copy(os.path.join(J, f), w)
    open(os.path.join(w, "eval_rows.jsonl"), "w", encoding="utf-8").write("".join(json.dumps(r, sort_keys=True) + "\n" for r in sub))
    open(os.path.join(w, "RUN-INPUTS.SHA256"), "w").write("".join(f"{sha(os.path.join(w, f))}  {f}\n" for f in ("eval_rows.jsonl", "fewshot.json", "eval.py", "evalcore.py", "jsonslot.py")))
    open(os.path.join(w, "script.jsonl"), "w", encoding="utf-8").write("".join(json.dumps({"ids_sha256": r["ids_sha256"], "target": script(r)}) + "\n" for r in sub))
    return w
def run(w, out, extra):
    cmd = [PY, "-B", os.path.join(J, "tests", "shim_jf.py"), os.path.join(w, "eval.py"), "--rows", os.path.join(w, "eval_rows.jsonl"),
           "--expect_manifest_sha", sha(os.path.join(w, "RUN-INPUTS.SHA256")), "--model", FX + "/model", "--adapter", AD,
           "--out_dir", os.path.join(w, out), "--tag", "t", "--expect_versions", json.dumps({"peft": "0.21.3", "torch": "2.15.0+cpu"})] + extra
    r = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "SHIM_SCRIPT": os.path.join(w, "script.jsonl")}, cwd=w)
    P = {}
    pp = os.path.join(w, out, "predictions-t.jsonl")
    if os.path.exists(pp): P = {json.loads(l)["id"]: json.loads(l) for l in open(pp, encoding="utf-8")}
    return r, P
res = {"batches": sel_b, "rows": len(sub), "bad_rows": bad, "scenarios": {}}
scen = [("R0 recorded script, no constraint, cap 128 (mock reproduces out-T)", lambda r: T[r["id"]]["raw"], ["--max_new_tokens", "128"]),
        ("R1 recorded script, json-slot, cap 256", lambda r: T[r["id"]]["raw"], ["--max_new_tokens", "256", "--constraint", "json-slot"]),
        ("R2 recorded script, json-slot, cap 128", lambda r: T[r["id"]]["raw"], ["--max_new_tokens", "128", "--constraint", "json-slot"])]
if HYP and not mode_all:
    scen.append(("R3 primary truncation hypotheses, json-slot, cap 256", lambda r: HYP["primary"].get(r["id"], T[r["id"]]["raw"]), ["--max_new_tokens", "256", "--constraint", "json-slot"]))
    scen.append(("R4 upper truncation hypotheses, json-slot, cap 256", lambda r: HYP["upper"].get(r["id"], T[r["id"]]["raw"]), ["--max_new_tokens", "256", "--constraint", "json-slot"]))
    scen.append(("R5 primary truncation hypotheses, no constraint, cap 256", lambda r: HYP["primary"].get(r["id"], T[r["id"]]["raw"]), ["--max_new_tokens", "256"]))
if mode_all: scen = scen[:2]
for name, script, extra in scen:
    w = stage(script); r, P = run(w, "o", extra)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    per = {}
    for i, p in P.items():
        o, e = parse_strict(p["raw"])
        per[i] = {"valid": e is None, "reason": e, "hit_max": p["hit_max"], "new_tokens": p["new_tokens"], "max_new": p.get("max_new"), "forced": p.get("forced"),
                  "same_as_outT": p["raw"] == T[i]["raw"], "raw": p["raw"] if (i in bad or p["raw"] != T[i]["raw"]) else None}
    n_same = sum(v["same_as_outT"] for v in per.values()); n_valid = sum(v["valid"] for v in per.values())
    good = [i for i in per if i not in bad]
    summ = {"rc": r.returncode, "last": last[:300], "rows": len(per), "valid": n_valid, "same_as_outT": n_same,
            "good_rows_same": sum(per[i]["same_as_outT"] for i in good), "good_rows": len(good),
            "bad_rows_valid_now": sum(per[i]["valid"] for i in bad if i in per), "hit_max": sum(v["hit_max"] for v in per.values()),
            "rows_forced": sum(bool(v["forced"]) for v in per.values()), "err_tail": r.stderr[-800:] if r.returncode else ""}
    res["scenarios"][name] = {"summary": summ, "bad": {i: per.get(i) for i in bad}}
    print(name, json.dumps(summ), flush=True)
    shutil.rmtree(w, ignore_errors=True)
json.dump(res, open(sys.argv[1], "w"), indent=1, sort_keys=True)
