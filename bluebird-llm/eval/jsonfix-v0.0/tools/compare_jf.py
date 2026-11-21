# jf0.0 before/after report (box, CPU, read-only). Recomputes every figure with the UNCHANGED v0.5 scorer functions (score.py a4d7a374...,
# imported, never run as a script here), so the numbers are the scorer's own. Two uses:
#  post-run:  compare_jf.py --after_per_row <score-jf>/per_row.jsonl --after_scores <score-jf>/SCORES.json --t_after <out-T-jf preds> --out REPORT-jf.md
#  predict:   compare_jf.py --predict <replay json> --scenario "<name>" --out PREDICTION-jf.md   (out-T with the replayed rows patched in; a prediction)
# Before = runs/r03/score (REPORT.md eecf22aa...). S = the before per_row model S (out-S-b4), reused unchanged for the paired T-jf vs S figure,
# because score.py takes one RUN pin and S was run under 0769b861..., T-jf under the jf pin (order §4).
import argparse, collections, hashlib, json, os, sys
sys.dont_write_bytecode = True
V05 = "/workspace/littleblue-eval-v0.5"; R03 = V05 + "/runs/r03"; sys.path.insert(0, V05)
import score as SC, evalstats as st
from evalcore import parse_strict
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
PINS = {"score.py": "a4d7a3746e17549ba5e21965df3dcad916758faecaf2425dfaebdda99d424045", "evalcore.py": "2d1d2f9bc0716938278a6d9dee9d19830ec673721c68d0753390127c3104ba75",
        "evalstats.py": "9464f55d3d993557a5d48cc30e180feb8a24ba65742ecc494f5dc423787bc537", "eval_rows.jsonl": "dd3fc66d50373f123ce4f76602658794a438f6250c0953e8fffa7c84934db899"}
BEFORE = {"runs/r03/score/REPORT.md": "eecf22aad959fb80df64c40a87a01abf7bcff31fba92c82c5033a4fc6dfed4e5", "runs/r03/score/SCORES.json": "cd0e9ac281a72dc504c30200ad398101d71c0eb5e9208350d5e74541a248478c",
          "runs/r03/score/per_row.jsonl": "6f109f251e37442cb1f6c46d0b2753a63701587a39c3d09a9f79a3f2f62466e4", "runs/r03/out-T/predictions-bluebird-v1.0-e2.jsonl": "8b2fab1571464515bf517419d84e476a99b847d65245110491b5883fc7f3fed3"}
for f, h in {**PINS, **BEFORE}.items():
    if sha(os.path.join(V05, f)) != h: sys.exit(f"PIN MISMATCH {f}")
ap = argparse.ArgumentParser(); ap.add_argument("--after_per_row"); ap.add_argument("--after_scores"); ap.add_argument("--t_after"); ap.add_argument("--predict"); ap.add_argument("--scenario")
ap.add_argument("--out", required=True); a = ap.parse_args()
rows = {r["id"]: r for r in (json.loads(l) for l in open(V05 + "/eval_rows.jsonl", encoding="utf-8"))}
per = collections.defaultdict(dict)
for l in open(R03 + "/score/per_row.jsonl", encoding="utf-8"):
    d = json.loads(l); per[d.pop("model")][d["id"]] = d
Tb, S = per["T"], per["S"]
Pb = {json.loads(l)["id"]: json.loads(l) for l in open(R03 + "/out-T/predictions-bluebird-v1.0-e2.jsonl", encoding="utf-8")}
def row_d(i, raw, hm):
    d = SC.score_row(rows[i], raw); d["_gold_ref"] = rows[i]["expect_refusal"]; d["_hit_max"] = hm; return d
if a.predict:
    R = json.load(open(a.predict)); sc = R["scenarios"][a.scenario]["bad"]
    Pa = {i: dict(p) for i, p in Pb.items()}
    for i, v in sc.items(): Pa[i].update(raw=v["raw"], hit_max=v["hit_max"], forced=v["forced"])
    Ta = {i: row_d(i, p["raw"], p.get("hit_max")) for i, p in Pa.items()}; kind = f"PREDICTION (not a model run): out-T with the {len(sc)} replayed rows of scenario {a.scenario!r} patched in"
else:
    Pa = {json.loads(l)["id"]: json.loads(l) for l in open(a.t_after, encoding="utf-8")}
    Ta = {}
    for l in open(a.after_per_row, encoding="utf-8"):
        d = json.loads(l)
        if d.pop("model") == "T": Ta[d["id"]] = d
    kind = "RESULT: score.py on out-T-jf (primary only), recomputed here with the same functions"
