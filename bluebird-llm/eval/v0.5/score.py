# Bluebird v1.0 eval scorer @0.2 (ORDER-bluebird-eval@0.2 §b, §f). Box, CPU, stdlib only. Deterministic (bootstrap seed 562).
# usage: score.py --rows eval_rows.jsonl --expect_score_manifest_sha <SCORE PIN> --expect_run_manifest_sha <RUN PIN> --expect_adapter_sha <sha> \
#                 --pred T=out-T/predictions-<tag>.jsonl [--pred S=out-S/predictions-<tag>.jsonl] --primary T [--baseline S] --out DIR
#                 [--accept_scorer_drift "<reason>"]
#        score.py ... --smoke --pred T=out-smoke-T/predictions-<tag>.jsonl --out DIR      (E3: format/runtime only, NEVER a verdict)
# @0.2 (review N1): two pins, decoupled from the whole-stage audit manifest EVAL-INPUTS.SHA256 (which no script reads):
#   SCORE PIN = sha256 of SCORE-INPUTS.SHA256 (score.py, evalcore.py, evalstats.py, rows): this scorer's self-check (exit 6).
#   RUN PIN   = sha256 of RUN-INPUTS.SHA256 (rows, fewshot, eval.py, evalcore.py) as used by eval.py at run time. Each run json records
#               that manifest's exact text (cfg.run_manifest_lines); a run is verified against what IT recorded, never against the
#               current stage, so changing score.py (or any non-run file) after E2 never makes a finished run unscorable.
#   Scorer drift: the run's evalcore.py (prompt rendering at run time) differs from the scorer's evalcore.py (parsing now). Refused with
#               15 unless --accept_scorer_drift "<reason>" is given; then scored and the drift + reason recorded in SCORES.json/REPORT.md.
# Refuses to score (non-zero exit, nothing scored) unless: score.py/evalcore.py/evalstats.py/rows match the score pin (exit 6);
# each prediction file's run json is complete, full (limit 0, all kinds), carries the run pin and the rows it is scored against, the expected
# adapter (primary) or no adapter + few-shot (baseline), and its EVAL.SHA256 + content hash verify (exit 15); and the prediction ids are
# EXACTLY the rows ids, each once, every line a valid record (exit 16). Review H1, M5, M6, L5, N1.
import argparse, collections, hashlib, json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from evalcore import (parse_strict, parse_lenient, is_refusal, norm, span_texts, render, digits_in_answer, denylist_hit, resolve, REFUSAL,
                      leak_hits, plan_batches, content_sha256, file_sha256 as sha, read_manifest)
import evalstats as st

# Decision parameters. All PROPOSED (Matt rules); each is a CLI flag. Calibration: sim/SIM-RESULTS.md.
PARAMS = {"test_floor_stated": 0.85,     # A-T: stated true accuracy (strict correct_all on the 2,090 test rows) the floor is built for
          "alpha_floor": 0.01,           # P(honest reader at the stated accuracy misses A-T) <= 0.01
          "alpha_probes_total": 0.04,    # split evenly (Bonferroni) over the 6 paired probe tests -> honest reader misses READS <= 0.05 overall
          "alpha_memo": 0.01, "memo_min_effect": 0.02,   # MEMORISES: old-value vs placebo, pooled cf+ar, exact one-sided McNemar + effect floor
          "margins": {"cf": 0.05, "ar": 0.05, "sh": 0.03, "rn": 0.03, "pp": 0.05, "pp_refusal": 0.05},
          "degenerate": {"refuse_answerable": 0.80, "ungrounded": 0.80, "overlong": 0.50, "extra_spans": 0.50, "reads_nothing_upper": 0.10, "min_nonref": 20}}
PROBE_TESTS = ("cf", "ar", "sh", "rn", "pp", "pp_refusal")
# @0.2 (review N6): the "honest reader misses READS <= 5%" figure holds only under these conditions; printed in every REPORT.md.
FA_CONDITIONS = [
    "The <= 5% false-alarm rate (an honest reader that reads the prompt is called something other than READS) assumes (1) its true strict "
    "accuracy on the 2,090 test rows is at least the stated 0.85, and (2) probe rows are as hard as their source rows (probe parity).",
    "Our simulation (sim/SIM-RESULTS.md, 4,000 reps): at 0.85, 3.45% (Wilson 95% 2.9-4.1%); at 0.83, 58.7% (the floor bar fails).",
    "Independent simulation (Kaylee, review evidence 40-ksim.md, 4,000 reps) at 0.85: independent rows 3.20% [2.70, 3.79]; probes correlated "
    "with their source rows (rho 0.7) 4.28% [3.69, 4.95]; heterogeneous by question type 3.87% [3.32, 4.52]; wrong answers = the training-mode "
    "value 2.95% [2.47, 3.52] (MEMORISES 0/4000); at 0.83, 57.95%.",
    "Probe parity broken (Kaylee 40-ksim.md): sh/pp probes 2 points harder than their sources -> 8.5% false alarms (8.53%); sh/pp/rn 4 points "
    "harder -> 35.9% (35.85%), INCONCLUSIVE in every such rep. A probe-bar FAIL is therefore evidence only if probe parity is credible.",
    "An INCONCLUSIVE whose only failing bar is A-T means: accuracy below the stated floor; no memorisation evidence. It is not a finding "
    "that the model ignores the prompt."]

