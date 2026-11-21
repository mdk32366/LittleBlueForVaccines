# Box CPU tests for the Bluebird v1.0 eval @0.3 (code under test = @0.2, byte-identical). Run (review venv: torch CPU, transformers 5.23.0, peft, tokenizers, jinja2):
#   LBE_REBUILD=1 /workspace/littleblue-fullrun-review/venv/bin/python -m unittest -v tests.test_eval
# Classes: Parse, Stats, Bars (in-process verdict logic), EndToEnd + ScoreGate (eval.py stub -> score.py CLI), Guards (eval.py out-dir state,
# integrity, resume), Shim (eval.py GPU branch on CPU via tests/shim_eval.py: exits 3/4/5/9/10/11/13, decoding config, resume), Build (probe rows).
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, time, unittest, collections, concurrent.futures as cf
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, H); sys.path.insert(0, os.path.join(H, "tests"))
from evalcore import parse_strict, parse_lenient, is_refusal, denylist_hit, digits_in_answer, norm, span_texts, resolve, leak_hits, plan_batches, content_sha256
import evalstats as st, probecheck as pc, score, stubs
ROWS = os.path.join(H, "eval_rows.jsonl"); MAN = os.path.join(H, "RUN-INPUTS.SHA256"); SMAN = os.path.join(H, "SCORE-INPUTS.SHA256"); PY = sys.executable
FX = os.path.join(H, "tests", "fixtures"); AD = os.path.join(FX, "adapter", "final-adapter")
SHIM_PY = os.environ.get("LBE_SHIM_PY", "/workspace/littleblue-fullrun-review/venv/bin/python")
GEN = os.environ.get("GEN_OUT", "/workspace/littleblue-v02g/repo/gen/out")
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def pin(): return sha(MAN)                       # RUN PIN (@0.2 N1)
def spin(): return sha(SMAN)                     # SCORE PIN
ADSHA = sha(os.path.join(FX, "adapter", "ADAPTER.SHA256"))
def dirhash(d): return {f: sha(os.path.join(d, f)) for f in sorted(os.listdir(d))}
def run_eval(out, mode="gold", tag="T", extra=(), rows=ROWS, adapter=AD, h=H, pin_=None):
    cmd = [PY, os.path.join(h, "eval.py"), "--rows", rows, "--expect_manifest_sha", pin_ or sha(os.path.join(os.path.dirname(rows), "RUN-INPUTS.SHA256")),
           "--out_dir", out, "--tag", tag, "--backend", f"stub:{mode}"] + (["--adapter", adapter] if adapter else []) + list(extra)
    return subprocess.run(cmd, capture_output=True, text=True)
def run_score(out, preds, primary="T", baseline=None, extra=(), h=H, rows=ROWS, adsha=None, run_pin=None, score_pin=None):
    d = os.path.dirname(rows)
    cmd = [PY, os.path.join(h, "score.py"), "--rows", rows, "--expect_score_manifest_sha", score_pin or sha(os.path.join(d, "SCORE-INPUTS.SHA256")),
           "--expect_run_manifest_sha", run_pin or sha(os.path.join(d, "RUN-INPUTS.SHA256")),
           "--expect_adapter_sha", adsha or ADSHA, "--primary", primary, "--out", out, "--allow_stub", "--no_ci"] + sum((["--pred", p] for p in preds), []) + list(extra)
    if baseline: cmd += ["--baseline", baseline]
    return subprocess.run(cmd, capture_output=True, text=True)
def aborts(d): return sorted(f for f in os.listdir(d) if f.startswith("ABORT-"))
# @0.2 (review N7): a copied stage is an ALLOW-LIST of the files the scripts need (never runs/, outputs or anything else in the stage)
STAGE_FILES = ("eval.py", "evalcore.py", "score.py", "evalstats.py", "probecheck.py", "mkmanifest.py", "build_eval_rows.py", "eval_rows.jsonl", "fewshot.json",
               "RUN-INPUTS.SHA256", "SCORE-INPUTS.SHA256", "EVAL-INPUTS.SHA256", "KINDS.SHA256")
def copy_stage():
    t = tempfile.mkdtemp(); c = os.path.join(t, "c"); os.makedirs(c)
    for f in STAGE_FILES: shutil.copy2(os.path.join(H, f), c)
    return c
class Cache:
    d = {}
    @classmethod
    def get(cls, mode):
        if mode not in cls.d:
            t = tempfile.mkdtemp(prefix=f"lbe-{mode}-"); r = run_eval(t, mode); assert r.returncode == 0, r.stdout + r.stderr
            s = run_score(os.path.join(t, "score"), [f"T={t}/predictions-T.jsonl"]); assert s.returncode == 0, s.stderr
            cls.d[mode] = (t, json.load(open(os.path.join(t, "score", "SCORES.json"))))
        return cls.d[mode]
ALL_ROWS = [json.loads(l) for l in open(ROWS)]; RB = {r["id"]: r for r in ALL_ROWS}
# @0.2 (review N7): the suite never writes inside the stage. Snapshot every stage file (bar __pycache__) at import; tearDownModule fails the run
# if anything was added, removed or changed (shows as an ERROR "tearDownModule").
def stage_snapshot():
    return {os.path.relpath(os.path.join(d, f), H): sha(os.path.join(d, f)) for d, ds, fs in os.walk(H) if "__pycache__" not in d.split(os.sep) for f in fs}
STAGE0 = stage_snapshot()
def tearDownModule():
    now = stage_snapshot(); diff = sorted(k for k in set(STAGE0) | set(now) if STAGE0.get(k) != now.get(k))
    if diff: raise AssertionError(f"the suite wrote inside the stage: {diff[:10]}")

class Parse(unittest.TestCase):
    def test_strict_accepts_gold_and_refusal(self):
        self.assertIsNotNone(parse_strict('{"answer": "Lapse: {S1}.", "spans": {"S1": {"anchor": "D#2", "text": "31 May 2026"}}}')[0])
        self.assertIsNotNone(parse_strict('{"answer": "not in the contracts", "spans": {}}')[0])
    def test_strict_rejects(self):
        for raw, why in [('{"answer": "Lapse: {S1}."', "not_json"), ('{"answer": "x", "spans": {}, "extra": 1}', "bad_keys"), ('[1]', "bad_keys"),
                         ('{"answer": 3, "spans": {}}', "bad_types"), ('{"answer": "a", "spans": []}', "bad_types"),
                         ('{"answer": "Lapse: {S1}.", "spans": {}}', "slot_mismatch"), ('{"answer": "a {S1}", "spans": {"S1": {"anchor": "D#2"}}}', "bad_span_obj"),
                         ('{"answer": "a {X1}", "spans": {"X1": {"anchor": "D#2", "text": "t"}}}', "bad_span_key"),
                         ('{"answer": "a {S1}", "spans": {"S1": {"anchor": 2, "text": "t"}}}', "bad_span_types"),
                         ('{"answer": "a {S1}", "spans": {"S1": {"anchor": "D#2", "text": 7}}}', "bad_span_types"),
                         ('{"answer": "not in the contracts", "spans": {"S1": {"anchor": "D#2", "text": "x"}}}', "refusal_with_spans"),
                         ('<|im_start|>{"answer": "not in the contracts", "spans": {}}', "not_json"),
                         ('```json\n{"answer": "not in the contracts", "spans": {}}\n```', "not_json")]:
            self.assertEqual(parse_strict(raw)[1], why, raw)
    def test_lenient_recovers_fenced_and_prose(self):
        self.assertTrue(is_refusal(parse_lenient('Sure!\n```json\n{"answer": "not in the contracts", "spans": {}}\n```')))
        self.assertEqual(parse_lenient('x {"a": {"b": 1}} y')["a"], {"b": 1}); self.assertIsNone(parse_lenient("no json here {"))
    def test_is_refusal_tolerance(self):
        for a in ("not in the contracts", "Not in the contracts.", "  NOT IN THE CONTRACTS  "): self.assertTrue(is_refusal({"answer": a, "spans": {}}), a)
        for a in ("not in contracts", "it is not in the contracts"): self.assertFalse(is_refusal({"answer": a, "spans": {}}), a)
    def test_norm_and_span_texts(self):
        self.assertEqual(norm("1,000 doses."), "1000 doses"); self.assertEqual(norm("  A\u2019b  "), "a'b"); self.assertNotEqual(norm("1,00"), "100")
        self.assertEqual(span_texts({"spans": {"S1": {"text": "2,500"}, "S2": {"text": "Tdap"}}}), ["2500", "tdap"])
    def test_validator_rules(self):
        self.assertTrue(digits_in_answer({"answer": "expires in 2027", "spans": {}}))
        self.assertFalse(digits_in_answer({"answer": "Lapse: {S1}.", "spans": {}}))
        self.assertTrue(denylist_hit({"answer": "You should push for a higher tier.", "spans": {}}))
        self.assertTrue(denylist_hit({"answer": "We recommend you seek larger rebates.", "spans": {}}))          # plural commercial term
        self.assertFalse(denylist_hit({"answer": "Band rebate: {S1}.", "spans": {"S1": {"anchor": "D#4", "text": "2.5 per cent"}}}))
    def test_resolve_whole_leaf(self):
        U = [{"id": "SYN-X-P1#*", "text": "proposal"}, {"id": "SYN-X-MSA1#2", "text": "c2"}]
        self.assertEqual(resolve(U, "SYN-X-P1#3"), "proposal"); self.assertEqual(resolve(U, "SYN-X-MSA1#2"), "c2"); self.assertIsNone(resolve(U, "SYN-X-MSA1#3"))
    def test_leak_hits(self):
        T = ["GSK PHARM", "GSK", "BEXSERO", "M-M-R-II"]
        self.assertEqual(leak_hits("by Gsk Pharm and bexsero", T), ["BEXSERO", "GSK", "GSK PHARM"]); self.assertEqual(leak_hits("GSKX BEXSEROS", T), [])
        self.assertEqual(leak_hits("m-m-r-ii", T), ["M-M-R-II"])

class Stats(unittest.TestCase):
    def test_wilson_known(self):
        lo, hi = st.wilson(5, 10); self.assertAlmostEqual(lo, 0.2366, 4); self.assertAlmostEqual(hi, 0.7634, 4)
        self.assertEqual(st.wilson(0, 10)[0], 0.0); self.assertAlmostEqual(st.wilson(0, 10)[1], 0.2775, 4); self.assertEqual(st.wilson(0, 0), (None, None))
    def test_binomial_and_mcnemar_exact(self):
        import math
        self.assertAlmostEqual(st.binom_cdf(3, 10, .5), sum(math.comb(10, i) for i in range(4)) / 1024, 12)
        self.assertAlmostEqual(st.binom_cdf(5, 20, .3), sum(math.comb(20, i) * .3 ** i * .7 ** (20 - i) for i in range(6)), 10)
        self.assertEqual(st.mcnemar_one_sided(9, 1), 11 / 1024); self.assertEqual(st.mcnemar_one_sided(0, 0), 1.0)
        self.assertEqual(st.mcnemar_two_sided(0, 6), 2 / 64); self.assertEqual(st.binom_sf_half(0, 5), 1.0); self.assertEqual(st.binom_sf_half(6, 5), 0.0)
    def test_floor_kmin_is_calibrated(self):
        for n, p, a in ((2090, .85, .01), (300, .9, .05), (50, .5, .1)):
            k = st.floor_kmin(n, p, a); self.assertLessEqual(st.binom_cdf(k - 1, n, p), a); self.assertGreater(st.binom_cdf(k, n, p), a)

def build_D(fn_by_id):
    D = {}
    for i, r in RB.items():
        d = score.score_row(r, fn_by_id(r)); d["_gold_ref"] = r["expect_refusal"]; D[i] = d
    return D