recheck = SC.decide(SC.model_metrics(rows, Tb, ci=False)["s"]["decision_counts"])
official = json.load(open(R03 + "/score/SCORES.json"))
assert [(b["id"], b["status"], b["value"]) for b in recheck["bars"]] == [(b["id"], b["status"], b["value"]) for b in official["bars"]] and recheck["verdict"] == official["verdict"], "recompute != official before"
Mb, Ma = SC.model_metrics(rows, Tb), SC.model_metrics(rows, Ta); Db, Da = SC.decide(Mb["s"]["decision_counts"]), SC.decide(Ma["s"]["decision_counts"])
if a.after_scores:
    off = json.load(open(a.after_scores))
    assert [(b["id"], b["status"], b["value"]) for b in Da["bars"]] == [(b["id"], b["status"], b["value"]) for b in off["bars"]] and Da["verdict"] == off["verdict"], "recompute != score-jf SCORES.json"
def paired(T):
    ids = sorted(i for i in T if rows[i]["kind"] == "test"); ans = [(T[i], S[i]) for i in ids if not T[i]["_gold_ref"]]
    b = sum(t["s_correct"] and not s["s_correct"] for t, s in ans); c = sum(s["s_correct"] and not t["s_correct"] for t, s in ans)
    dv = SC.mean(t["s_correct"] - s["s_correct"] for t, s in ans)
    return {"diff": SC.r4(dv), "ci": SC.boot(ans, lambda z: SC.mean(t["s_correct"] - s["s_correct"] for t, s in z)), "b_c": [b, c], "p": float(f"{st.mcnemar_two_sided(b, c):.3g}")}
pb, pa = paired(Tb), paired(Ta)
same = sum(Pa[i]["raw"] == Pb[i]["raw"] for i in Pb); changed = sorted(i for i in Pb if Pa[i]["raw"] != Pb[i]["raw"])
inv_b = sorted(i for i in Pb if parse_strict(Pb[i]["raw"])[1]); inv_a = sorted(i for i in Pa if parse_strict(Pa[i]["raw"])[1])
L = [f"# Bluebird T: before (out-T, 128, no constraint) vs after (out-T-jf, 256, json-slot)", "", f"**{kind}.**", "",
     "The owner-override T PASS (card t391s1356, OWNER-OVERRIDE-T-PASS.md) stands regardless of these numbers. The after figures are reported, not re-certified, unless Matt cards otherwise. The after run measures the model **plus** the constrained decoder.", "",
     "| Item | Before | After |", "|---|---|---|"]
bb = {b["id"]: b for b in Db["bars"]}; ba = {b["id"]: b for b in Da["bars"]}
for k in bb: L.append(f"| {k} | {bb[k]['value']} {bb[k]['status']} | {ba[k]['value']} {ba[k]['status']} |")
L += [f"| verdict (strict) | {Db['verdict']} | {Da['verdict']} |", f"| verdict reasons | {'; '.join(Db['verdict_reasons'])} | {'; '.join(Da['verdict_reasons'])} |",
      f"| T correct_all | {Mb['s']['correct_all']} {Mb['s']['correct_all_ci']} | {Ma['s']['correct_all']} {Ma['s']['correct_all_ci']} |",
      f"| T valid_json_schema (test) | {Mb['s']['valid_json_schema']} | {Ma['s']['valid_json_schema']} |",
      f"| T invalid reasons (test) | {Mb['invalid_reasons_test']} | {Ma['invalid_reasons_test']} |",
      f"| T hit_max (all 3,569 rows) | {Mb['hit_max_new_tokens']} | {Ma['hit_max_new_tokens']} |",
      f"| S correct_all (out-S-b4, unchanged) | {SC.model_metrics(rows, S, ci=False)['s']['correct_all']} | same rows, not rerun |",
      f"| T−S answer_value_match (paired, test) | {pb['diff']} {pb['ci']} b/c {pb['b_c']} p {pb['p']} | {pa['diff']} {pa['ci']} b/c {pa['b_c']} p {pa['p']} |",
      f"| memorisation test fires | {Db['memorisation_test']['fires']} | {Da['memorisation_test']['fires']} |", "",
      f"No-op check: {same} of {len(Pb)} raw outputs byte-identical to out-T; {len(changed)} changed. Strict-invalid before: {len(inv_b)}; after: {len(inv_a)}.",
      f"Changed rows: {changed}", f"Rows changed that were strict-valid before: {sorted(set(changed) - set(inv_b))}",
      f"Rows where the decoder overrode the model (forced > 0): {sorted(i for i, p in Pa.items() if p.get('forced'))}"]
open(a.out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