def score_row(r, raw):
    o, err = parse_strict(raw); lo = o if o is not None else parse_lenient(raw)
    d = {"id": r["id"], "kind": r["kind"], "valid": o is not None, "invalid_reason": err}
    gl = [len(norm(v["text"])) for v in r["gold"]["spans"].values()]
    for tag, x in (("s", o), ("l", lo)):                     # s = strict (invalid counts wrong), l = lenient parse
        ref = is_refusal(x); gold_ref = r["expect_refusal"]
        val = (ref if gold_ref else (x is not None and not ref and span_texts(x) == span_texts(r["gold"])))
        d[f"{tag}_refusal"] = ref; d[f"{tag}_correct"] = bool(val)
        d[f"{tag}_exact"] = x == r["gold"]
        d[f"{tag}_rendered"] = (x is not None and render(x) == render(r["gold"]))
        sp = x.get("spans") if isinstance(x, dict) and isinstance(x.get("spans"), dict) else {}
        sv = [v for v in sp.values() if isinstance(v, dict)]
        alltext = "\n".join(u["text"] for u in r["units"])
        d[f"{tag}_grounded"] = bool(sv) and all(str(v.get("text", "")) and str(v.get("text")) in alltext for v in sv)
        d[f"{tag}_span_ok"] = bool(sv) and all((t := resolve(r["units"], v.get("anchor"))) is not None and str(v.get("text", "")) in t for v in sv)
        ga = sorted(v["anchor"] for v in r["gold"]["spans"].values()); pa = sorted(str(v.get("anchor")) for v in sv)
        d[f"{tag}_anchor_exact"] = (not gold_ref) and pa == ga
        d[f"{tag}_nspans"] = len(sv)
        d[f"{tag}_overlong"] = bool(sv) and bool(gl) and any(len(norm(v.get("text", ""))) > max(40, 3 * max(gl)) for v in sv)
        d[f"{tag}_extra_spans"] = bool(gl) and len(sv) > len(gl)
        if x is not None and isinstance(x.get("answer"), str):
            d[f"{tag}_v_digits"] = digits_in_answer(x); d[f"{tag}_v_deny"] = denylist_hit(x)
            d[f"{tag}_v_xsys"] = any(str(v.get("anchor", "")).split("-")[1:2] != [r["system_id"]] for v in sv)
            d[f"{tag}_v_verbatim"] = (not sv) or d[f"{tag}_span_ok"]
        stx = span_texts(x) if x else []
        if r["kind"] == "cf":
            d[f"{tag}_cf_new"] = stx == [norm(r["new_value"])]; d[f"{tag}_cf_old"] = norm(r["old_value"]) in stx
            d[f"{tag}_cf_placebo"] = None if r.get("placebo_value") is None else norm(r["placebo_value"]) in stx
        if r["kind"] == "ar":
            d[f"{tag}_ar_old"] = any(norm(v) in stx for v in r["old_value"])
            d[f"{tag}_ar_placebo"] = None if r.get("placebo_value") is None else any(norm(v) in stx for v in r["placebo_value"])
    if r["kind"] == "rn":
        d["leak_terms_hit"] = leak_hits(raw, r["leak_terms"]); d["s_rn_leak"] = d["l_rn_leak"] = bool(d["leak_terms_hit"])
    return d

def mean(xs): xs = list(xs); return sum(xs) / len(xs) if xs else None
def boot(rows, f, B=1000, seed=562):
    if not rows: return None
    rng = random.Random(seed); n = len(rows); v = []
    for _ in range(B):
        s = [rows[rng.randrange(n)] for _ in range(n)]; x = f(s)
        if x is not None: v.append(x)
    v.sort(); return [round(v[int(.025 * len(v))], 4), round(v[int(.975 * len(v)) - 1], 4)] if v else None
def prf(rows, tag):
    tp = sum(r[f"{tag}_refusal"] and r["_gold_ref"] for r in rows); fp = sum(r[f"{tag}_refusal"] and not r["_gold_ref"] for r in rows)
    fn = sum((not r[f"{tag}_refusal"]) and r["_gold_ref"] for r in rows)
    p = tp / (tp + fp) if tp + fp else None; rc = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * rc / (p + rc) if p and rc else (0.0 if p is not None and rc is not None else None)
    return p, rc, f1
def rate(rows, k): return mean(bool(r.get(k)) for r in rows)
def r4(x): return None if x is None else round(x, 4)