class Bars(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.G = build_D(stubs.gold); cls.FO = build_D(stubs.format_only); cls.REF = build_D(stubs.refuse); cls.MEM = build_D(stubs.mem)
        cls.src = {r["src"] for r in ALL_ROWS if r["kind"] != "test"}
    def dec(self, D): return score.decide(score.decision_counts(RB, D))
    def bar(self, R, i): return [b for b in R["bars"] if b["id"] == i][0]
    def flip(self, ids, V=None):
        D = dict(self.G)
        for i in ids: D[i] = (V or self.FO)[i]
        return D
    def test_gold_reads_every_bar_passes(self):
        R = self.dec(self.G); self.assertEqual(R["verdict"], "READS"); self.assertTrue(all(b["status"] == "PASS" for b in R["bars"])); self.assertTrue(R["promotable"])
        self.assertEqual(len(R["bars"]), 10)
    def test_gf_boundary_one_invalid_is_degenerate(self):
        i = next(r["id"] for r in ALL_ROWS if r["kind"] == "test"); D = dict(self.G); D[i] = score.score_row(RB[i], '{"answer": "x'); D[i]["_gold_ref"] = RB[i]["expect_refusal"]
        R = self.dec(D); self.assertEqual(self.bar(R, "G-F")["status"], "FAIL"); self.assertEqual(R["verdict"], "DEGENERATE")
    def test_gg_one_hit_fails_gate_not_verdict(self):
        r = next(r for r in ALL_ROWS if r["kind"] == "test" and not r["expect_refusal"] and len(r["gold"]["spans"]) == 1 and r["id"].split(":")[1] not in self.src)
        g = json.loads(json.dumps(r["gold"])); g["answer"] = "You should push for a lower price. " + g["answer"]
        D = dict(self.G); D[r["id"]] = score.score_row(r, json.dumps(g)); D[r["id"]]["_gold_ref"] = False
        R = self.dec(D); self.assertEqual(self.bar(R, "G-G")["status"], "FAIL"); self.assertEqual(R["verdict"], "READS"); self.assertFalse(R["promotable"])
    def test_at_only_inconclusive_wording(self):                                  # @0.2 (N6)
        n = 2090; k = st.floor_kmin(n, score.PARAMS["test_floor_stated"], score.PARAMS["alpha_floor"])
        free = [r["id"] for r in ALL_ROWS if r["kind"] == "test" and r["src"] not in self.src]
        R = self.dec(self.flip(free[:n - k + 1])); self.assertEqual(R["verdict"], "INCONCLUSIVE")
        self.assertEqual([b["id"] for b in R["bars"] if b["status"] != "PASS" and b["id"] != "G-G"], ["A-T"])
        self.assertEqual(R["verdict_note"], f"accuracy below the stated floor; no memorisation evidence (memo p={R['memorisation_test']['p_value']})")
        self.assertIsNone(self.dec(self.G)["verdict_note"])
        R2 = self.dec(self.flip(free[:n - k + 1] + [r["id"] for r in ALL_ROWS if r["kind"] == "sh"]))       # a probe bar fails too: no note
        self.assertEqual(R2["verdict"], "INCONCLUSIVE"); self.assertIsNone(R2["verdict_note"])
    def test_floor_boundary_exact(self):
        n = 2090; k = st.floor_kmin(n, score.PARAMS["test_floor_stated"], score.PARAMS["alpha_floor"])
        free = [r["id"] for r in ALL_ROWS if r["kind"] == "test" and r["src"] not in self.src]
        R = self.dec(self.flip(free[:n - k])); self.assertEqual(self.bar(R, "A-T")["status"], "PASS"); self.assertEqual(R["verdict"], "READS")
        R = self.dec(self.flip(free[:n - k + 1])); self.assertEqual(self.bar(R, "A-T")["status"], "FAIL"); self.assertEqual(R["verdict"], "INCONCLUSIVE")
    def test_each_probe_drop_bar_fails_alone(self):
        for kind, bid in (("cf", "P-CF"), ("ar", "P-AR"), ("sh", "P-SH"), ("rn", "P-RN"), ("pp", "P-PP")):
            ids = [r["id"] for r in ALL_ROWS if r["kind"] == kind and not (kind == "pp" and r["expect_refusal"])][:40]
            R = self.dec(self.flip(ids)); bad = sorted(b["id"] for b in R["bars"] if b["status"] != "PASS")
            self.assertEqual(R["verdict"], "INCONCLUSIVE", kind); self.assertIn(bid, bad, kind)
            self.assertTrue(set(bad) <= {bid, "P-PP-REF"}, (kind, bad))
            ids5 = ids[:5] if kind in ("sh", "rn") else ids[:10]                     # below the margin: point drop <= margin -> PASS
            R = self.dec(self.flip(ids5)); self.assertEqual(self.bar(R, bid)["status"], "PASS", kind)
    def test_pp_extra_refusal_bar(self):
        ids = [r["id"] for r in ALL_ROWS if r["kind"] == "pp" and not r["expect_refusal"]][:40]
        R = self.dec(self.flip(ids, self.REF)); self.assertEqual(self.bar(R, "P-PP-REF")["status"], "FAIL"); self.assertEqual(R["verdict"], "INCONCLUSIVE")
        R = self.dec(self.flip(ids, self.FO)); self.assertEqual(self.bar(R, "P-PP-REF")["status"], "PASS")
    def test_rn_leak_one_row(self):
        r = next(r for r in ALL_ROWS if r["kind"] == "rn" and r["gold"]["spans"]); D = dict(self.G)
        D[r["id"]] = score.score_row(r, stubs.leaker(r)); D[r["id"]]["_gold_ref"] = r["expect_refusal"]
        R = self.dec(D); self.assertEqual(self.bar(R, "P-RN-LEAK")["status"], "FAIL"); self.assertEqual(R["verdict"], "INCONCLUSIVE")
    def test_memorises_needs_old_over_placebo(self):
        cf = [r for r in ALL_ROWS if r["kind"] == "cf" and r.get("placebo_value") and norm(r["placebo_value"]) != norm(r["old_value"])]
        R = self.dec(self.flip([r["id"] for r in cf[:30]], self.MEM)); self.assertEqual(R["verdict"], "MEMORISES")
        D = dict(self.G)
        for k, r in enumerate(cf[:40]):
            g = json.loads(json.dumps(r["gold"])); next(iter(g["spans"].values()))["text"] = r["old_value"] if k % 2 else r["placebo_value"]
            D[r["id"]] = score.score_row(r, json.dumps(g)); D[r["id"]]["_gold_ref"] = False
        R = self.dec(D); self.assertNotEqual(R["verdict"], "MEMORISES"); m = R["memorisation_test"]
        self.assertEqual((m["b_old_not_placebo"], m["c_placebo_not_old"]), (20, 20)); self.assertFalse(m["fires"])
    def test_degenerate_detectors(self):
        for fn, why in ((stubs.refuse, "refuses answerable"), (stubs.format_only, "format-only"), (stubs.copy_anchor, "copies whole clauses"),
                        (stubs.length_gamer, "length-gaming")):
            R = self.dec(build_D(fn)); self.assertEqual(R["verdict"], "DEGENERATE", why); self.assertTrue(any(why in x for x in R["verdict_reasons"]), (why, R["verdict_reasons"]))
        def wrong_word(r):                                    # valid, grounded, short, one span per gold span, but the wrong word: reads nothing
            if r["expect_refusal"]: return stubs.gold(r)
            words = [w.strip(".,;:*|()") for w in r["units"][0]["text"].split()]; gt = {norm(v["text"]) for v in r["gold"]["spans"].values()}
            w = next(x for x in words if x and norm(x) not in gt and not any(norm(x) in g for g in gt))
            return json.dumps({"answer": r["gold"]["answer"], "spans": {k: {"anchor": r["units"][0]["id"], "text": w} for k in r["gold"]["spans"]}})
        R = self.dec(build_D(wrong_word)); self.assertEqual(R["verdict"], "DEGENERATE"); self.assertEqual(len(R["verdict_reasons"]), 1, R["verdict_reasons"])
        self.assertIn("answers almost nothing right", R["verdict_reasons"][0])
    def test_missing_kind_is_fail_not_pass(self):
        D = {i: d for i, d in self.G.items() if RB[i]["kind"] != "sh"}; R = self.dec(D)
        self.assertEqual(self.bar(R, "P-SH")["status"], "FAIL"); self.assertNotEqual(R["verdict"], "READS")
        D = {i: d for i, d in self.G.items() if RB[i]["kind"] != "rn"}; R = self.dec(D); self.assertEqual(self.bar(R, "P-RN-LEAK")["status"], "FAIL")
    def test_honest_45_not_memorises(self):
        R = self.dec(build_D(stubs.honest(0.45))); self.assertEqual(R["verdict"], "INCONCLUSIVE"); self.assertFalse(R["memorisation_test"]["fires"])
        self.assertEqual(self.bar(R, "G-G")["status"], "PASS"); self.assertFalse(R["promotable"])              # promotable needs READS, not just G-G
    def test_every_review_stub_lands_on_expected_outcome(self):
        o = os.path.join(tempfile.mkdtemp(), "STUB-OUTCOMES.json")                 # @0.2 (N7): never into the stage
        r = subprocess.run([PY, os.path.join(H, "sim", "stub_harness.py"), o], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(all(x["match"] for x in json.load(open(o))))
    def test_honest_false_alarm_small_sim(self):
        t = tempfile.mkdtemp(); r = subprocess.run([PY, os.path.join(H, "sim", "simulate.py"), "200", os.path.join(t, "S")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); S = json.load(open(os.path.join(t, "S.json")))
        for name, v in S.items():
            n = v["reps"]; fr = lambda k: v["verdicts"].get(k, 0) / n
            if name.startswith("honest") and float(name.split("=")[1]) >= 0.85: self.assertLessEqual(1 - fr("READS"), 0.09, name)   # 0.05 target + MC slack at 200 reps
            if name.startswith(("honest", "null")): self.assertEqual(fr("MEMORISES"), 0.0, name)
            if "memorises 10%" in name: self.assertGreaterEqual(fr("MEMORISES"), 0.95, name)
            if "sh 0.85" in name: self.assertGreaterEqual(1 - fr("READS"), 0.8, name)

class EndToEnd(unittest.TestCase):
    def test_gold_reads(self):
        _, S = Cache.get("gold"); m = S["models"]["T"]["s"]
        self.assertEqual(m["valid_json_schema"], 1.0); self.assertEqual(m["correct_all"], 1.0); self.assertEqual(m["span_ok_anchor_resolves_and_contains_text"], 1.0)
        self.assertEqual(m["anchor_exact"], 1.0); self.assertEqual(m["refusal_f1"], 1.0); self.assertEqual(m["validator"]["xsys"], 0.0)
        self.assertTrue(all(b["status"] == "PASS" for b in S["bars"]), S["bars"]); self.assertEqual(S["verdict"], "READS")
    def test_invalid_is_degenerate(self):
        _, S = Cache.get("invalid"); self.assertEqual(S["models"]["T"]["s"]["valid_json_schema"], 0.0); self.assertEqual(S["verdict"], "DEGENERATE")
        self.assertEqual([b["status"] for b in S["bars"] if b["id"] == "G-F"], ["FAIL"])
    def test_wrong_span(self):
        _, S = Cache.get("wrongspan"); m = S["models"]["T"]["s"]
        self.assertEqual(m["answer_value_match"], 0.0); self.assertEqual(m["span_ok_anchor_resolves_and_contains_text"], 0.0); self.assertEqual(m["span_grounded"], 0.0)
        self.assertEqual(m["refusal_recall"], 1.0); self.assertEqual(S["verdict"], "DEGENERATE")
    def test_old_value_on_counterfactual_memorises(self):
        _, S = Cache.get("oldvalue"); cf = S["models"]["T"]["s"]["probes"]["cf"]
        self.assertEqual(cf["old_value"], 1.0); self.assertEqual(cf["new_value"], 0.0); self.assertEqual(S["verdict"], "MEMORISES")
        self.assertEqual(S["models"]["T"]["s"]["correct_all"], 1.0); self.assertTrue(S["memorisation_test"]["fires"])
    def test_non_refusal_on_anchor_removal_memorises(self):
        _, S = Cache.get("norefuse"); ar = S["models"]["T"]["s"]["probes"]["ar"]
        self.assertEqual(ar["refusal"], 0.0); self.assertEqual(ar["old_value_hallucinated"], 1.0); self.assertEqual(S["verdict"], "MEMORISES")
        self.assertEqual([b["status"] for b in S["bars"] if b["id"] == "P-AR"], ["FAIL"])
    def test_t_vs_s_paired(self):
        tg, _ = Cache.get("gold"); s = tempfile.mkdtemp()
        r = run_eval(s, "invalid", tag="S", adapter=None, extra=["--mode", "fewshot", "--fewshot", os.path.join(H, "fewshot.json")]); self.assertEqual(r.returncode, 0, r.stdout)
        r = run_score(os.path.join(s, "score"), [f"T={tg}/predictions-T.jsonl", f"S={s}/predictions-S.jsonl"], "T", "S"); self.assertEqual(r.returncode, 0, r.stderr)
        S = json.load(open(os.path.join(s, "score", "SCORES.json")))
        self.assertEqual(S["t_vs_s"]["s"]["answer_value_match_diff"], 1.0); self.assertLess(S["t_vs_s"]["s"]["mcnemar_exact_two_sided_p"], 1e-10)
        r = run_score(os.path.join(s, "score2"), [f"T={tg}/predictions-T.jsonl", f"S={tg}/predictions-T.jsonl"], "T", "S"); self.assertEqual(r.returncode, 15)  # baseline with adapter
    def test_report_written(self):
        t, _ = Cache.get("gold"); L = open(os.path.join(t, "score", "REPORT.md")).read()
        self.assertIn("Verdict (T, strict): **READS**", L); self.assertIn("template", L)

class ScoreGate(unittest.TestCase):
    """H1, M5, M6, L5: score.py refuses partial / duplicate / foreign / unprovenanced predictions."""
    def fresh(self):
        t = tempfile.mkdtemp(); g, _ = Cache.get("gold"); o = os.path.join(t, "o"); shutil.copytree(g, o, ignore=shutil.ignore_patterns("score")); return o
    def sc(self, o, **k): return run_score(os.path.join(o, "..", "sc"), [f"T={o}/predictions-T.jsonl"], **k)
    def edit(self, o, fn):
        p = os.path.join(o, "predictions-T.jsonl"); L = open(p).read().splitlines(True); open(p, "w").writelines(fn(L))
    def test_partial_refused(self):
        o = self.fresh(); self.edit(o, lambda L: L[:64]); self.assertEqual(self.sc(o).returncode, 16)
    def test_missing_probe_kind_refused(self):
        o = self.fresh(); self.edit(o, lambda L: [l for l in L if not json.loads(l)["id"].startswith(("sh:", "rn:", "pp:"))]); r = self.sc(o)
        self.assertEqual(r.returncode, 16); self.assertIn("900 of 3569", r.stderr)
    def test_duplicate_refused(self):
        o = self.fresh(); self.edit(o, lambda L: L + L[:1]); self.assertEqual(self.sc(o).returncode, 16)
    def test_garbage_and_foreign_lines_refused(self):
        o = self.fresh(); self.edit(o, lambda L: L[:-1] + ["not json\n"]); self.assertEqual(self.sc(o).returncode, 16)
        o = self.fresh(); self.edit(o, lambda L: L[:-1] + ['{"id": "test:NOPE", "raw": "x"}\n']); self.assertEqual(self.sc(o).returncode, 16)
        o = self.fresh(); self.edit(o, lambda L: L + ['{"id": "test:NOPE", "raw": "x"}\n']); r = self.sc(o); self.assertEqual(r.returncode, 16); self.assertIn("id not in rows", r.stderr)
    def test_tampered_prediction_refused_by_provenance(self):
        o = self.fresh(); self.edit(o, lambda L: [L[0].replace('"raw": "', '"raw": "x', 1)] + L[1:]); r = self.sc(o)
        self.assertEqual(r.returncode, 15); self.assertIn("EVAL.SHA256 mismatch", r.stderr)
        p = os.path.join(o, "predictions-T.jsonl"); open(os.path.join(o, "EVAL.SHA256"), "w").write("".join(f"{sha(os.path.join(o, f))}  {f}\n" for f in ("predictions-T.jsonl", "run-T.json")))
        r = self.sc(o); self.assertEqual(r.returncode, 15); self.assertIn("content sha256", r.stderr)
    def test_run_json_gates(self):
        for key, val, msg in (("status", "running", "not complete"), ("cfg.limit", 64, "limit=64"), ("cfg.kinds", "test", "kinds="), ("cfg.backend", "stub:gold", None),
                              ("cfg.adapter_manifest_sha256", "0" * 64, "adapter manifest"), ("cfg.mode", "fewshot", "zero-shot"), ("cfg.rows_sha256", "0" * 64, "rows sha256")):
            o = self.fresh(); rp = os.path.join(o, "run-T.json"); R = json.load(open(rp)); tgt = R
            ks = key.split(".")
            for k in ks[:-1]: tgt = tgt[k]
            tgt[ks[-1]] = val; json.dump(R, open(rp, "w"))
            open(os.path.join(o, "EVAL.SHA256"), "w").write("".join(f"{sha(os.path.join(o, f))}  {f}\n" for f in ("predictions-T.jsonl", "run-T.json")))
            r = run_score(os.path.join(o, "..", "sc"), [f"T={o}/predictions-T.jsonl"]) if key != "cfg.backend" else None
            if key == "cfg.backend":
                r = subprocess.run([PY, os.path.join(H, "score.py"), "--rows", ROWS, "--expect_score_manifest_sha", spin(), "--expect_run_manifest_sha", pin(), "--expect_adapter_sha", ADSHA, "--primary", "T",
                                    "--out", os.path.join(o, "..", "sc"), "--pred", f"T={o}/predictions-T.jsonl"], capture_output=True, text=True); msg = "not a model run"
            self.assertEqual(r.returncode, 15, key); self.assertIn(msg, r.stderr, key)
        o = self.fresh(); os.remove(os.path.join(o, "run-T.json")); self.assertEqual(self.sc(o).returncode, 15)
        o = self.fresh(); self.assertEqual(self.sc(o, adsha="1" * 64).returncode, 15)
    def test_self_check_pin_and_tamper(self):
        g, _ = Cache.get("gold")
        r = subprocess.run([PY, os.path.join(H, "score.py"), "--rows", ROWS, "--expect_score_manifest_sha", "0" * 64, "--expect_run_manifest_sha", pin(), "--expect_adapter_sha", ADSHA, "--primary", "T",
                            "--out", tempfile.mkdtemp(), "--allow_stub", "--pred", f"T={g}/predictions-T.jsonl"], capture_output=True, text=True); self.assertEqual(r.returncode, 6)
        for f in ("score.py", "evalcore.py", "evalstats.py"):
            c = copy_stage(); t = os.path.dirname(c)
            open(os.path.join(c, f), "a").write("\n# tamper\n")
            r = run_score(os.path.join(t, "sc"), [f"T={g}/predictions-T.jsonl"], h=c, rows=os.path.join(c, "eval_rows.jsonl")); self.assertEqual(r.returncode, 6, f)
    def test_rows_sha_vs_run_json(self):
        g, _ = Cache.get("gold"); preds = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(g, "predictions-T.jsonl"))}
        M = {l.split()[1]: l.split()[0] for l in open(MAN)}; sc = {"evalcore.py": M["evalcore.py"]}
        score.check_run(os.path.join(g, "predictions-T.jsonl"), preds, M["eval_rows.jsonl"], "eval_rows.jsonl", pin(), sc, "primary", ADSHA, True)
        with self.assertRaises(score.Refuse) as e: score.check_run(os.path.join(g, "predictions-T.jsonl"), preds, "f" * 64, "eval_rows.jsonl", pin(), sc, "primary", ADSHA, True)
        self.assertEqual(e.exception.code, 15)
    def test_smoke_scoring_never_a_verdict(self):
        t = tempfile.mkdtemp(); self.assertEqual(run_eval(t, "gold", extra=["--limit", "64"]).returncode, 0)
        r = subprocess.run([PY, os.path.join(H, "score.py"), "--rows", ROWS, "--expect_score_manifest_sha", spin(), "--expect_run_manifest_sha", pin(), "--smoke", "--allow_stub", "--out", os.path.join(t, "sm"),
                            "--pred", f"T={t}/predictions-T.jsonl"], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr)
        S = json.load(open(os.path.join(t, "sm", "SMOKE-T.json"))); self.assertIn("NO_VERDICT", S); self.assertEqual(S["rows"], 64); self.assertNotIn("verdict", S)
        self.assertEqual(self.sc_full(t).returncode, 16)
        g, _ = Cache.get("gold")                                                                     # smoke scorer refuses a full run
        r = subprocess.run([PY, os.path.join(H, "score.py"), "--rows", ROWS, "--expect_score_manifest_sha", spin(), "--expect_run_manifest_sha", pin(), "--smoke", "--allow_stub", "--out", os.path.join(t, "sm2"),
                            "--pred", f"T={g}/predictions-T.jsonl"], capture_output=True, text=True); self.assertEqual(r.returncode, 15, r.stderr); self.assertIn("not a smoke run", r.stderr)
    def sc_full(self, t): return run_score(os.path.join(t, "sc"), [f"T={t}/predictions-T.jsonl"])

class Provenance(unittest.TestCase):
    """@0.2 (review N1): scoring verifies each run against the run manifest IT recorded; the score pin covers only the scorer's own files.
    Each test fails under @0.1 (one whole-stage pin in both eval.py and score.py; evidence 32-score-manifest-coupling.txt)."""
    def stage_with(self, edit=None):
        c = copy_stage()
        if edit: open(os.path.join(c, edit), "a").write("\n# later edit after E2\n")
        subprocess.run([PY, os.path.join(c, "mkmanifest.py")], capture_output=True, check=True); return c
    def score_in(self, c, **k):
        g, _ = Cache.get("gold"); out = os.path.join(os.path.dirname(c), "sc")
        return run_score(out, [f"T={g}/predictions-T.jsonl"], h=c, rows=os.path.join(c, "eval_rows.jsonl"), **k), out
    def test_unrelated_stage_change_after_run_still_scores(self):
        c = self.stage_with("probecheck.py"); self.assertNotEqual(sha(os.path.join(c, "EVAL-INPUTS.SHA256")), sha(os.path.join(H, "EVAL-INPUTS.SHA256")))
        r, out = self.score_in(c, run_pin=pin(), score_pin=spin()); self.assertEqual(r.returncode, 0, r.stderr)
    def test_score_py_fix_after_run_scores_with_new_score_pin_and_records_it(self):
        c = self.stage_with("score.py"); new = sha(os.path.join(c, "SCORE-INPUTS.SHA256")); self.assertNotEqual(new, spin())
        self.assertEqual(sha(os.path.join(c, "RUN-INPUTS.SHA256")), pin())                     # run pin untouched by a scorer edit
        r, out = self.score_in(c, run_pin=pin(), score_pin=new); self.assertEqual(r.returncode, 0, r.stderr)
        S = json.load(open(os.path.join(out, "SCORES.json")))["scorer"]
        self.assertEqual(S["score_manifest_sha256"], new); self.assertEqual(S["files_sha256"]["score.py"], sha(os.path.join(c, "score.py")))
        self.assertEqual(S["run_manifest_sha256"], pin()); self.assertEqual(S["drift"], {})
        self.assertIn(new, open(os.path.join(out, "REPORT.md")).read())
        r, _ = self.score_in(c, run_pin=pin(), score_pin=spin()); self.assertEqual(r.returncode, 6, r.stderr)   # the old score pin no longer matches
    def test_evalcore_change_is_explicit_drift_never_silent(self):
        c = self.stage_with("evalcore.py")
        r, _ = self.score_in(c, run_pin=pin()); self.assertEqual(r.returncode, 15); self.assertIn("scorer drift", r.stderr); self.assertIn("evalcore.py", r.stderr)
        r, out = self.score_in(c, run_pin=pin(), extra=["--accept_scorer_drift", "comment-only edit, parse unchanged"]); self.assertEqual(r.returncode, 0, r.stderr)
        S = json.load(open(os.path.join(out, "SCORES.json")))["scorer"]
        self.assertEqual([d["file"] for d in S["drift"]["T"]], ["evalcore.py"]); self.assertEqual(S["accepted_drift_reason"], "comment-only edit, parse unchanged")
        self.assertEqual(S["drift"]["T"][0]["run"], sha(os.path.join(H, "evalcore.py"))); self.assertIn("scorer drift ACCEPTED", open(os.path.join(out, "REPORT.md")).read())
    def test_wrong_run_pin_or_tampered_recorded_manifest_refused_15(self):
        r, _ = self.score_in(self.stage_with(), run_pin="0" * 64); self.assertEqual(r.returncode, 15); self.assertIn("--expect_run_manifest_sha", r.stderr)
        g, _ = Cache.get("gold")
        def variant(fn):
            o = os.path.join(tempfile.mkdtemp(), "o"); shutil.copytree(g, o, ignore=shutil.ignore_patterns("score")); rp = os.path.join(o, "run-T.json")
            R = json.load(open(rp)); fn(R["cfg"]); json.dump(R, open(rp, "w"))
            open(os.path.join(o, "EVAL.SHA256"), "w").write("".join(f"{sha(os.path.join(o, f))}  {f}\n" for f in ("predictions-T.jsonl", "run-T.json")))
            return run_score(os.path.join(o, "..", "sc"), [f"T={o}/predictions-T.jsonl"])
        bad_ec = "f" * 64
        r = variant(lambda c: c.update(run_manifest_lines=c["run_manifest_lines"].replace(c["inputs_sha256"]["evalcore.py"], bad_ec)))
        self.assertEqual(r.returncode, 15); self.assertIn("recorded run manifest text", r.stderr)
        def both(c):                                        # self-consistent forgery: lines + sha rewritten, but then it is not the pinned run manifest
            c["run_manifest_lines"] = c["run_manifest_lines"].replace(c["inputs_sha256"]["eval.py"], bad_ec); c["manifest_sha256"] = hashlib.sha256(c["run_manifest_lines"].encode()).hexdigest()
        r = variant(both); self.assertEqual(r.returncode, 15); self.assertIn("--expect_run_manifest_sha", r.stderr); self.assertIn("eval.py sha256 the run used", r.stderr)
        r = variant(lambda c: c.pop("run_manifest_lines")); self.assertEqual(r.returncode, 15); self.assertIn("pre-@0.2", r.stderr)
        r = variant(lambda c: c["inputs_sha256"].update({"eval.py": bad_ec})); self.assertEqual(r.returncode, 15); self.assertIn("eval.py sha256 the run used", r.stderr)
    def test_report_states_false_alarm_conditions(self):                      # @0.2 (N6)
        _, S = Cache.get("gold"); g, _ = Cache.get("gold"); R = open(os.path.join(g, "score", "REPORT.md")).read()
        for x in ("Conditions of the false-alarm figure", "at least the stated 0.85", "probe parity", "8.5%", "35.9%", "3.45%", "3.20%", "4.28%", "3.87%", "2.95%",
                  "accuracy below the stated floor; no memorisation evidence"):
            self.assertIn(x, R, x)

# @0.3 (Kaylee RECHECK-eval@0.2 N8, from her evidence-eval@0.2/extra02.py KayleeM28): the pre-lock "predictions without a run json" refusal
# (mutant M28) is observable. Without it, take_lock() runs first on an orphan dir: a torn lock is emptied, a fresh torn lock costs a 5 s wait,
# a stale lock gets a new inode/mtime, and a read-only dir crashes with exit 11. The original refuses with 7 before touching anything.
class KayleeM28(unittest.TestCase):
    def _orphan(self):
        t = tempfile.mkdtemp(prefix="k28-"); open(os.path.join(t, "predictions-T.jsonl"), "w").write('{"id": "x"}\n'); return t
    def test_orphan_with_torn_lock_refused_7_lock_bytes_untouched(self):
        t = self._orphan(); p = os.path.join(t, "eval.lock"); open(p, "wb").write(b'{"pid": 12'); os.utime(p, (1, 1)); before = dirhash(t)
        r = run_eval(t); self.assertEqual(r.returncode, 7, r.stdout + r.stderr); self.assertEqual(dirhash(t), before)
        self.assertEqual(open(p, "rb").read(), b'{"pid": 12'); self.assertIn("predictions without a run json", r.stdout)
    def test_orphan_with_fresh_torn_lock_refused_at_once(self):
        t = self._orphan(); p = os.path.join(t, "eval.lock"); open(p, "wb").write(b'{"pid": 12'); t0 = time.time()
        r = run_eval(t); self.assertEqual(r.returncode, 7, r.stdout + r.stderr); self.assertLess(time.time() - t0, 4.0)   # M28: 5 s torn-lock wait
        self.assertEqual(open(p, "rb").read(), b'{"pid": 12')
    def test_orphan_with_stale_lock_same_inode_and_mtime(self):
        t = self._orphan(); p = os.path.join(t, "eval.lock"); dp = subprocess.Popen([PY, "-c", "pass"]); dp.wait()
        open(p, "w").write(json.dumps({"pid": dp.pid, "started": "x", "tag": "T"})); os.utime(p, (1, 1)); st = os.stat(p); before = dirhash(t)
        r = run_eval(t); self.assertEqual(r.returncode, 7, r.stdout + r.stderr); self.assertEqual(dirhash(t), before)
        st2 = os.stat(p); self.assertEqual((st2.st_ino, st2.st_mtime_ns), (st.st_ino, st.st_mtime_ns))
    def test_orphan_in_readonly_out_dir_refused_7(self):
        if os.getuid() == 0: self.skipTest("root ignores directory modes")
        t = self._orphan(); os.chmod(t, 0o555)
        try: r = run_eval(t)
        finally: os.chmod(t, 0o755)
        self.assertEqual(r.returncode, 7, r.stdout + r.stderr); self.assertNotIn("unhandled", r.stdout + r.stderr)   # M28: exit 11 PermissionError
        self.assertEqual(sorted(os.listdir(t)), ["predictions-T.jsonl"])

class Guards(unittest.TestCase):
    """eval.py out-dir state machine, integrity, resume (H4, M1-M4, L4, L5, L8) on the stub backend; same code path as the GPU branch."""
    def copy_h(self): return copy_stage()
    def test_bad_pin_exit_6_then_clean_start_and_numbered_aborts(self):
        t = os.path.join(tempfile.mkdtemp(), "o")
        r = run_eval(t, pin_="0" * 64); self.assertEqual(r.returncode, 6); self.assertEqual(aborts(t), ["ABORT-1.json"]); a1 = sha(os.path.join(t, "ABORT-1.json"))
        self.assertEqual(json.load(open(os.path.join(t, "ABORT-1.json")))["exit"], 6)
        r = run_eval(t, pin_="1" * 64); self.assertEqual(r.returncode, 6); self.assertEqual(aborts(t), ["ABORT-1.json", "ABORT-2.json"])
        self.assertEqual(sha(os.path.join(t, "ABORT-1.json")), a1)                                   # never overwritten
        r = run_eval(t); self.assertEqual(r.returncode, 0, r.stdout)                                   # early abort does not poison the dir (H4)
        self.assertEqual(sha(os.path.join(t, "ABORT-1.json")), a1); self.assertEqual(json.load(open(os.path.join(t, "run-T.json")))["status"], "complete")
        L = open(os.path.join(t, "EVAL.SHA256")).read().split()                                         # EVAL.SHA256 covers the markers too
        self.assertIn("ABORT-1.json", L); self.assertIn("ABORT-2.json", L)
    def test_tampered_inputs_exit_6(self):
        for f in ("eval_rows.jsonl", "eval.py", "evalcore.py", "fewshot.json"):
            c = self.copy_h(); p = os.path.join(c, f)
            open(p, "a").write("\n" if f.endswith("l") or f.endswith(".json") else "# x\n")
            ex = ["--mode", "fewshot", "--fewshot", os.path.join(c, "fewshot.json")] if f == "fewshot.json" else []
            r = run_eval(os.path.join(c, "o"), rows=os.path.join(c, "eval_rows.jsonl"), h=c, extra=ex, adapter=None if ex else AD); self.assertEqual(r.returncode, 6, f + r.stdout)
            self.assertIn(f, json.load(open(os.path.join(c, "o", "ABORT-1.json")))["abort"])
        t = tempfile.mkdtemp(); ad = os.path.join(t, "adapter"); shutil.copytree(os.path.join(FX, "adapter"), ad)
        open(os.path.join(ad, "final-adapter", "adapter_config.json"), "a").write(" ")
        r = run_eval(os.path.join(t, "o"), adapter=os.path.join(ad, "final-adapter")); self.assertEqual(r.returncode, 6)
    def test_completed_dir_refused_nothing_written(self):
        t = os.path.join(tempfile.mkdtemp(), "o"); self.assertEqual(run_eval(t, extra=["--limit", "24"]).returncode, 0); before = dirhash(t)
        for ex in (["--limit", "24"], ["--limit", "24", "--batch", "4"], ["--mode", "fewshot"]):
            r = run_eval(t, extra=ex); self.assertEqual(r.returncode, 7, ex); self.assertEqual(dirhash(t), before, ex)
    def partial(self, extra=()):
        t = os.path.join(tempfile.mkdtemp(), "o"); self.assertEqual(run_eval(t, extra=list(extra)).returncode, 0)
        ref = json.load(open(os.path.join(t, "run-T.json")))["content_sha256"]
        rp = os.path.join(t, "run-T.json"); R = json.load(open(rp)); R["status"] = "running"; R.pop("complete"); json.dump(R, open(rp, "w"))
        os.remove(os.path.join(t, "EVAL.SHA256")); return t, ref
    # ---- @0.2 (review N5): single runner + no stray writes into a run dir ----
    def live_pid(self):
        p = subprocess.Popen([PY, "-c", "import time; time.sleep(120)"]); self.addCleanup(p.kill); return p.pid
    def dead_pid(self):
        p = subprocess.Popen([PY, "-c", "pass"]); p.wait(); return p.pid
    def test_launch_against_live_run_refused_7_nothing_written(self):
        t, _ = self.partial(["--limit", "40"]); pid = self.live_pid(); lk = os.path.join(t, "eval.lock")
        open(lk, "w").write(json.dumps({"pid": pid, "started": "2026-11-15 10:00:00", "tag": "T"})); before = dirhash(t)
        for kw in ({"extra": ["--limit", "40"]}, {"extra": ["--limit", "40"], "pin_": "0" * 64}, {"extra": ["--limit", "40", "--mode", "fewshot"]},
                   {"extra": ["--limit", "48"]}):                 # duplicate launch, mistyped pin, invocation error, other config
            r = run_eval(t, **kw); self.assertEqual(r.returncode, 7, str(kw) + r.stdout); self.assertIn(f"pid {pid}", r.stdout); self.assertEqual(dirhash(t), before, kw)
        os.remove(lk); rp = os.path.join(t, "run-T.json"); R = json.load(open(rp)); R["sessions"][-1]["pid"] = pid; json.dump(R, open(rp, "w")); before = dirhash(t)
        r = run_eval(t, extra=["--limit", "40"], pin_="0" * 64); self.assertEqual(r.returncode, 7, r.stdout); self.assertEqual(dirhash(t), before)   # no lock, pid alive
    def test_mistyped_launch_against_stopped_run_writes_nothing(self):          # evidence 33-abort-into-running-dir.txt
        t, ref = self.partial(["--limit", "40"]); before = dirhash(t)
        r = run_eval(t, extra=["--limit", "40"], pin_="0" * 64); self.assertEqual(r.returncode, 6, r.stdout); self.assertIn("NOT recorded", r.stdout); self.assertEqual(dirhash(t), before)
        r = run_eval(t, extra=["--limit", "40", "--mode", "fewshot"]); self.assertEqual(r.returncode, 8, r.stdout); self.assertEqual(dirhash(t), before)
        self.assertEqual(json.load(open(os.path.join(t, "run-T.json")))["status"], "running")
        r = run_eval(t, extra=["--limit", "40"]); self.assertEqual(r.returncode, 0, r.stdout); R = json.load(open(os.path.join(t, "run-T.json")))
        self.assertEqual(R["status"], "complete"); self.assertEqual(R["content_sha256"], ref); self.assertEqual(aborts(t), [])
    def test_stale_lock_taken_over_and_recorded(self):
        t, ref = self.partial(["--limit", "40"]); dp = self.dead_pid()
        open(os.path.join(t, "eval.lock"), "w").write(json.dumps({"pid": dp, "started": "2026-11-15 09:00:00", "tag": "T"}))
        r = run_eval(t, extra=["--limit", "40"]); self.assertEqual(r.returncode, 0, r.stdout); R = json.load(open(os.path.join(t, "run-T.json")))
        self.assertEqual(R["sessions"][-1]["repairs"][0]["stale_lock"]["pid"], dp); self.assertFalse(os.path.exists(os.path.join(t, "eval.lock")))
        self.assertNotIn("eval.lock", open(os.path.join(t, "EVAL.SHA256")).read()); self.assertEqual(R["content_sha256"], ref)
    def test_lock_released_on_every_exit_path(self):
        t = os.path.join(tempfile.mkdtemp(), "o"); self.assertEqual(run_eval(t, extra=["--limit", "24"]).returncode, 0); self.assertNotIn("eval.lock", os.listdir(t))
        self.assertEqual(run_eval(t, extra=["--limit", "24"]).returncode, 7); self.assertNotIn("eval.lock", os.listdir(t))
        u = os.path.join(tempfile.mkdtemp(), "o"); self.assertEqual(run_eval(u, pin_="0" * 64).returncode, 6); self.assertEqual(sorted(os.listdir(u)), ["ABORT-1.json"])
        v, _ = self.partial(["--limit", "40"]); self.assertEqual(run_eval(v, extra=["--limit", "48"]).returncode, 7); self.assertNotIn("eval.lock", os.listdir(v))
    def test_concurrent_launches_one_runner(self):
        t = os.path.join(tempfile.mkdtemp(), "o")
        cmd = lambda: [PY, os.path.join(H, "eval.py"), "--rows", ROWS, "--expect_manifest_sha", pin(), "--out_dir", t, "--tag", "T", "--backend", "stub:gold", "--adapter", AD]
        P = [subprocess.Popen(cmd(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for _ in range(3)]
        rc = sorted(p.wait() for p in P); outs = [p.stdout.read() for p in P]; self.assertEqual(rc, [0, 7, 7], outs)
        R = json.load(open(os.path.join(t, "run-T.json"))); self.assertEqual(R["status"], "complete"); self.assertEqual(len(R["sessions"]), 1)
        self.assertEqual(aborts(t), []); self.assertNotIn("eval.lock", os.listdir(t))
    def test_partial_run_different_config_refused(self):
        t, _ = self.partial(["--limit", "40"]); before = dirhash(t)
        for ex in (["--limit", "40", "--batch", "4"], ["--limit", "40", "--max_new_tokens", "64"], ["--limit", "48"]):
            self.assertEqual(run_eval(t, extra=ex).returncode, 7, ex); self.assertEqual(dirhash(t), before)
        c = tempfile.mkdtemp(); shutil.copytree(os.path.join(FX, "adapter"), os.path.join(c, "adapter"))      # same bytes, different adapter path (M1)
        self.assertEqual(run_eval(t, extra=["--limit", "40"], adapter=os.path.join(c, "adapter", "final-adapter")).returncode, 7); self.assertEqual(dirhash(t), before)
        self.assertEqual(run_eval(t, extra=["--limit", "40"], adapter=None).returncode, 7)
    def test_resume_with_changed_adapter_bytes_refused(self):                     # ruling 4: same adapter path, new bytes (+ consistent ADAPTER.SHA256) -> 7
        c = tempfile.mkdtemp(); shutil.copytree(os.path.join(FX, "adapter"), os.path.join(c, "adapter")); ad = os.path.join(c, "adapter", "final-adapter")
        t = os.path.join(tempfile.mkdtemp(), "o"); self.assertEqual(run_eval(t, extra=["--limit", "40"], adapter=ad).returncode, 0)
        rp = os.path.join(t, "run-T.json"); R = json.load(open(rp)); R["status"] = "running"; R.pop("complete"); json.dump(R, open(rp, "w")); os.remove(os.path.join(t, "EVAL.SHA256"))
        old_sha = R["cfg"]["adapter_manifest_sha256"]
        open(os.path.join(ad, "adapter_config.json"), "a").write("\n")
        open(os.path.join(c, "adapter", "ADAPTER.SHA256"), "w").write("".join(f"{sha(os.path.join(ad, f))}  final-adapter/{f}\n" for f in ("adapter_config.json", "adapter_model.safetensors")))
        self.assertNotEqual(sha(os.path.join(c, "adapter", "ADAPTER.SHA256")), old_sha)
        before = dirhash(t); r = run_eval(t, extra=["--limit", "40"], adapter=ad); self.assertEqual(r.returncode, 7, r.stdout); self.assertEqual(dirhash(t), before)
        open(os.path.join(ad, "adapter_config.json"), "a").write("\n"); r = run_eval(t, extra=["--limit", "40"], adapter=ad)   # bytes != ADAPTER.SHA256 -> 6
        self.assertEqual(r.returncode, 6, r.stdout)
    def test_torn_tail_and_partial_batch_redone(self):
        t, ref = self.partial(["--limit", "40"]); p = os.path.join(t, "predictions-T.jsonl"); L = open(p).read().splitlines(True)
        open(p, "w").writelines(L[:-3] + [L[-3][:25]])                                                 # batch 5 of 5: 5 of 8 rows kept + a torn 6th line
        r = run_eval(t, extra=["--limit", "40"]); self.assertEqual(r.returncode, 0, r.stdout); self.assertIn("REPAIRED", r.stdout)
        R = json.load(open(os.path.join(t, "run-T.json"))); rep = R["sessions"][-1]["repairs"][0]
        self.assertEqual(rep["dropped_partial_batch_rows"], 5); self.assertGreater(rep["torn_tail_bytes"], 0); self.assertEqual(rep["partial_batches"], [4])
        self.assertEqual(R["content_sha256"], ref); self.assertEqual(len(R["sessions"]), 2); self.assertEqual(R["sessions"][-1]["batches_done_at_start"], 4)
        ids = [json.loads(l)["id"] for l in open(p)]; self.assertEqual(len(ids), 40); self.assertEqual(len(set(ids)), 40)
        B = [json.loads(l)["batch"] for l in open(p)]; self.assertEqual(B, sorted(B))
    def test_torn_last_line_with_newline_repaired_not_fatal(self):              # torn last record that still got its newline: repaired, not exit 12 (N21)
        t, ref = self.partial(["--limit", "40"]); p = os.path.join(t, "predictions-T.jsonl"); L = open(p).read().splitlines(True)
        open(p, "w").writelines(L[:-3] + [L[-3][:25] + "\n"])
        r = run_eval(t, extra=["--limit", "40"]); self.assertEqual(r.returncode, 0, r.stdout); self.assertIn("REPAIRED", r.stdout)
        R = json.load(open(os.path.join(t, "run-T.json"))); rep = R["sessions"][-1]["repairs"][0]
        self.assertEqual(rep["torn_tail_bytes"], 26); self.assertEqual(rep["partial_batches"], [4]); self.assertEqual(R["content_sha256"], ref)
        t, _ = self.partial(["--limit", "40"]); p = os.path.join(t, "predictions-T.jsonl"); L = open(p).read().splitlines(True)
        open(p, "w").writelines(L[:-3] + [L[-3][:25] + "\n", L[-2]])                 # the same bad line NOT last -> exit 12
        self.assertEqual(run_eval(t, extra=["--limit", "40"]).returncode, 12)
    def test_resume_same_config_no_duplicates(self):
        t, ref = self.partial(["--limit", "40"]); p = os.path.join(t, "predictions-T.jsonl"); L = open(p).read().splitlines(True); open(p, "w").writelines(L[:16])
        self.assertEqual(run_eval(t, extra=["--limit", "40"]).returncode, 0)
        ids = [json.loads(l)["id"] for l in open(p)]; self.assertEqual(len(ids), 40); self.assertEqual(len(set(ids)), 40)
        self.assertEqual(json.load(open(os.path.join(t, "run-T.json")))["content_sha256"], ref)
    def test_corrupt_middle_line_and_duplicates_exit_12(self):
        for fn in (lambda L: L[:3] + ["{bad\n"] + L[4:], lambda L: L + L[:1], lambda L: L[:-1] + ['{"id": "test:NOPE", "raw": "x"}\n']):
            t, _ = self.partial(["--limit", "40"]); p = os.path.join(t, "predictions-T.jsonl"); L = open(p).read().splitlines(True); open(p, "w").writelines(fn(L))
            r = run_eval(t, extra=["--limit", "40"]); self.assertEqual(r.returncode, 12, r.stdout); self.assertEqual(json.load(open(os.path.join(t, "run-T.json")))["status"], "aborted")
    def test_preds_without_run_json_and_unknown_files_refused(self):
        t = os.path.join(tempfile.mkdtemp(), "o"); os.makedirs(t); open(os.path.join(t, "predictions-T.jsonl"), "w").write("")
        self.assertEqual(run_eval(t).returncode, 7); self.assertEqual(os.listdir(t), ["predictions-T.jsonl"])
        t = os.path.join(tempfile.mkdtemp(), "o"); os.makedirs(t); open(os.path.join(t, "ABORT.json"), "w").write("{}")      # @0.0 marker = unknown
        self.assertEqual(run_eval(t).returncode, 7); self.assertEqual(os.listdir(t), ["ABORT.json"])
    def test_bad_invocation_exit_8(self):
        t = os.path.join(tempfile.mkdtemp(), "o"); r = run_eval(t, adapter=None, extra=["--mode", "fewshot"]); self.assertEqual(r.returncode, 8)
        self.assertEqual(json.load(open(os.path.join(t, "ABORT-1.json")))["exit"], 8)
        r = run_eval(os.path.join(tempfile.mkdtemp(), "o"), extra=["--replay_b1", "4"]); self.assertEqual(r.returncode, 8)
    def test_unhandled_crash_exit_11_with_cause(self):
        t = tempfile.mkdtemp(); src = os.path.join(t, "src.jsonl"); open(src, "w").write(json.dumps({"id": "test:NOPE", "raw": "x"}) + "\n")
        o = os.path.join(t, "o"); r = run_eval(o, mode=f"replay={src}"); self.assertEqual(r.returncode, 11)
        A = json.load(open(os.path.join(o, "ABORT-1.json"))); self.assertIn("KeyError", A["abort"]); self.assertIn("Traceback", A["traceback"])
        self.assertEqual(json.load(open(os.path.join(o, "run-T.json")))["status"], "aborted")
    def test_eval_sha256_complete_and_verifies(self):
        t, _ = Cache.get("gold"); L = [ln.split() for ln in open(os.path.join(t, "EVAL.SHA256")) if ln.strip()]
        self.assertTrue(L); files = {f for f in os.listdir(t) if f != "EVAL.SHA256" and os.path.isfile(os.path.join(t, f))}
        self.assertEqual({f for _, f in L}, files); self.assertIn("predictions-T.jsonl", files); self.assertIn("run-T.json", files)
        for h, f in L: self.assertEqual(sha(os.path.join(t, f)), h, f)
    def test_run_json_identity_and_content_hash(self):
        t, _ = Cache.get("gold"); R = json.load(open(os.path.join(t, "run-T.json"))); c = R["cfg"]
        self.assertEqual(c["adapter_path"], os.path.abspath(AD)); self.assertEqual(c["adapter_manifest_sha256"], ADSHA); self.assertIn("model_path", c)
        self.assertEqual(c["manifest_sha256"], pin()); self.assertEqual(set(c["inputs_sha256"]), {"eval_rows.jsonl", "eval.py", "evalcore.py"})
        self.assertEqual(c["run_manifest_lines"], open(MAN).read()); self.assertEqual(c["schema"], "bluebird-eval@0.2")   # N1: the run records its run manifest
        self.assertEqual(set(c["adapter_files_sha256"]), {"final-adapter/adapter_config.json", "final-adapter/adapter_model.safetensors"})
        preds = [json.loads(l) for l in open(os.path.join(t, "predictions-T.jsonl"))]; self.assertEqual(R["content_sha256"], content_sha256(preds))
        self.assertEqual(R["planned_rows"], 3569); self.assertEqual(R["complete"], True); self.assertEqual(R["status"], "complete")
    def test_smoke_plan_is_whole_full_run_batches(self):
        full = plan_batches(ALL_ROWS, "zero", 8); sm = plan_batches(ALL_ROWS, "zero", 8, "", 64)
        self.assertEqual(len(sm), 8); fs = [tuple(r["id"] for r in b) for b in full]
        for b in sm: self.assertIn(tuple(r["id"] for r in b), fs)
        self.assertEqual(sm[0], full[0]); self.assertEqual(sm[-1], full[-2]); self.assertEqual(sum(map(len, sm)), 64)   # last FULL batch = longest 8-row batch (peak memory); 1-row tail excluded
        self.assertEqual(sum(map(len, full)), 3569); self.assertTrue(all(len(b) == 8 for b in full[:-1]))
        ks = plan_batches(ALL_ROWS, "fewshot", 8, "test"); self.assertEqual(sum(map(len, ks)), 2090)
        k = [r["fs_prompt_tokens"] for b in ks for r in b]; self.assertEqual(k, sorted(k))

# ---------------- GPU branch on CPU (shim) ----------------
SUB = None
def stage_sub(tamper=None):
    """Work dir like the laptop's: eval.py, evalcore.py, score.py, evalstats.py, fewshot.json, a 38-row subset, its own manifest."""
    t = tempfile.mkdtemp(prefix="lbe-shim-")
    for f in ("eval.py", "evalcore.py", "score.py", "evalstats.py", "fewshot.json"): shutil.copy(os.path.join(H, f), t)
    sel = []
    for k in ("test", "cf", "ar", "sh", "rn", "pp"): sel += sorted([r for r in ALL_ROWS if r["kind"] == k], key=lambda r: (r["prompt_tokens"], r["id"]))[:6]
    sel += sorted([r for r in ALL_ROWS if r["kind"] == "test"], key=lambda r: (-r["prompt_tokens"], r["id"]))[:2]
    sel = json.loads(json.dumps(sel))
    if tamper: tamper(sel)
    open(os.path.join(t, "eval_rows.jsonl"), "w").write("".join(json.dumps(r, sort_keys=True) + "\n" for r in sel))
    open(os.path.join(t, "RUN-INPUTS.SHA256"), "w").write("".join(f"{sha(os.path.join(t, f))}  {f}\n" for f in ("eval_rows.jsonl", "fewshot.json", "eval.py", "evalcore.py")))
    open(os.path.join(t, "SCORE-INPUTS.SHA256"), "w").write("".join(f"{sha(os.path.join(t, f))}  {f}\n" for f in ("score.py", "evalcore.py", "evalstats.py", "eval_rows.jsonl")))
    return t
SHIM_VERS = json.dumps({"peft": "0.21.3", "torch": "2.15.0+cpu"})     # transformers: checked against VERIFIED_TRANSFORMERS / --pin_transformers
def shim(w, out, env=None, extra=(), model=None, adapter=AD, rows=None, vers=SHIM_VERS):
    cmd = [SHIM_PY, os.path.join(H, "tests", "shim_eval.py"), os.path.join(w, "eval.py"), "--rows", rows or os.path.join(w, "eval_rows.jsonl"),
           "--expect_manifest_sha", sha(os.path.join(os.path.dirname(rows or os.path.join(w, "x")), "RUN-INPUTS.SHA256")),
           "--model", model or os.path.join(FX, "model"), "--out_dir", os.path.join(w, out), "--tag", "t", "--max_new_tokens", "16"]
    cmd += (["--adapter", adapter] if adapter else []) + (["--expect_versions", vers] if vers else []) + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, **(env or {})}, cwd=w)
    return {"rc": r.returncode, "out": r.stdout, "err": r.stderr[-3000:], "dir": os.path.join(w, out)}
def scen_ok(w): return [shim(w, "ok", env={"SHIM_LOG": os.path.join(w, "ok.log")})]
def scen_ver(w): return [shim(w, "ver", vers=None)]
def scen_tf(w):
    v = {"SHIM_TF_VERSION": "5.22.2"}
    return [shim(w, "tf1", env=v), shim(w, "tf2", env=v, extra=["--preflight"]), shim(w, "tf3", env=v, extra=["--pin_transformers", "5.22.2"]),
            shim(w, "tf4", env=v, extra=["--pin_transformers", "5.21.0"]), shim(w, "tf5", extra=["--pin_transformers", "5.22.2"]), shim(w, "tf6", env=v), shim(w, "tf6", env=v, extra=["--pin_transformers", "5.22.2"])]
def scen_tamper(w): return [shim(w, "tam", env={"SHIM_TAMPER_MERGED": "1"})]
def scen_cuda(w): return [shim(w, "nc", env={"SHIM_CUDA": "0"}), shim(w, "nc")]
def scen_free(w): return [shim(w, "lf", env={"SHIM_FREE": "1e9"}), shim(w, "mf", env={"SHIM_FREE": "6e9"}, extra=["--min_free", "5e9"]), shim(w, "mf2", env={"SHIM_FREE": "6e9"})]
def scen_peak(w): return [shim(w, "pk", env={"SHIM_PEAK_AT": "1"}), shim(w, "pk")]
def scen_oomload(w): return [shim(w, "ol", env={"SHIM_OOM_LOAD": "1"}), shim(w, "ol")]
def scen_oomgen(w): return [shim(w, "og", env={"SHIM_OOM_AT": "2"}), shim(w, "og")]
def scen_long(w): return [shim(w, "lg", extra=["--max_new_tokens", "400"])]
def scen_raise(w): return [shim(w, "rs", env={"SHIM_RAISE_AT": "2"}), shim(w, "ki", env={"SHIM_INTERRUPT_AT": "1"})]
def scen_kill(w):
    a = shim(w, "kl", env={"SHIM_KILL_AT": "2"}); p = os.path.join(w, "kl", "predictions-t.jsonl")
    L = open(p).read().splitlines(True) if os.path.exists(p) else []     # @0.2 (review N2): a mutant may leave no/empty predictions
    if len(L) >= 3: open(p, "w").writelines(L[:-3] + [L[-3][:30]])
    return [a, shim(w, "kl", env={"SHIM_LOG": os.path.join(w, "kl.log")})]
def scen_model2(w):
    m2 = os.path.join(w, "model2"); shutil.copytree(os.path.join(FX, "model"), m2)
    a = shim(w, "m2", env={"SHIM_KILL_AT": "1"}); before = dirhash(os.path.join(w, "m2")); b = shim(w, "m2", model=m2); b["unchanged"] = dirhash(os.path.join(w, "m2")) == before
    return [a, b]
def scen_vchange(w):                                                               # N32: resume under other library versions -> 7, nothing written
    a = shim(w, "vc", env={"SHIM_KILL_AT": "1"}); before = dirhash(os.path.join(w, "vc"))
    b = shim(w, "vc", env={"SHIM_TF_VERSION": "5.22.2"}, extra=["--pin_transformers", "5.22.2"]); b["unchanged"] = dirhash(os.path.join(w, "vc")) == before
    return [a, b]
def scen_special(w): return [shim(w, "sp", env={"SHIM_SPECIAL": "1"})]
def scen_pre(w): return [shim(w, "pre", extra=["--preflight"]), shim(w, "prel", env={"SHIM_FREE": "1e9"}, extra=["--preflight"])]
def scen_fs(w): return [shim(w, "fs", adapter=None, extra=["--mode", "fewshot", "--fewshot", os.path.join(w, "fewshot.json")])]
def scen_full(w): return [shim(w, "full", rows=ROWS, extra=["--limit", "8", "--max_new_tokens", "4"])]
def scen_smoke(w):
    a = shim(w, "sm", extra=["--limit", "16", "--replay_b1", "4"])
    r = subprocess.run([SHIM_PY, os.path.join(w, "score.py"), "--rows", os.path.join(w, "eval_rows.jsonl"), "--expect_score_manifest_sha", sha(os.path.join(w, "SCORE-INPUTS.SHA256")),
                        "--expect_run_manifest_sha", sha(os.path.join(w, "RUN-INPUTS.SHA256")), "--smoke", "--out", os.path.join(w, "smscore"), "--pred", f"T={w}/sm/predictions-t.jsonl"], capture_output=True, text=True)
    return [a, {"rc": r.returncode, "out": r.stdout, "err": r.stderr, "dir": os.path.join(w, "smscore")}]
def scen_ids(w):
    def t(sel): sel[0]["ids_sha256"] = "0" * 64
    w2 = stage_sub(t); return [shim(w2, "id")]
def scen_count(w):
    def t(sel): sel[1]["prompt_tokens"] += 1
    w2 = stage_sub(t); return [shim(w2, "ct")]
def scen_outplan(w):                                                              # @0.2 (review N3): tampered row OUTSIDE the --limit plan
    def t(sel):
        plan = {r["id"] for b in plan_batches(sel, "zero", 8, "", 8) for r in b}
        x = next(r for r in sel if r["id"] not in plan); x["ids_sha256"] = "0" * 64; t.id = x["id"]
    w2 = stage_sub(t); r = shim(w2, "op", extra=["--limit", "8"]); r["tampered_id"] = t.id; return [r]
SCEN = {k[5:]: v for k, v in globals().items() if k.startswith("scen_")}
# @0.2 (review N2, Kaylee's HARDEN): a scenario that crashes (e.g. a mutant leaves no predictions) must fail ITS test, not the whole class
import inspect as _insp
def _safe(f):
    n = max(1, _insp.getsource(f).count("shim(") + _insp.getsource(f).count("subprocess.run("))
    def g(w):
        try: return f(w)
        except Exception as e: return [{"rc": -999, "out": "SCENARIO CRASHED " + repr(e), "err": "", "dir": w, "unchanged": False} for _ in range(n)]
    return g
SCEN.update({k: _safe(v) for k, v in list(SCEN.items())})
class Shim(unittest.TestCase):
    R = None
    @classmethod
    def setUpClass(cls):
        if os.environ.get("LBE_SKIP_SHIM") == "1": raise unittest.SkipTest("LBE_SKIP_SHIM=1")
        assert os.path.exists(SHIM_PY), f"shim python missing: {SHIM_PY} (set LBE_SHIM_PY)"
        names = [n for n in SCEN if os.environ.get("LBE_SHIM_ONLY", "") in ("", n) or n in os.environ.get("LBE_SHIM_ONLY", "").split(",")]
        def go(n): w = stage_sub(); return n, w, SCEN[n](w)
        with cf.ThreadPoolExecutor(int(os.environ.get("LBE_SHIM_JOBS", "8"))) as ex: cls.R = {n: (w, r) for n, w, r in ex.map(go, names)}
    def get(self, n):
        if n not in self.R: self.skipTest(f"{n} not selected")
        return self.R[n]
    def runjson(self, d): return json.load(open(os.path.join(d, "run-t.json")))
    def test_ok_greedy_merged_config_recorded(self):
        w, (a,) = self.get("ok"); self.assertEqual(a["rc"], 0, a["out"] + a["err"]); R = self.runjson(a["dir"]); s = R["sessions"][0]
        self.assertEqual(s["logits_processors"], []); g = s["merged_generation_config"]
        self.assertIs(g["do_sample"], False); self.assertEqual(g["num_beams"], 1); self.assertIn(g["repetition_penalty"], (None, 1.0)); self.assertIsNone(g["top_k"])
        self.assertEqual(sorted(g["eos_token_id"]), [151643, 151645]); self.assertEqual(s["versions"]["transformers"], "5.23.0"); self.assertEqual(s["transformers_check"], "PASS")
        self.assertIn("MERGED_GENERATION_CONFIG", a["out"]); self.assertIn("VERSIONS", a["out"]); self.assertEqual(R["status"], "complete")
        self.assertIn("generation_config.json", R["cfg"]["model_files_sha256"]); self.assertEqual(s["gpu_free_at_start"], int(7.5e9))
    def test_exit_13_versions_differ_from_train_json(self):
        w, (a,) = self.get("ver"); self.assertEqual(a["rc"], 13, a["out"]); A = json.load(open(os.path.join(a["dir"], "ABORT-1.json")))
        self.assertIn("2.11.0+cu128", A["abort"]); self.assertIn("torch", A["abort"]); self.assertFalse(os.path.exists(os.path.join(a["dir"], "predictions-t.jsonl")))
    def test_exit_13_unverified_transformers_unless_pinned(self):                     # ruling 8
        w, (a, b, c, d, e, early, f) = self.get("tf")
        self.assertEqual(a["rc"], 13, a["out"]); A = json.load(open(os.path.join(a["dir"], "ABORT-1.json")))
        for x in ("5.22.2", "5.23.0", "--pin_transformers 5.22.2"): self.assertIn(x, A["abort"])
        self.assertIn('"installed": "5.22.2"', a["out"]); self.assertNotIn("MERGED_GENERATION_CONFIG", a["out"])             # stops before the model loads
        self.assertFalse(os.path.exists(os.path.join(a["dir"], "predictions-t.jsonl"))); self.assertFalse(os.path.exists(os.path.join(a["dir"], "run-t.json")))
        self.assertEqual(b["rc"], 13, b["out"] + b["err"]); self.assertIn("MERGED_GENERATION_CONFIG", b["out"]); self.assertIn("VERSIONS", b["out"])  # E0: prints both, then stops
        P = json.load(open(os.path.join(b["dir"], "PREFLIGHT-t-1.json"))); self.assertEqual(P["transformers_check"], "FAIL"); self.assertEqual(P["session"]["logits_processors"], [])
        self.assertEqual(P["session"]["gpu_free_at_start"], int(7.5e9)); self.assertEqual(aborts(b["dir"]), ["ABORT-1.json"])
        self.assertEqual(c["rc"], 0, c["out"] + c["err"]); s = self.runjson(c["dir"])["sessions"][0]
        self.assertEqual((s["versions"]["transformers"], s["transformers_pin"], s["transformers_check"]), ("5.22.2", "5.22.2", "PINNED_UNVERIFIED"))
        self.assertEqual(d["rc"], 13); self.assertIn("!= installed", json.load(open(os.path.join(d["dir"], "ABORT-1.json")))["abort"])
        self.assertEqual(e["rc"], 13); self.assertIn("!= installed transformers 5.23.0", json.load(open(os.path.join(e["dir"], "ABORT-1.json")))["abort"])
        self.assertEqual(early["rc"], 13); self.assertEqual(f["rc"], 0, f["out"] + f["err"]); self.assertEqual(aborts(f["dir"]), ["ABORT-1.json"])             # pinned rerun after the early abort starts clean
    def test_exit_13_merged_config_not_greedy(self):
        w, (a,) = self.get("tamper"); self.assertEqual(a["rc"], 13, a["out"] + a["err"]); A = json.load(open(os.path.join(a["dir"], "ABORT-1.json")))
        for k in ("do_sample", "repetition_penalty", "logits_processors"): self.assertIn(k, A["abort"])
        self.assertEqual(open(os.path.join(a["dir"], "predictions-t.jsonl")).read(), "")                # nothing from the bad batch was written
    def test_exit_10_no_cuda_then_clean_rerun(self):
        w, (a, b) = self.get("cuda"); self.assertEqual(a["rc"], 10); self.assertEqual(b["rc"], 0, b["out"] + b["err"])        # H4: no exit 7 after an early abort
        self.assertEqual(aborts(b["dir"]), ["ABORT-1.json"]); self.assertEqual(json.load(open(os.path.join(b["dir"], "ABORT-1.json")))["exit"], 10)
    def test_exit_10_low_free_and_configurable_floor(self):
        w, (a, b, c) = self.get("free"); self.assertEqual(a["rc"], 10); self.assertIn("1000000000", json.load(open(os.path.join(a["dir"], "ABORT-1.json")))["abort"])
        self.assertEqual(b["rc"], 0, b["out"] + b["err"]); self.assertEqual(c["rc"], 10)
        self.assertEqual(self.runjson(b["dir"])["sessions"][0]["min_free"], 5e9)
    def test_exit_3_peak_then_resume(self):
        w, (a, b) = self.get("peak"); self.assertEqual(a["rc"], 3); self.assertEqual(b["rc"], 0, b["out"] + b["err"])
        R = self.runjson(b["dir"]); self.assertEqual(R["sessions"][1]["batches_done_at_start"], 1); self.assertEqual(R["sessions"][0]["abort_file"], "ABORT-1.json")
        self.assertEqual(aborts(b["dir"]), ["ABORT-1.json"]); self.assertEqual(R["predictions"], 38)
    def test_exit_5_oom_at_load_then_clean_rerun(self):
        w, (a, b) = self.get("oomload"); self.assertEqual(a["rc"], 5); self.assertEqual(b["rc"], 0, b["out"] + b["err"])
    def test_exit_5_oom_in_generate_then_resume(self):
        w, (a, b) = self.get("oomgen"); self.assertEqual(a["rc"], 5); self.assertEqual(b["rc"], 0); self.assertEqual(self.runjson(b["dir"])["sessions"][1]["batches_done_at_start"], 1)
    def test_exit_9_prompt_too_long(self):
        w, (a,) = self.get("long"); self.assertEqual(a["rc"], 9); self.assertIn("prompt_too_long", json.load(open(os.path.join(a["dir"], "ABORT-1.json")))["abort"])
    def test_exit_11_unhandled_and_interrupt(self):
        w, (a, b) = self.get("raise"); self.assertEqual(a["rc"], 11); self.assertIn("RuntimeError", json.load(open(os.path.join(a["dir"], "ABORT-1.json")))["abort"])
        self.assertEqual(b["rc"], 11); self.assertIn("KeyboardInterrupt", json.load(open(os.path.join(b["dir"], "ABORT-1.json")))["abort"])
        self.assertEqual(self.runjson(a["dir"])["status"], "aborted")
    def test_exit_4_ids_sha_and_count(self):
        _, (a,) = self.get("ids"); self.assertEqual(a["rc"], 4); self.assertIn("tokenizer_mismatch ids", json.load(open(os.path.join(a["dir"], "ABORT-1.json")))["abort"])
        _, (b,) = self.get("count"); self.assertEqual(b["rc"], 4); self.assertIn("tokenizer_mismatch count", json.load(open(os.path.join(b["dir"], "ABORT-1.json")))["abort"])
    def test_exit_4_row_outside_limit_plan(self):                                  # @0.2 (N3): the token check covers rows outside --limit
        _, (a,) = self.get("outplan"); self.assertEqual(a["rc"], 4, a["out"] + a["err"])
        A = json.load(open(os.path.join(a["dir"], "ABORT-1.json"))); self.assertIn(f"tokenizer_mismatch ids {a['tampered_id']}", A["abort"])
    def test_kill_torn_resume_same_batches_same_text(self):
        w, (a, b) = self.get("kill"); wo, (o,) = self.get("ok"); self.assertEqual(a["rc"], 137); self.assertEqual(b["rc"], 0, b["out"] + b["err"])
        R = self.runjson(b["dir"]); self.assertEqual(R["content_sha256"], self.runjson(o["dir"])["content_sha256"])          # same text as uninterrupted
        reps = R["sessions"][1]["repairs"]; self.assertEqual(reps[0]["stale_lock"]["pid"], R["sessions"][0]["pid"])   # @0.2: kill -9 leaves a stale lock
        rep = reps[1]; self.assertGreater(rep["torn_tail_bytes"], 0); self.assertEqual(rep["partial_batches"], [1])
        sh = lambda f: [json.loads(l)["shape"] for l in open(f) if '"shape"' in l]
        self.assertEqual(sh(os.path.join(w, "kl.log")), sh(os.path.join(wo, "ok.log"))[1:])                                 # redone batches = the same fixed batches
    def test_resume_with_different_model_refused_nothing_written(self):
        w, (a, b) = self.get("model2"); self.assertEqual(a["rc"], 137); self.assertEqual(b["rc"], 7); self.assertTrue(b["unchanged"]); self.assertIn("model", b["out"])
    def test_resume_under_other_library_versions_refused_nothing_written(self):
        w, (a, b) = self.get("vchange"); self.assertEqual(a["rc"], 137); self.assertEqual(b["rc"], 7, b["out"]); self.assertTrue(b["unchanged"])
        self.assertIn("library versions differ", b["out"])
    def test_special_tokens_stay_visible(self):
        w, (a,) = self.get("special"); self.assertEqual(a["rc"], 0, a["out"] + a["err"])
        raws = [json.loads(l)["raw"] for l in open(os.path.join(a["dir"], "predictions-t.jsonl"))]; self.assertTrue(all(r.startswith("<|im_start|>") for r in raws))
    def test_preflight_records_merged_config_and_free_memory(self):
        w, (a, b) = self.get("pre"); self.assertEqual(a["rc"], 0, a["out"] + a["err"]); P = json.load(open(os.path.join(a["dir"], "PREFLIGHT-t-1.json")))
        self.assertEqual(P["session"]["logits_processors"], []); self.assertEqual(P["min_free_check"], "PASS"); self.assertEqual(P["session"]["gpu_free_at_start"], int(7.5e9))
        self.assertFalse(os.path.exists(os.path.join(a["dir"], "predictions-t.jsonl")))
        self.assertEqual(b["rc"], 10); self.assertEqual(json.load(open(os.path.join(b["dir"], "PREFLIGHT-t-1.json")))["min_free_check"], "FAIL")
    def test_fewshot_branch(self):
        w, (a,) = self.get("fs"); self.assertEqual(a["rc"], 0, a["out"] + a["err"]); self.assertEqual(self.runjson(a["dir"])["cfg"]["adapter_path"], None)
    def test_all_3569_prompt_ids_match_hf(self):
        w, (a,) = self.get("full"); self.assertEqual(a["rc"], 0, a["out"] + a["err"]); self.assertEqual(self.runjson(a["dir"])["predictions"], 8)
    def test_smoke_replay_and_smoke_score(self):
        w, (a, b) = self.get("smoke"); self.assertEqual(a["rc"], 0, a["out"] + a["err"]); s = self.runjson(a["dir"])["sessions"][0]
        self.assertEqual(s["replay_b1"]["rows"], 4); self.assertIn("raw_differs", s["replay_b1"])
        self.assertEqual(b["rc"], 0, b["err"]); S = json.load(open(os.path.join(b["dir"], "SMOKE-T.json"))); self.assertIn("NO_VERDICT", S); self.assertEqual(S["rows"], 16)
        self.assertTrue(S["E3_acceptance_proposed"]["merged generation config read and greedy (every session)"])

class Build(unittest.TestCase):
    def test_rename_no_independent_real_supplier_brands(self):                       # @0.2 (N4), independent of the builder's catalog/leak_terms
        brands = {"GSK": "AREXVY HAVRIX TWINRIX KINRIX INFANRIX ROTARIX MENVEO PENMENVY FLUARIX BEXSERO BOOSTRIX ENGERIX PEDIARIX PRIORIX SHINGRIX FLULAVAL CERVARIX HIBERIX GLAXOSMITHKLINE GLAXO GSK",
                  "PFIZER": "PREVNAR ABRYSVO COMIRNATY TRUMENBA NIMENRIX PENBRAYA TICOVAC VAXCHORA WYETH PFIZER",
                  "MERCK": "GARDASIL PNEUMOVAX PROQUAD RECOMBIVAX ROTATEQ VARIVAX VAXNEUVANCE CAPVAXIVE ENFLONSIA M-M-R VAQTA PEDVAXHIB ZOSTAVAX ERVEBO VAXELIS MSD MERCK",
                  "SANOFI": "ADACEL BEYFORTUS FLUBLOK FLUZONE MENQUADFI PENTACEL QUADRACEL DAPTACEL IPOL IMOVAX TENIVAC YF-VAX VAXELIS TYPHIM MENACTRA PASTEUR SANOFI",
                  "SEQIRUS": "FLUAD FLUCELVAX AFLURIA AUDENZ CSL SEQIRUS"}
        rn = [r for r in ALL_ROWS if r["kind"] == "rn"]; self.assertEqual(len(rn), 300)
        for r in rn:
            s = next(k for k in brands if k in r["renamed_from"].upper())
            txt = r["question"] + "\n" + "\n".join(u["text"] for u in r["units"]) + "\n" + json.dumps(r["gold"])
            left = [t for t in brands[s].split() if re.search(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", txt, re.I)]
            self.assertEqual(left, [], (r["id"], left))
        self.assertTrue(all("TENIVAC" in r["leak_terms"] and "MENACTRA" in r["leak_terms"] for r in rn if r["renamed_from"] == "SANOFI"))
    @classmethod
    def setUpClass(cls):
        tq = [json.loads(l) for l in open(f"{GEN}/train/qa.jsonl")] + [json.loads(l) for l in open(f"{GEN}/test/qa.jsonl")]
        cls.known = set().union(*(pc.grams(q["question"]) for q in tq))
    @unittest.skipUnless(os.environ.get("LBE_REBUILD") == "1", "set LBE_REBUILD=1 (needs tokenizers + jinja2; ~45 s)")
    def test_builder_is_deterministic(self):
        t = tempfile.mkdtemp(); env = dict(os.environ, EVAL_OUT=t)
        r = subprocess.run([PY, os.path.join(H, "build_eval_rows.py")], capture_output=True, text=True, env=env); self.assertEqual(r.returncode, 0, r.stderr)
        for f in ("eval_rows.jsonl", "fewshot.json", "BUILD.json"): self.assertEqual(sha(os.path.join(t, f)), sha(os.path.join(H, f)), f)
    def test_probe_rows_well_formed(self):
        self.assertEqual(pc.check_rows(ALL_ROWS, self.known), [])
        test = [r for r in ALL_ROWS if r["kind"] == "test"]; self.assertEqual(len(test), 2090); self.assertEqual(sum(r["expect_refusal"] for r in test), 430)
        self.assertEqual(collections.Counter(r["kind"] for r in ALL_ROWS), {"test": 2090, "cf": 279, "ar": 300, "sh": 300, "rn": 300, "pp": 300})
        rn = [r for r in ALL_ROWS if r["kind"] == "rn"]; self.assertGreater(sum(bool(r["renamed_brands"]) for r in rn), 290)
    def test_probe_checks_catch_broken_rows(self):
        def first(R, k): return next(r for r in R if r["kind"] == k)
        cases = {
            "cf_old_present": lambda R: first(R, "cf")["units"].append({"id": "X#1", "text": "value " + first(R, "cf")["old_value"]}),            # D01
            "rn_real_name_present": lambda R: first(R, "rn")["units"].append({"id": "X#1", "text": first(R, "rn")["renamed_from"].title() + " will supply."}),  # D02
            "sh_anchor_not_moved": lambda R: [r.__setitem__("units", [u for u in {x["src"]: x for x in R if x["kind"] == "test"}[r["src"]]["units"]]) for r in R if r["kind"] == "sh"],  # D03
            "pp_not_paraphrased": lambda R: [r.__setitem__("question", r["original_question"] + " ") for r in R if r["kind"] == "pp"],                 # D04
            "ar_old_present": lambda R: first(R, "ar")["units"].append({"id": "Y#9", "text": "It is " + first(R, "ar")["old_value"][0]}),           # D05
            "ar_gold_not_refusal": lambda R: first(R, "ar").__setitem__("gold", {"answer": "x {S1}", "spans": {"S1": {"anchor": "A#1", "text": "1"}}}),  # D06
            "cf_new_not_once": lambda R: first(R, "cf")["units"].append({"id": "X#2", "text": "again " + first(R, "cf")["new_value"]}),
            "cf_gold_not_new": lambda R: next(iter(first(R, "cf")["gold"]["spans"].values())).__setitem__("text", "zzz"),
            "cf_placebo_present": lambda R: (lambda r: r["units"].append({"id": "X#3", "text": "is " + r["placebo_value"]}))(next(r for r in R if r["kind"] == "cf" and r["placebo_value"])),
            "ar_placebo_present": lambda R: first(R, "ar")["units"].append({"id": "Y#8", "text": "It is " + first(R, "ar")["placebo_value"][0]}),
            "ar_unit_kept": lambda R: first(R, "ar")["units"].append({"id": first(R, "ar")["removed"][0], "text": "kept"}),
            "sh_units_changed": lambda R: first(R, "sh")["units"].pop(),
            "rn_leak_terms_incomplete": lambda R: first(R, "rn")["leak_terms"].remove(first(R, "rn")["renamed_from"]),
            "pp_4gram_with_corpus": lambda R: first(R, "pp").__setitem__("question", first(R, "pp")["original_question"].upper()),
            "pp_units_changed": lambda R: first(R, "pp")["units"].pop(),
            "over_budget": lambda R: first(R, "test").__setitem__("prompt_tokens", 1409),
            "dup_id": lambda R: R.append(json.loads(json.dumps(first(R, "pp")))),
            "no_src": lambda R: first(R, "sh").__setitem__("src", "NOPE"),
            "rn_fake_absent": lambda R: first(R, "rn").__setitem__("renamed_to", "ZQXWV NOWHERE"),
            "unknown_kind": lambda R: first(R, "pp").__setitem__("kind", "zz"),
        }
        for code, fn in cases.items():
            R = json.loads(json.dumps(ALL_ROWS)); fn(R); got = {c for c, _ in pc.check_rows(R, self.known)}
            self.assertIn(code, got, code)
    def test_check_functions_negative(self):
        t = tempfile.mkdtemp(); p = os.path.join(t, "f"); open(p, "w").write("x")
        self.assertEqual(pc.check_sha_pin(p, hashlib.sha256(b"x").hexdigest()), []); self.assertTrue(pc.check_sha_pin(p, "0" * 64))
        self.assertEqual(pc.check_system_disjoint({"A", "B"}, {"C"}), []); self.assertEqual(pc.check_system_disjoint({"A", "B"}, {"B"}), [("system_overlap", "B")])
        self.assertTrue(pc.check_absent(["TESSARA PHARMA"], [("d", "made by Tessara  Pharma"), ("e", "by tessara pharma")]))
        self.assertEqual(pc.check_absent(["ORRIN"], [("d", "ORRINX")]), [])
        self.assertTrue(pc.check_paraphrase_templates({"x": ["what is the rebate rate for this"]}, pc.grams("so what is the rebate rate here")))
    def bad_corpus(self, mutate):
        t = tempfile.mkdtemp(); g = os.path.join(t, "gen"); os.makedirs(os.path.join(g, "test")); os.symlink(f"{GEN}/train", os.path.join(g, "train")) if mutate[0] != "train" else None
        for d in ("docs", "leaves"): os.symlink(f"{GEN}/test/{d}", os.path.join(g, "test", d))
        shutil.copy(f"{GEN}/test/qa.jsonl", os.path.join(g, "test", "qa.jsonl"))
        if mutate[0] == "train":
            os.makedirs(os.path.join(g, "train")); os.symlink(f"{GEN}/train/leaves", os.path.join(g, "train", "leaves")); shutil.copy(f"{GEN}/train/qa.jsonl", os.path.join(g, "train", "qa.jsonl"))
            os.makedirs(os.path.join(g, "train", "docs"))
            for f in os.listdir(f"{GEN}/train/docs"): os.symlink(f"{GEN}/train/docs/{f}", os.path.join(g, "train", "docs", f))
        mutate[1](g); out = os.path.join(t, "out"); os.makedirs(out)
        r = subprocess.run([PY, os.path.join(H, "build_eval_rows.py")], capture_output=True, text=True, env=dict(os.environ, GEN_OUT=g, EVAL_OUT=out))
        return r, os.listdir(out)
    def test_builder_refuses_bad_corpus_and_writes_nothing(self):
        def qa_edit(g): p = os.path.join(g, "test", "qa.jsonl"); open(p, "a").write("\n")
        def overlap(g):
            p = os.path.join(g, "train", "qa.jsonl"); q = json.loads(open(f"{GEN}/test/qa.jsonl").readline()); open(p, "a").write(json.dumps(q) + "\n")
        def fake(g):
            f = sorted(os.listdir(os.path.join(g, "train", "docs")))[0]; p = os.path.join(g, "train", "docs", f); os.remove(p); open(p, "w").write(open(f"{GEN}/train/docs/{f}").read() + "\nOrrin Vaccine Co\n")
        for name, m, msg in (("qa", ("test", qa_edit), "sha256 != ORDER"), ("overlap", ("train", overlap), "system overlap"), ("fake", ("train", fake), "fake names vs corpus")):
            r, files = self.bad_corpus(m); self.assertNotEqual(r.returncode, 0, name); self.assertIn(msg, r.stderr, name); self.assertEqual(files, [], name)

if __name__ == "__main__": unittest.main()
