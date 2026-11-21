# Every stub (tests/stubs.py) through the real pipeline: eval.py --backend stub:replay=<file> -> score.py. Plus the three completeness stubs
# from the review (smoke subset, sh/rn/pp missing, duplicate ids), which must be REFUSED. usage: stub_harness.py [OUT.json]
# Writes OUT.json (default sim/STUB-OUTCOMES.json; @0.2 N7: the test suite passes a temp path, so it never writes into the stage).
import json, os, subprocess, sys, tempfile, hashlib, concurrent.futures as cf
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(H, "tests")); sys.path.insert(0, H)
import stubs
from evalcore import plan_batches
PY = sys.executable; ROWS = os.path.join(H, "eval_rows.jsonl"); MAN = os.path.join(H, "RUN-INPUTS.SHA256"); SMAN = os.path.join(H, "SCORE-INPUTS.SHA256"); AD = os.path.join(H, "tests/fixtures/adapter")
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
MS, SS, AS = sha(MAN), sha(SMAN), sha(os.path.join(AD, "ADAPTER.SHA256"))
rows = [json.loads(l) for l in open(ROWS)]
JOBS = {}
def run_stub(name):
    fn, post = JOBS[name]
    t = tempfile.mkdtemp(prefix=f"stub-{name}-"); src = os.path.join(t, "src.jsonl")
    with open(src, "w") as f:
        for r in rows: f.write(json.dumps({"id": r["id"], "raw": fn(r)}) + "\n")
    out = os.path.join(t, "out")
    e = subprocess.run([PY, os.path.join(H, "eval.py"), "--rows", ROWS, "--expect_manifest_sha", MS, "--out_dir", out, "--tag", "T",
                        "--adapter", os.path.join(AD, "final-adapter"), "--backend", f"stub:replay={src}"], capture_output=True, text=True)
    assert e.returncode == 0, e.stdout + e.stderr
    pred = os.path.join(out, "predictions-T.jsonl")
    if post: post(pred)
    s = subprocess.run([PY, os.path.join(H, "score.py"), "--rows", ROWS, "--expect_score_manifest_sha", SS, "--expect_run_manifest_sha", MS, "--expect_adapter_sha", AS, "--pred", f"T={pred}",
                        "--primary", "T", "--out", os.path.join(t, "score"), "--allow_stub", "--no_ci"], capture_output=True, text=True)
    if s.returncode: return {"stub": name, "outcome": f"REFUSED exit {s.returncode}", "why": s.stderr.strip()[-300:]}
    S = json.load(open(os.path.join(t, "score", "SCORES.json"))); m = S["models"]["T"]["s"]; C = m["decision_counts"]
    return {"stub": name, "outcome": S["verdict"], "why": S["verdict_reasons"][:3], "test_correct": m["correct_all"], "valid": m["valid_json_schema"],
            "memo": {k: S["memorisation_test"][k] for k in ("b_old_not_placebo", "c_placebo_not_old", "p_value", "fires")},
            "failed_bars": [b["bar"].split(":")[0] for b in S["bars"] if b["status"] != "PASS"]}
def keep_ids(f, pred):
    L = [l for l in open(pred) if f(json.loads(l)["id"])]; open(pred, "w").writelines(L)
plan64 = {r["id"] for b in plan_batches(rows, "zero", 8, "", 64) for r in b}
kind = {r["id"]: r["kind"] for r in rows}
POST = {"gold_partial64": lambda p: keep_ids(lambda i: i in plan64, p),
        "gold_no_sh_rn_pp": lambda p: keep_ids(lambda i: kind[i] in ("test", "cf", "ar"), p),
        "dup": lambda p: open(p, "a").writelines([l.replace('"raw": ', '"raw": "garbage", "x": ', 1) for l in open(p)][:5])}
EXPECT = dict(stubs.EXPECT, gold_partial64="REFUSED exit 16", gold_no_sh_rn_pp="REFUSED exit 16", dup="REFUSED exit 16")
if __name__ == "__main__":
    JOBS.update({n: (f, None) for n, f in stubs.all_stubs(rows).items()}); JOBS.update({n: (stubs.gold, p) for n, p in POST.items()})
    import multiprocessing as mp
    with cf.ProcessPoolExecutor(int(os.environ.get("LBE_STUB_JOBS", "4")), mp_context=mp.get_context("fork")) as ex: res = list(ex.map(run_stub, list(JOBS)))
    ok = 0
    for r in res:
        r["expected"] = EXPECT[r["stub"]]; r["match"] = r["outcome"] in EXPECT[r["stub"]].split("|"); ok += r["match"]
        print(f"{r['stub']:24s} {r['outcome']:18s} expected {r['expected']:24s} {'OK' if r['match'] else 'WRONG'}  {r.get('why')}")
    json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, "sim", "STUB-OUTCOMES.json"), "w"), indent=1)
    print(f"{ok}/{len(res)} stubs on the expected outcome"); sys.exit(0 if ok == len(res) else 1)