def decision_counts(rows_by_id, D, tag="s"):
    """Every count the bars and the verdict use (strict by default). Shared by score.py and sim/simulate.py."""
    test = [D[i] for i in D if rows_by_id[i]["kind"] == "test"]; ans = [d for d in test if not d["_gold_ref"]]
    nonref = [d for d in ans if not d[f"{tag}_refusal"]]
    C = {"n_test": len(test), "valid_test": sum(d["valid"] for d in test), "correct_test": sum(d[f"{tag}_correct"] for d in test),
         "n_ans": len(ans), "correct_ans": sum(d[f"{tag}_correct"] for d in ans), "refused_ans": sum(d[f"{tag}_refusal"] for d in ans),
         "n_nonref": len(nonref), "ungrounded": sum(not d[f"{tag}_grounded"] for d in nonref), "overlong": sum(d[f"{tag}_overlong"] for d in nonref),
         "extra_spans": sum(d[f"{tag}_extra_spans"] for d in nonref), "deny_hits": sum(bool(d.get(f"{tag}_v_deny")) for d in test), "pairs": {}, "memo": {}}
    for kind in ("cf", "ar", "sh", "rn", "pp"):
        pr = [D[i] for i in D if rows_by_id[i]["kind"] == kind]
        pairs = [(D.get(f"test:{rows_by_id[d['id']]['src']}"), d) for d in pr]
        if any(s is None for s, _ in pairs): pairs = []          # cannot happen after the completeness gate; no data -> FAIL
        good = f"{tag}_refusal" if kind == "ar" else f"{tag}_correct"
        C["pairs"][kind] = {"n": len(pairs), "b": sum(s[f"{tag}_correct"] and not d[good] for s, d in pairs),
                            "c": sum((not s[f"{tag}_correct"]) and d[good] for s, d in pairs),
                            "src_correct": sum(s[f"{tag}_correct"] for s, _ in pairs), "probe_correct": sum(d[good] for _, d in pairs)}
        if kind == "pp":
            pa = [(s, d) for s, d in pairs if not d["_gold_ref"]]
            C["pairs"]["pp_refusal"] = {"n": len(pa), "b": sum(d[f"{tag}_refusal"] and not s[f"{tag}_refusal"] for s, d in pa),
                                        "c": sum(s[f"{tag}_refusal"] and not d[f"{tag}_refusal"] for s, d in pa),
                                        "src_refused": sum(s[f"{tag}_refusal"] for s, _ in pa), "probe_refused": sum(d[f"{tag}_refusal"] for _, d in pa)}
        if kind == "rn": C["rn_leaks"] = sum(bool(d.get(f"{tag}_rn_leak")) for d in pr); C["n_rn"] = len(pr)
        if kind in ("cf", "ar"):
            mp = [d for d in pr if d.get(f"{tag}_{kind}_placebo") is not None]
            C["memo"][kind] = {"n": len(mp), "old": sum(bool(d[f"{tag}_{kind}_old"]) for d in mp), "placebo": sum(bool(d[f"{tag}_{kind}_placebo"]) for d in mp),
                               "b": sum(bool(d[f"{tag}_{kind}_old"]) and not d[f"{tag}_{kind}_placebo"] for d in mp),
                               "c": sum(bool(d[f"{tag}_{kind}_placebo"]) and not d[f"{tag}_{kind}_old"] for d in mp),
                               "old_all_rows": sum(bool(d.get(f"{tag}_{kind}_old")) for d in pr), "n_all_rows": len(pr)}
    return C

def decide(C, P=PARAMS):
    """Bars + verdict from decision_counts. Verdict precedence: MEMORISES > DEGENERATE > READS > INCONCLUSIVE."""
    bars = []
    def add(name, src, value, ok, thr, **kw): bars.append({"id": name.split(" ")[0], "bar": name, "source": src, "value": value, "threshold": thr, "status": "PASS" if ok else "FAIL", **kw})
    n = C["n_test"]
    add("G-F format: strict schema-valid JSON on test", "carried §f / brief (hard gate)", f"{C['valid_test']}/{n}", n > 0 and C["valid_test"] == n, "= all test rows")
    add("G-G guardrail: denylist hits on test", "carried §f (must be 0); promotion gate, not part of the verdict", C["deny_hits"], n > 0 and C["deny_hits"] == 0, "= 0")
    kmin = st.floor_kmin(n, P["test_floor_stated"], P["alpha_floor"]) if n else None
    lo, hi = st.wilson(C["correct_test"], n) if n else (None, None)
    add("A-T test accuracy floor (strict correct, all test rows)", "proposed (@0.1, ruling 1)", f"{C['correct_test']}/{n} = {r4(C['correct_test'] / n) if n else None}",
        n > 0 and C["correct_test"] >= kmin, f"Wilson95 LB >= {r4(st.wilson(kmin, n)[0]) if n else None} (count >= {kmin}); stated true accuracy {P['test_floor_stated']}, miss rate at stated <= {P['alpha_floor']}",
        wilson95=[r4(lo), r4(hi)])
    a_each = P["alpha_probes_total"] / len(PROBE_TESTS)
    names = {"cf": "P-CF counterfactual: new value vs same rows original", "ar": "P-AR anchor removal: refusal vs same rows answered",
             "sh": "P-SH clause shuffle: drop vs same rows", "rn": "P-RN supplier+brand rename: drop vs same rows", "pp": "P-PP paraphrase: drop vs same rows",
             "pp_refusal": "P-PP-REF paraphrase: extra refusal on answerable vs same rows"}
    for k in PROBE_TESTS:
        q = C["pairs"].get(k, {"n": 0, "b": 0, "c": 0}); m = P["margins"][k]
        if not q["n"]: add(names[k], "proposed", None, False, "no data", n=0); continue
        drop = (q["b"] - q["c"]) / q["n"]; p = st.mcnemar_one_sided(q["b"], q["c"]); fail = p < a_each and drop > m
        add(names[k], "proposed (@0.1: exact one-sided McNemar on discordant pairs)", r4(drop), not fail,
            f"FAIL iff p < {r4(a_each)} AND drop > {m}", n=q["n"], b=q["b"], c=q["c"], p_value=float(f"{p:.3g}"))
    add("P-RN-LEAK real supplier/brand name in output after rename", "proposed (case-insensitive, word-bounded)", C.get("rn_leaks"), C.get("n_rn", 0) > 0 and C.get("rn_leaks") == 0, "= 0")
    mb = sum(C["memo"].get(k, {}).get("b", 0) for k in ("cf", "ar")); mc = sum(C["memo"].get(k, {}).get("c", 0) for k in ("cf", "ar"))
    mn = sum(C["memo"].get(k, {}).get("n", 0) for k in ("cf", "ar"))
    mp_ = st.mcnemar_one_sided(mb, mc); eff = (mb - mc) / mn if mn else 0.0
    memo = {"n": mn, "b_old_not_placebo": mb, "c_placebo_not_old": mc, "effect": r4(eff), "p_value": float(f"{mp_:.3g}"),
            "fires": bool(mn) and mp_ < P["alpha_memo"] and eff >= P["memo_min_effect"],
            "rule": f"old value (cf: the replaced original; ar: the removed value) returned more often than a placebo value absent from the prompt: exact one-sided McNemar p < {P['alpha_memo']} AND effect >= {P['memo_min_effect']}",
            "by_kind": C["memo"]}
    G = P["degenerate"]; deg = []
    if not (n > 0 and C["valid_test"] == n): deg.append(f"format gate failed ({n - C['valid_test']} of {n} test outputs not strict-valid)")
    if C["n_ans"] and C["refused_ans"] / C["n_ans"] >= G["refuse_answerable"]: deg.append(f"refuses answerable rows ({C['refused_ans']}/{C['n_ans']})")
    if C["n_nonref"] >= G["min_nonref"]:
        if C["ungrounded"] / C["n_nonref"] >= G["ungrounded"]: deg.append(f"span text not in the prompt (format-only) ({C['ungrounded']}/{C['n_nonref']})")
        if C["overlong"] / C["n_nonref"] >= G["overlong"]: deg.append(f"copies whole clauses as spans ({C['overlong']}/{C['n_nonref']})")
        if C["extra_spans"] / C["n_nonref"] >= G["extra_spans"]: deg.append(f"enumerates extra spans (length-gaming) ({C['extra_spans']}/{C['n_nonref']})")
    if C["n_ans"] and st.wilson(C["correct_ans"], C["n_ans"])[1] < G["reads_nothing_upper"]: deg.append(f"answers almost nothing right ({C['correct_ans']}/{C['n_ans']} answerable)")
    reads_need = [b for b in bars if b["id"] != "G-G"]
    failed = [b["bar"] for b in reads_need if b["status"] != "PASS"]
    if memo["fires"]: v, why = "MEMORISES", [f"old value returned over placebo: {mb} vs {mc} discordant of {mn}, p={memo['p_value']}"]
    elif deg: v, why = "DEGENERATE", deg
    elif not failed: v, why = "READS", ["format gate, completeness, test floor and every probe bar pass"]
    else: v, why = "INCONCLUSIVE", failed
    note = None                                                      # N6: an A-T-only INCONCLUSIVE is reported as what it is
    if v == "INCONCLUSIVE" and [b["id"] for b in reads_need if b["status"] != "PASS"] == ["A-T"]:
        note = f"accuracy below the stated floor; no memorisation evidence (memo p={memo['p_value']})"
    return {"bars": bars, "memorisation_test": memo, "verdict": v, "verdict_reasons": why, "verdict_note": note,
            "promotable": v == "READS" and all(b["status"] == "PASS" for b in bars if b["id"] == "G-G"), "params": P}

def model_metrics(rows_by_id, D, ci=True):
    test = [D[i] for i in D if rows_by_id[i]["kind"] == "test"]; ans = [d for d in test if not d["_gold_ref"]]
    B = (lambda rows, f: boot(rows, f)) if ci else (lambda rows, f: None)
    M = {"n_test": len(test), "n_pred": len(D)}
    for tag in ("s", "l"):
        p, rc, f1 = prf(test, tag)
        M[tag] = {"valid_json_schema": r4(rate(test, "valid")), "correct_all": r4(rate(test, f"{tag}_correct")),
                  "correct_all_ci": B(test, lambda s: rate(s, f"{tag}_correct")),
                  "answer_value_match": r4(rate(ans, f"{tag}_correct")), "answer_value_match_ci": B(ans, lambda s: rate(s, f"{tag}_correct")),
                  "answer_exact_match_template_dependent": r4(rate(ans, f"{tag}_exact")), "rendered_match_template_dependent": r4(rate(ans, f"{tag}_rendered")),
                  "span_grounded": r4(rate(ans, f"{tag}_grounded")), "span_ok_anchor_resolves_and_contains_text": r4(rate(ans, f"{tag}_span_ok")),
                  "anchor_exact": r4(rate(ans, f"{tag}_anchor_exact")),
                  "refusal_precision": r4(p), "refusal_recall": r4(rc), "refusal_f1": r4(f1), "refusal_f1_ci": B(test, lambda s: prf(s, tag)[2]),
                  "validator": {k: r4(rate(test, f"{tag}_v_{k}")) for k in ("digits", "xsys", "deny")} | {"verbatim_pass": r4(rate(ans, f"{tag}_v_verbatim"))},
                  "guardrail_denylist_hits": sum(bool(d.get(f"{tag}_v_deny")) for d in test)}
        br = {}
        for dim in ("qt_group", "answer_type", "manufacturer", "truncated", "anchor_position"):
            g = collections.defaultdict(list)
            for d in test: g[str(rows_by_id[d["id"]][dim])].append(d)
            br[dim] = {k: {"n": len(v), "correct": r4(rate(v, f"{tag}_correct")), "valid": r4(rate(v, "valid"))} for k, v in sorted(g.items())}
        M[tag]["breakdown"] = br
        C = decision_counts(rows_by_id, D, tag); Pr = {}
        for kind in ("cf", "ar", "sh", "rn", "pp"):
            pr = [D[i] for i in D if rows_by_id[i]["kind"] == kind]; q = C["pairs"][kind]
            good = f"{tag}_refusal" if kind == "ar" else f"{tag}_correct"
            pairs = [(D[f"test:{rows_by_id[d['id']]['src']}"], d) for d in pr]
            sc = [d for s, d in pairs if s[f"{tag}_correct"]]
            e = {"n": len(pr), "valid": r4(rate(pr, "valid")), "correct": r4(rate(pr, good)), "src_correct_same_rows": r4(q["src_correct"] / q["n"]) if q["n"] else None,
                 "drop_vs_src": r4((q["b"] - q["c"]) / q["n"]) if q["n"] else None, "discordant_b_c": [q["b"], q["c"]],
                 "correct_given_src_correct": r4(rate(sc, good)), "n_src_correct": len(sc),
                 "anchor_exact": r4(rate(pr, f"{tag}_anchor_exact")), "refused": r4(rate(pr, f"{tag}_refusal"))}
            if kind == "cf": e.update(new_value=r4(rate(pr, f"{tag}_cf_new")), old_value=r4(rate(pr, f"{tag}_cf_old")),
                                      placebo_value=r4(mean(bool(d[f"{tag}_cf_placebo"]) for d in pr if d[f"{tag}_cf_placebo"] is not None)),
                                      old_value_given_src_correct=r4(rate(sc, f"{tag}_cf_old")))
            if kind == "ar": e.update(refusal=r4(rate(pr, f"{tag}_refusal")), old_value_hallucinated=r4(rate(pr, f"{tag}_ar_old")),
                                      placebo_value=r4(mean(bool(d[f"{tag}_ar_placebo"]) for d in pr if d[f"{tag}_ar_placebo"] is not None)),
                                      old_value_given_src_correct=r4(rate(sc, f"{tag}_ar_old")))
            if kind == "rn": e.update(name_leak=C["rn_leaks"], leak_terms_seen=sorted({t for d in pr for t in d.get("leak_terms_hit", [])}))
            if kind == "pp": e.update(over_refusal_on_answerable=r4(mean(d[f"{tag}_refusal"] for d in pr if not d["_gold_ref"])))
            Pr[kind] = e
        M[tag]["probes"] = Pr; M[tag]["decision_counts"] = C
    M["hit_max_new_tokens"] = sum(bool(d.get("_hit_max")) for d in D.values())
    M["invalid_reasons_test"] = dict(collections.Counter(d["invalid_reason"] for d in test if d["invalid_reason"]))
    return M

class Refuse(Exception):
    def __init__(self, code, why): super().__init__(why); self.code = code

def load_predictions(path, rows, full=True, planned=None):
    """Exact id-set equality with the rows (or the smoke plan), no duplicates, every line a valid record (H1, M5)."""
    want = set(planned) if planned is not None else set(rows)
    if not os.path.exists(path): raise Refuse(16, f"{path}: missing")
    preds = {}; n = 0
    for n, l in enumerate(open(path, encoding="utf-8"), 1):
        try:
            p = json.loads(l); assert isinstance(p, dict) and isinstance(p.get("id"), str) and isinstance(p.get("raw"), str)
        except Exception: raise Refuse(16, f"{path}: line {n} is not a valid prediction record")
        if p["id"] in preds: raise Refuse(16, f"{path}: duplicate id {p['id']}")
        if p["id"] not in want: raise Refuse(16, f"{path}: id not in {'rows' if planned is None else 'the smoke plan'}: {p['id']}")
        preds[p["id"]] = p
    miss = want - set(preds)
    if miss:
        by = collections.Counter(rows[i]["kind"] for i in miss)
        raise Refuse(16, f"{path}: {len(miss)} of {len(want)} ids have no prediction (by kind {dict(by)}); refusing to score partial predictions")
    return preds

def parse_manifest_text(t):
    out = {}
    for ln in t.splitlines():
        if ln.strip():
            h, f = ln.split(None, 1); out[f.strip().lstrip("*")] = h
    return out

def check_run(path, preds, rows_sha, rows_name, run_pin, scorer, role, expect_adapter, allow_stub, smoke=False, accept_drift=None):
    """Provenance of one prediction file from its run json + EVAL.SHA256 (H1, M6), verified against what the run recorded (N1).
    scorer = {file: sha} of this scorer's evalcore.py. Returns (run json, drift list)."""
    d = os.path.dirname(os.path.abspath(path)); base = os.path.basename(path)
    if not (base.startswith("predictions-") and base.endswith(".jsonl")): raise Refuse(15, f"{path}: not a predictions-<tag>.jsonl file")
    tag = base[len("predictions-"):-len(".jsonl")]; rp = os.path.join(d, f"run-{tag}.json"); mf = os.path.join(d, "EVAL.SHA256")
    if not os.path.exists(rp): raise Refuse(15, f"{path}: no run json {rp}")
    R = json.load(open(rp)); c = R.get("cfg", {}); bad = []; drift = []
    if R.get("status") != "complete" or R.get("complete") is not True: bad.append("run not complete")
    if smoke: (c.get("limit", 0) > 0) or bad.append("not a smoke run (limit 0)")
    else:
        if c.get("limit") != 0: bad.append(f"limit={c.get('limit')} (smoke run)")
        if c.get("kinds") != "": bad.append(f"kinds={c.get('kinds')!r} (subset run)")
    lines = c.get("run_manifest_lines")
    if not isinstance(lines, str): bad.append("run json records no run manifest (pre-@0.2 run)"); RM = {}
    else:
        RM = parse_manifest_text(lines)
        if hashlib.sha256(lines.encode("utf-8")).hexdigest() != c.get("manifest_sha256"): bad.append("recorded run manifest text != recorded manifest sha256")
    if c.get("manifest_sha256") != run_pin: bad.append("run manifest sha256 differs from --expect_run_manifest_sha")
    ins = c.get("inputs_sha256", {})
    need = ["eval.py", "evalcore.py", rows_name] + (["fewshot.json"] if role == "baseline" else [])
    for f in need:
        if ins.get(f) is None or ins.get(f) != RM.get(f): bad.append(f"{f} sha256 the run used != the run manifest it recorded")
    if c.get("rows_sha256") != rows_sha or ins.get(rows_name) != rows_sha: bad.append("rows sha256 the run used differs from --rows")
    for f, h in scorer.items():                                      # N1: scorer drift is explicit, never silent
        if ins.get(f) is not None and ins.get(f) != h:
            drift.append({"file": f, "run": ins.get(f), "scorer": h})
    if drift and not accept_drift:
        bad.append(f"scorer drift: {[x['file'] for x in drift]} differ between the run and this scorer; rescore with the matching scorer, "
                   f"or pass --accept_scorer_drift \"<reason>\" (recorded in SCORES.json and REPORT.md)")
    if c.get("backend") != "hf" and not allow_stub: bad.append(f"backend={c.get('backend')} (not a model run)")
    if role == "primary":
        if c.get("mode") != "zero": bad.append("primary must be zero-shot")
        if c.get("adapter_manifest_sha256") != expect_adapter: bad.append("adapter manifest sha256 != --expect_adapter_sha")
    if role == "baseline":
        if c.get("mode") != "fewshot": bad.append("baseline must be few-shot")
        if c.get("adapter_manifest_sha256") is not None or c.get("adapter_path") is not None: bad.append("baseline has an adapter")
    if not os.path.exists(mf): bad.append("no EVAL.SHA256")
    else:
        L = read_manifest(mf)
        for f in (base, os.path.basename(rp)):
            if f not in L: bad.append(f"EVAL.SHA256 does not list {f}")
        for f, h in L.items():
            if not os.path.exists(os.path.join(d, f)) or sha(os.path.join(d, f)) != h: bad.append(f"EVAL.SHA256 mismatch: {f}")
    if R.get("content_sha256") != content_sha256(preds.values()): bad.append("content sha256 != run json")
    if bad: raise Refuse(15, f"{path}: provenance: {bad}")
    return R, drift

def self_check(a):
    """SCORE PIN (N1): SCORE-INPUTS.SHA256 lists score.py, evalcore.py, evalstats.py and the rows; all four must match (exit 6)."""
    mp = a.score_manifest or os.path.join(os.path.dirname(os.path.abspath(a.rows)), "SCORE-INPUTS.SHA256")
    if not os.path.exists(mp): raise Refuse(6, f"missing score manifest {mp}")
    msha = sha(mp)
    if msha != a.expect_score_manifest_sha: raise Refuse(6, f"score manifest sha256 {msha} != --expect_score_manifest_sha")
    M = read_manifest(mp)
    for p in (os.path.join(HERE, "score.py"), os.path.join(HERE, "evalcore.py"), os.path.join(HERE, "evalstats.py"), a.rows):
        if M.get(os.path.basename(p)) != sha(p): raise Refuse(6, f"{os.path.basename(p)} sha256 != score manifest")
    scorer = {"score_manifest_sha256": msha, "files_sha256": {f: M[f] for f in ("score.py", "evalcore.py", "evalstats.py")}}
    return M, scorer

def smoke(a, rows, M, scorer):
    tag, path = a.pred[0].split("=", 1)
    R = json.load(open(os.path.join(os.path.dirname(os.path.abspath(path)), f"run-{os.path.basename(path)[12:-6]}.json"))) if os.path.exists(path) else {}
    c = R.get("cfg", {})
    plan = [r["id"] for b in plan_batches(list(rows.values()), c.get("mode", "zero"), c.get("batch", 8), c.get("kinds", ""), c.get("limit", 0)) for r in b]
    preds = load_predictions(path, rows, planned=plan)
    check_run(path, preds, M[os.path.basename(a.rows)], os.path.basename(a.rows), a.expect_run_manifest_sha, {"evalcore.py": scorer["files_sha256"]["evalcore.py"]},
              "smoke", None, a.allow_stub, smoke=True, accept_drift=a.accept_scorer_drift)
    D = {i: score_row(rows[i], p["raw"]) for i, p in preds.items()}
    ses = R["sessions"]; last = ses[-1]; tdir = os.path.dirname(os.path.abspath(path))
    aborts = sorted(f for f in os.listdir(tdir) if f.startswith("ABORT-"))
    secs = [p.get("sec") for p in preds.values() if isinstance(p.get("sec"), (int, float))]
    valid = mean(d["valid"] for d in D.values()); hm = mean(bool(p.get("hit_max")) for p in preds.values())
    greedy = all(s.get("logits_processors") == [] and s.get("merged_generation_config") is not None for s in ses) if c.get("backend") == "hf" else None
    crit = {"status complete, exit 0": R.get("status") == "complete", "no ABORT-n.json in out dir": not aborts,
            "merged generation config read and greedy (every session)": greedy,
            f"hit_max <= {a.smoke_hit_max} (primary only)": (hm <= a.smoke_hit_max) if a.smoke_role == "primary" else "report only",
            f"strict-valid >= {a.smoke_valid} (primary only)": (valid >= a.smoke_valid) if a.smoke_role == "primary" else "report only"}
    S = {"NO_VERDICT": "smoke rows only; score.py never issues a verdict on a smoke run", "rows": len(preds), "batches": R.get("planned_batches"),
         "strict_valid": r4(valid), "hit_max_rate": r4(hm), "refused": r4(mean(d["s_refusal"] for d in D.values())),
         "sec_per_row_mean": r4(mean(secs)), "projected_hours_3569_rows": r4(mean(secs) * 3569 / 3600) if secs else None,
         "peak_alloc_bytes": last.get("peak_alloc_bytes"), "gpu_free_at_start": last.get("gpu_free_at_start"), "replay_b1": last.get("replay_b1"),
         "versions": last.get("versions"), "merged_generation_config": last.get("merged_generation_config"), "logits_processors": last.get("logits_processors"),
         "invalid_reasons": dict(collections.Counter(d["invalid_reason"] for d in D.values() if d["invalid_reason"])), "E3_acceptance_proposed": crit,
         "E3_pass": all(v is True or v == "report only" for v in crit.values() if v is not None) and (greedy is not False)}
    os.makedirs(a.out, exist_ok=True); json.dump(S, open(os.path.join(a.out, f"SMOKE-{tag}.json"), "w"), indent=1, sort_keys=True); print(json.dumps(S, indent=1))
    return 0

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("--rows", required=True); a.add_argument("--pred", action="append", required=True)
    a.add_argument("--expect_score_manifest_sha", required=True, help="SCORE PIN: sha256 of SCORE-INPUTS.SHA256 (N1)")
    a.add_argument("--score_manifest", default=None, help="default: SCORE-INPUTS.SHA256 next to --rows")
    a.add_argument("--expect_run_manifest_sha", required=True, help="RUN PIN: sha256 of RUN-INPUTS.SHA256 the runs used, from the order (N1)")
    a.add_argument("--accept_scorer_drift", default=None, metavar="REASON", help="score despite evalcore.py differing between run and scorer; recorded")
    a.add_argument("--expect_adapter_sha", default=None, help="ADAPTER.SHA256 sha256 the primary run must carry")
    a.add_argument("--primary", default=None); a.add_argument("--baseline", default=None); a.add_argument("--out", required=True)
    a.add_argument("--smoke", action="store_true"); a.add_argument("--smoke_role", default="primary"); a.add_argument("--smoke_hit_max", type=float, default=0.02)
    a.add_argument("--smoke_valid", type=float, default=0.90)
    a.add_argument("--allow_stub", action="store_true", help="tests only: accept stub-backend runs")
    a.add_argument("--params", default=None, help="JSON overriding PARAMS keys (Matt's rulings)")
    a.add_argument("--no_ci", action="store_true")
    a = a.parse_args(argv)
    P = json.loads(json.dumps(PARAMS))
    if a.params:
        for k, v in json.loads(a.params).items(): P[k] = {**P[k], **v} if isinstance(P.get(k), dict) else v
    try:
        M, scorer = self_check(a)
        rows = {r["id"]: r for r in (json.loads(l) for l in open(a.rows, encoding="utf-8"))}
        if a.smoke: return smoke(a, rows, M, scorer)
        if not a.primary or not a.expect_adapter_sha: raise Refuse(2, "--primary and --expect_adapter_sha are required")
        res = {}; per = {}; runs = {}; drifts = {}
        for spec in a.pred:
            tag, path = spec.split("=", 1)
            preds = load_predictions(path, rows)
            runs[tag], dr = check_run(path, preds, M[os.path.basename(a.rows)], os.path.basename(a.rows), a.expect_run_manifest_sha,
                                      {"evalcore.py": scorer["files_sha256"]["evalcore.py"]},
                                      "primary" if tag == a.primary else ("baseline" if tag == a.baseline else "other"),
                                      a.expect_adapter_sha, a.allow_stub, accept_drift=a.accept_scorer_drift)
            if dr: drifts[tag] = dr
            D = {}
            for i, p in preds.items():
                d = score_row(rows[i], p["raw"]); d["_gold_ref"] = rows[i]["expect_refusal"]; d["_hit_max"] = p.get("hit_max"); D[i] = d
            per[tag] = D; res[tag] = model_metrics(rows, D, ci=not a.no_ci)
    except Refuse as e:
        print(f"SCORE_REFUSED exit {e.code}: {e}", file=sys.stderr, flush=True); return e.code
    os.makedirs(a.out, exist_ok=True)
    dec = decide(res[a.primary]["s"]["decision_counts"], P)
    scorer_block = {**scorer, "run_manifest_sha256": a.expect_run_manifest_sha, "drift": drifts,
                    "accepted_drift_reason": a.accept_scorer_drift if drifts else None}
    out = {"models": res, **dec, "scorer": scorer_block,
           "inputs": {"run_manifest_sha256": a.expect_run_manifest_sha, "score_manifest_sha256": scorer["score_manifest_sha256"],
                      "runs": {t: {"cfg": R["cfg"], "content_sha256": R["content_sha256"]} for t, R in runs.items()}}}
    if a.baseline:
        T, S = per[a.primary], per[a.baseline]; ids = sorted(i for i in T if rows[i]["kind"] == "test")
        pairs = [(T[i], S[i]) for i in ids]; ans = [(t, s) for t, s in pairs if not t["_gold_ref"]]
        out["t_vs_s"] = {"n_paired": len(pairs)}
        for tag in ("s", "l"):
            b = sum(t[f"{tag}_correct"] and not s[f"{tag}_correct"] for t, s in ans); c = sum(s[f"{tag}_correct"] and not t[f"{tag}_correct"] for t, s in ans)
            dv = mean(t[f"{tag}_correct"] - s[f"{tag}_correct"] for t, s in ans)
            out["t_vs_s"][tag] = {"answer_value_match_diff": r4(dv), "answer_value_match_diff_ci": None if a.no_ci else boot(ans, lambda z: mean(t[f"{tag}_correct"] - s[f"{tag}_correct"] for t, s in z)),
                                  "mcnemar_exact_two_sided_p": float(f"{st.mcnemar_two_sided(b, c):.3g}"), "discordant_T_only_S_only": [b, c],
                                  "refusal_f1_diff_ci": None if a.no_ci else boot(pairs, lambda z: (lambda x, y: None if x is None or y is None else x - y)(prf([t for t, _ in z], tag)[2], prf([s for _, s in z], tag)[2]))}
    json.dump(out, open(os.path.join(a.out, "SCORES.json"), "w"), indent=1, sort_keys=True)
    with open(os.path.join(a.out, "per_row.jsonl"), "w") as f:
        for tag, D in per.items():
            for d in D.values(): f.write(json.dumps({"model": tag, **d}, sort_keys=True) + "\n")
    L = ["# Bluebird v1.0 eval report (@0.2)", "", f"Verdict ({a.primary}, strict): **{out['verdict']}**", ""] + [f"- {x}" for x in out["verdict_reasons"]]
    if out.get("verdict_note"): L += ["", f"**{out['verdict_note']}**"]
    L += ["", "## Conditions of the false-alarm figure", ""] + [f"- {x}" for x in FA_CONDITIONS]
    L += ["", "## Scorer provenance", "", f"- score manifest sha256 (SCORE PIN): {scorer['score_manifest_sha256']}",
          f"- run manifest sha256 (RUN PIN, as recorded by every run): {a.expect_run_manifest_sha}",
          "- scorer files: " + ", ".join(f"{k} {v}" for k, v in scorer["files_sha256"].items()),
          ("- scorer drift ACCEPTED: " + json.dumps(drifts, sort_keys=True) + f"; reason: {a.accept_scorer_drift}") if drifts else "- scorer drift: none"]
    L += ["", f"Promotable (READS and G-G pass): {out['promotable']}", "", "| Bar | Source | Value | Threshold | Status | n / b / c / p |", "|---|---|---|---|---|---|"]
    L += [f"| {b['bar']} | {b['source']} | {b['value']} | {b['threshold']} | {b['status']} | {b.get('n', '')} / {b.get('b', '')} / {b.get('c', '')} / {b.get('p_value', '')} |" for b in out["bars"]]
    L += ["", "Memorisation test (MEMORISES iff it fires): " + json.dumps({k: v for k, v in out["memorisation_test"].items() if k != "by_kind"})]
    for tag, Mx in res.items():
        s = Mx["s"]; L += ["", f"## {tag} (strict)", "", "| Metric | Value | 95% CI |", "|---|---|---|"]
        for k in ("valid_json_schema", "correct_all", "answer_value_match", "answer_exact_match_template_dependent", "rendered_match_template_dependent", "span_grounded",
                  "span_ok_anchor_resolves_and_contains_text", "anchor_exact", "refusal_precision", "refusal_recall", "refusal_f1"):
            L.append(f"| {k} | {s[k]} | {s.get(k + '_ci', '')} |")
        L += ["", "Exact match and rendered match depend on the answer template; family B never shares a template with training, so they are ~0 by construction and not comparable across families (review I5).",
              "", "| Probe | n | correct | drop vs src | correct given src correct | extra |", "|---|---|---|---|---|---|"]
        for k, e in s["probes"].items():
            ex = {x: e[x] for x in ("new_value", "old_value", "placebo_value", "old_value_given_src_correct", "refusal", "old_value_hallucinated", "name_leak", "over_refusal_on_answerable", "anchor_exact") if x in e}
            L.append(f"| {k} | {e['n']} | {e['correct']} | {e['drop_vs_src']} | {e['correct_given_src_correct']} | {json.dumps(ex)} |")
    if a.baseline: L += ["", "## T vs S (test, paired)", "", "```", json.dumps(out["t_vs_s"], indent=1), "```"]
    open(os.path.join(a.out, "REPORT.md"), "w").write("\n".join(L) + "\n")
    print(json.dumps({"verdict": out["verdict"], "reasons": out["verdict_reasons"], "bars": [(b["bar"], b["status"]) for b in out["bars"]]}, indent=1))
    return 0
if __name__ == "__main__": sys.exit(main())
