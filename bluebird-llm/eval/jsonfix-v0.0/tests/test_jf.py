# jf0.0 box tests (CPU). Run from the stage root with the review venv (torch CPU, transformers 5.23.0, tokenizers):
#   PYTHONDONTWRITEBYTECODE=1 /workspace/littleblue-fullrun-review/venv/bin/python -B -m unittest -v tests.test_jf
# Classes: Automaton (byte acceptor = parse_strict), Vocab (byte table vs the real tokenizer), Proc (logits processor with mocked logits),
#          Identity (run identity, collisions, out-T untouched, score.py pins), EvalPatch (eval.py jf0.0 lines).
import hashlib, json, os, random, re, shutil, subprocess, sys, tempfile, unittest
J = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, J)
V05 = "/workspace/littleblue-eval-v0.5"; R03 = V05 + "/runs/r03"; FX = V05 + "/tests/fixtures"; AD = FX + "/adapter/final-adapter"
import jsonslot as JS, evalcore as EC
from evalcore import parse_strict
PY = sys.executable
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
OUT_T = {"EVAL.SHA256": "5d0873c68712a1531acb6ef95c52702cef85ce786cccfe547754146b0d2d7f64",
         "predictions-bluebird-v1.0-e2.jsonl": "8b2fab1571464515bf517419d84e476a99b847d65245110491b5883fc7f3fed3",
         "run-bluebird-v1.0-e2.json": "ee85fbb619fbf7ba226acb302256298aa1231bc1e4b6f47e79973f090b600e44"}
RAWS = [json.loads(l) for l in open(R03 + "/out-T/predictions-bluebird-v1.0-e2.jsonl", encoding="utf-8")]

def walk(s, bs):
    s = s.clone()
    for b in bs:
        if not s.feed(b): return None
    return s

class Automaton(unittest.TestCase):
    def test_slot_regex_is_evalcore(self): self.assertEqual(JS.SLOT.pattern, EC.SLOT.pattern)
    def test_every_strict_valid_outT_raw_accepted_and_complete(self):
        n = 0
        for p in RAWS:
            if parse_strict(p["raw"])[1] is None:
                al, dn, off = JS.accepts(p["raw"]); self.assertTrue(al and dn, (p["id"], off)); n += 1
        self.assertEqual(n, 3556)
    def test_the_13_invalid_outT_raws(self):
        exp = {"not_json": (True, False), "bad_span_key": (False, False), "bad_span_obj": (False, False), "slot_mismatch": (False, False)}
        bad = [(p, parse_strict(p["raw"])[1]) for p in RAWS if parse_strict(p["raw"])[1] is not None]
        self.assertEqual(len(bad), 13)
        for p, why in bad:
            al, dn, off = JS.accepts(p["raw"]); self.assertEqual((al, dn), exp[why], p["id"])
    def test_bare_string_span_impossible(self):
        s = walk(JS.State(), b'{"answer": "x {S1}", "spans": {"S1": ')
        self.assertIsNotNone(s); self.assertIsNone(walk(s, b'"')); self.assertIsNotNone(walk(s, b'{'))
        self.assertIsNone(walk(JS.State(), b'{"answer": "x {S1}", "spans": {"S1": "a"}}'))
    def test_non_slot_key_impossible(self):
        s = walk(JS.State(), b'{"answer": "The Customer turned the terms down.", "spans": {')
        self.assertIsNone(walk(s, b'"')); self.assertIsNotNone(walk(s, b'}}'))
        self.assertIsNone(walk(JS.State(), b'{"answer": "a {S1}", "spans": {"SYN-1#4": '))
    def test_slot_mismatch_impossible(self):
        s = walk(JS.State(), b'{"answer": "below {S2}.", "spans": {"S')
        self.assertIsNone(walk(s, b'1')); self.assertIsNotNone(walk(s, b'2"'))
        s2 = walk(JS.State(), b'{"answer": "a {S1} b {S2}", "spans": {"S2": {"anchor": "x", "text": "y"}')
        self.assertIsNone(walk(s2, b'}')); self.assertIsNotNone(walk(s2, b', "S1"'))
        self.assertIsNone(walk(s2, b', "S2"'))                                   # no duplicate key
        s3 = walk(JS.State(), b'{"answer": "a {S1}", "spans": {"S1": {"anchor": "x", "text": "y"}')
        self.assertIsNone(walk(s3, b', ')); self.assertTrue(walk(s3, b'}}').done())  # no extra key
    def test_prefix_keys_S1_S12(self):
        s = walk(JS.State(), b'{"answer": "{S1} {S12}", "spans": {"S1')
        self.assertIsNotNone(walk(s, b'"')); self.assertIsNotNone(walk(s, b'2"')); self.assertIsNone(walk(s, b'3'))
    def test_refusal_forces_empty_spans(self):
        s = walk(JS.State(), b'{"answer": "not in the contracts", "spans": {')
        self.assertIsNone(walk(s, b'"')); self.assertTrue(walk(s, b'}}').done())
    def test_escapes_and_bytes(self):
        ok = ['{"answer": "a\\"b\\\\c\\/d\\n\\t\\u00e9 {S1}", "spans": {"S1": {"anchor": "D#1", "text": "caf\u00e9 \\u007b"}}}']
        for r in ok: self.assertEqual(JS.accepts(r)[:2], (True, True)); self.assertIsNone(parse_strict(r)[1])
        self.assertIsNone(walk(JS.State(), b'{"answer": "a\\x'))
        self.assertIsNone(walk(JS.State(), b'{"answer": "a\n'))
        self.assertIsNone(walk(JS.State(), b'{"answer": "\\u00g'))
        self.assertIsNotNone(walk(JS.State(), '{"answer": "\u00e9'.encode()))
    def test_escaped_slot_counts(self):                     # \u007bS1} decodes to {S1}: parse_strict needs span S1, so must the automaton
        r = '{"answer": "\\u007bS1}", "spans": {"S1": {"anchor": "a", "text": "b"}}}'
        self.assertIsNone(parse_strict(r)[1]); self.assertEqual(JS.accepts(r)[:2], (True, True))
        self.assertIsNone(walk(JS.State(), b'{"answer": "\\u007bS1}", "spans": {}'))
    def test_nothing_after_close(self):
        s = walk(JS.State(), b'{"answer": "a", "spans": {}}'); self.assertTrue(s.done())
        for b in range(256): self.assertFalse(s.clone().feed(b))
    def test_random_walks_always_strict_valid(self):
        """Property: any byte string the automaton reaches DONE on is strict-valid (2,000 random walks over allowed bytes)."""
        rnd = random.Random(562); n_done = 0
        alphabet = list(b'{}"\\:, Sanswerpanchortextu0123456789#.-abcdefABCDEFnrtbf/') + [0xc3, 0xa9, 0x7f]
        for _ in range(2000):
            s = JS.State(); out = bytearray()
            for step in range(400):
                if s.done(): break
                opts = [b for b in alphabet if s.clone().feed(b)]
                self.assertTrue(opts, bytes(out))                                # never a dead end
                if s.ph == "S" and rnd.random() < 0.15 and s.clone().feed(0x22): b = 0x22
                else: b = rnd.choice(opts)
                s.feed(b); out.append(b)
            if s.done():
                n_done += 1; self.assertIsNone(parse_strict(out.decode("utf-8", "replace"))[1], bytes(out))
        self.assertGreater(n_done, 300)
    def test_random_valid_objects_accepted(self):
        """Converse: json.dumps of random strict-valid objects (slots, escapes, unicode) is accepted and DONE."""
        rnd = random.Random(7); pool = ["a", "\u00e9", "\"", "\\", "\n", "\t", "{", "}", "S", "1", " ", "\u2019", "/"]
        for _ in range(3000):
            ks = sorted({f"S{rnd.randint(1, 12)}" for _ in range(rnd.randint(0, 3))})
            ans = "".join(rnd.choice(pool) for _ in range(rnd.randint(0, 8))) + "".join("{%s}" % k for k in ks)
            if ans.strip().lower() == EC.REFUSAL_TEXT: continue
            ks2 = sorted({m[1:-1] for m in EC.SLOT.findall(ans)}); rnd.shuffle(ks2)
            o = {"answer": ans, "spans": {k: {"anchor": "".join(rnd.choice(pool) for _ in range(3)), "text": "".join(rnd.choice(pool) for _ in range(4))} for k in ks2}}
            r = json.dumps(o, ensure_ascii=rnd.random() < 0.5)
            self.assertIsNone(parse_strict(r)[1], r); self.assertEqual(JS.accepts(r)[:2], (True, True), r)

class Vocab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.TB = JS.token_bytes_from_tokenizer_json(FX + "/model/tokenizer.json", 151665)
        from tokenizers import Tokenizer
        cls.tk = Tokenizer.from_file(FX + "/model/tokenizer.json")
    def test_pinned_sha_refused_otherwise(self):
        t = tempfile.mkdtemp(); p = os.path.join(t, "tokenizer.json"); open(p, "wb").write(open(FX + "/model/tokenizer.json", "rb").read() + b" ")
        with self.assertRaises(ValueError): JS.token_bytes_from_tokenizer_json(p, 151665)
    def test_specials_have_no_bytes(self):
        for i in range(151643, 151665): self.assertIsNone(self.TB[i])
        self.assertEqual(sum(b is not None for b in self.TB), 151643)
        self.assertEqual(sorted({len(b) for b in self.TB if b is not None and len(b) == 1}), [1]); self.assertEqual(len({b for b in self.TB if b is not None and len(b) == 1}), 256)
    def test_byte_table_matches_tokenizer_on_all_outT_raws(self):
        for p in RAWS:
            ids = self.tk.encode(p["raw"], add_special_tokens=False).ids
            self.assertEqual(b"".join(self.TB[i] for i in ids), p["raw"].encode("utf-8"), p["id"])
            self.assertEqual(self.tk.decode(ids, skip_special_tokens=False), p["raw"])

class Proc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch; cls.torch = torch
        cls.TB = JS.token_bytes_from_tokenizer_json(FX + "/model/tokenizer.json", 151665); cls.V = 151936
        cls.BY = {}
        for i, b in enumerate(cls.TB):
            if b is not None and b not in cls.BY: cls.BY[b] = i
    def masked_argmax(self, st, row):
        torch = self.torch; m = torch.full_like(row, float("-inf"))
        P = JS.JsonSlotConstraint(self.TB, [151645, 151643], 1)
        ok = [t for t in range(row.shape[0]) if P.allowed(st, t)]
        m[ok] = row[ok]; return int(torch.argmax(m)), len(ok)
    def test_greedy_exact_vs_full_mask(self):
        """The lazy choice equals argmax after masking every disallowed token (full 151,936-id scan), incl. ties."""
        torch = self.torch; g = torch.Generator().manual_seed(562)
        prefixes = [b'', b'{"answer": "x', b'{"answer": "x {S2}", "spans": {"S', b'{"answer": "x", "spans": {', b'{"answer": "a {S1}", "spans": {"S1": {"anchor": "D',
                    b'{"answer": "a {S1}", "spans": {"S1": {"anchor": "D", "text": "v"}', b'{"answer": "a", "spans": {}}']
        for pre in prefixes:
            st = walk(JS.State(), pre)
            for trial in range(2):
                row = torch.randn(self.V, generator=g)
                if trial == 1: row = torch.round(row)                             # many ties
                P = JS.JsonSlotConstraint(self.TB, [151645, 151643], 1); P.states[0] = st.clone()
                out = P(torch.zeros((1, 5), dtype=torch.long), row[None].clone())
                want, n_ok = self.masked_argmax(st, row)
                self.assertEqual(int(torch.argmax(out[0])), want, (pre, trial)); self.assertGreater(n_ok, 0)
                self.assertEqual(int(torch.isfinite(out[0]).sum()), 1)
    def test_argmax_kept_when_allowed_and_counts_forced(self):
        torch = self.torch; P = JS.JsonSlotConstraint(self.TB, [151645, 151643], 2)
        row = torch.zeros((2, self.V)); row[0, self.BY[b'{"']] = 5; row[1, self.BY[b'['] if b'[' in self.BY else 58] = 5
        out = P(torch.zeros((2, 3), dtype=torch.long), row)
        self.assertEqual(int(out[0].argmax()), self.BY[b'{"']); self.assertNotEqual(int(out[1].argmax()), self.BY.get(b'[', 58))
        self.assertEqual(P.forced, [0, 1])
    def test_stop_only_when_done_and_finished_rows_untouched(self):
        torch = self.torch; P = JS.JsonSlotConstraint(self.TB, [151645, 151643], 2)
        P.states[0] = walk(JS.State(), b'{"answer": "a", "spans": {}}'); P.states[1] = walk(JS.State(), b'{"answer": "a')
        row = torch.zeros((2, self.V)); row[:, 151645] = 9
        out = P(torch.zeros((2, 4), dtype=torch.long), row.clone())
        self.assertEqual(int(out[0].argmax()), 151645); self.assertNotEqual(int(out[1].argmax()), 151645)
        nxt = torch.tensor([[0, 0, 0, 0, 151645], [0, 0, 0, 0, int(out[1].argmax())]])
        out2 = P(nxt, row.clone()); self.assertTrue(P.fin[0]); self.assertTrue(torch.equal(out2[0], row[0]))
        nxt2 = torch.cat([nxt, torch.tensor([[151643], [151643]])], 1)
        with self.assertRaises(RuntimeError): P(nxt2, row.clone())               # row 1 'stopped' before its object was complete
    def test_disallowed_token_fed_back_raises(self):
        torch = self.torch; P = JS.JsonSlotConstraint(self.TB, [151645, 151643], 1)
        P(torch.zeros((1, 2), dtype=torch.long), torch.zeros((1, self.V)))
        with self.assertRaises(RuntimeError): P(torch.tensor([[0, 0, self.BY[b'[']]]), torch.zeros((1, self.V)))
    def test_no_allowed_token_raises(self):
        torch = self.torch; tb = [None] * 10; P = JS.JsonSlotConstraint(tb, [9], 1)
        with self.assertRaises(RuntimeError): P(torch.zeros((1, 2), dtype=torch.long), torch.zeros((1, 10)))
    def test_padding_ids_beyond_tokenizer_never_allowed(self):
        P = JS.JsonSlotConstraint(self.TB, [151645, 151643], 1)
        for t in (151665, 151700, 151935): self.assertFalse(P.allowed(JS.State(), t))

# ---- identity: jf eval.py (stub backend; same out-dir / identity code as the GPU path) ----
STAGE = ("eval.py", "evalcore.py", "jsonslot.py", "eval_rows.jsonl", "fewshot.json", "RUN-INPUTS.SHA256")
def copy_stage():
    c = tempfile.mkdtemp(prefix="jf-id-")
    for f in STAGE: shutil.copy2(os.path.join(J, f), c)
    return c
def run(c, out, tag, extra=(), pin=None, backend="stub:gold"):
    cmd = [PY, "-B", os.path.join(c, "eval.py"), "--rows", os.path.join(c, "eval_rows.jsonl"), "--expect_manifest_sha", pin or sha(os.path.join(c, "RUN-INPUTS.SHA256")),
           "--out_dir", out, "--tag", tag, "--backend", backend, "--adapter", AD] + list(extra)
    return subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
def dirsha(d): return {f: sha(os.path.join(d, f)) for f in sorted(os.listdir(d))}
JF = ["--max_new_tokens", "256", "--constraint", "json-slot", "--limit", "16"]
class Identity(unittest.TestCase):
    def test_run_pin_changed_and_manifest_lists_jsonslot(self):
        m = JS_m = EC.read_manifest(os.path.join(J, "RUN-INPUTS.SHA256"))
        self.assertEqual(set(m), {"eval_rows.jsonl", "fewshot.json", "eval.py", "evalcore.py", "jsonslot.py"})
        for f, h in m.items(): self.assertEqual(sha(os.path.join(J, f)), h, f)
        self.assertNotEqual(sha(os.path.join(J, "RUN-INPUTS.SHA256")), "0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d")
        for f in ("evalcore.py", "eval_rows.jsonl", "fewshot.json"): self.assertEqual(sha(os.path.join(J, f)), sha(os.path.join(V05, f)), f)
    def test_outT_is_byte_identical_to_pins(self):
        self.assertEqual(dirsha(R03 + "/out-T"), OUT_T)
    def test_launch_into_copy_of_outT_refused_nothing_written(self):
        c = copy_stage(); o = os.path.join(c, "out-T"); shutil.copytree(R03 + "/out-T", o)
        for tag in ("bluebird-v1.0-e2-jf", "bluebird-v1.0-e2"):              # new tag (unknown files) and the old tag (completed run)
            r = run(c, o, tag, JF); self.assertEqual(r.returncode, 7, r.stdout + r.stderr); self.assertIn("REFUSED", r.stdout)
            self.assertEqual(dirsha(o), OUT_T)
    def test_identity_keys_in_cfg(self):
        c = copy_stage(); o = os.path.join(c, "out-T-jf"); r = run(c, o, "bluebird-v1.0-e2-jf", JF); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cfg = json.load(open(os.path.join(o, "run-bluebird-v1.0-e2-jf.json")))["cfg"]
        self.assertEqual((cfg["max_new_tokens"], cfg["constraint"], cfg["constraint_schema"], cfg["schema"]), (256, "json-slot", JS.SCHEMA_ID, "bluebird-eval@jf0.0"))
        self.assertEqual(cfg["constraint_tokenizer_sha256"], JS.TOKENIZER_SHA256); self.assertIn("1536", cfg["budget_rule"])
        self.assertEqual(cfg["inputs_sha256"]["jsonslot.py"], sha(os.path.join(J, "jsonslot.py")))
        rows = {r["id"]: r for r in (json.loads(l) for l in open(os.path.join(c, "eval_rows.jsonl")))}
        P = [json.loads(l) for l in open(os.path.join(o, "predictions-bluebird-v1.0-e2-jf.jsonl"))]; byb = {}
        for p in P: byb.setdefault(p["batch"], []).append(p)
        for k, ps in byb.items(): self.assertEqual({p["max_new"] for p in ps}, {min(256, 1536 - max(rows[p["id"]]["prompt_tokens"] for p in ps))})
        self.assertIn(128, {p["max_new"] for p in P}); self.assertIn(256, {p["max_new"] for p in P})
    def test_changed_identity_refused_7(self):
        c = copy_stage(); o = os.path.join(c, "out-T-jf")
        base = ["--max_new_tokens", "256", "--constraint", "json-slot", "--limit", "16"]
        be = "stub:replay=" + self._torn(c); r = run(c, o, "x", base, backend=be)
        self.assertEqual(r.returncode, 11, r.stdout); self.assertEqual(json.load(open(os.path.join(o, "run-x.json")))["status"], "aborted")
        for chg, key in ((["--max_new_tokens", "320", "--constraint", "json-slot", "--limit", "16"], "max_new_tokens"),
                         (["--max_new_tokens", "256", "--constraint", "none", "--limit", "16"], "constraint"),
                         (["--max_new_tokens", "128", "--constraint", "json-slot", "--limit", "16"], "max_new_tokens"),
                         (["--max_new_tokens", "256", "--constraint", "json-slot", "--limit", "16", "--batch", "4"], "batch")):
            before = dirsha(o); r2 = run(c, o, "x", chg, backend=be); self.assertEqual(r2.returncode, 7, (chg, r2.stdout)); self.assertIn("different config", r2.stdout)
            self.assertIn(f"'{key}'", r2.stdout); self.assertEqual(dirsha(o), before)
        r3 = run(c, o, "x", base, backend=be); self.assertEqual(r3.returncode, 11, r3.stdout)              # the identical line resumes (and hits the same stub gap)
    def _torn(self, c):
        """A started-but-incomplete run: a replay file missing one id makes the stub raise -> exit 11 with status aborted (resumable dir)."""
        rows = [json.loads(l) for l in open(os.path.join(c, "eval_rows.jsonl"))]
        p = os.path.join(c, "rp.jsonl"); open(p, "w").write("".join(json.dumps({"id": r["id"], "raw": json.dumps(r["gold"])}) + "\n" for r in rows[:5])); return p
    def test_old_pin_refused_6(self):
        c = copy_stage(); r = run(c, os.path.join(c, "o"), "x", JF, pin="0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d")
        self.assertEqual(r.returncode, 6, r.stdout)
    def test_jsonslot_tamper_refused_6(self):
        c = copy_stage(); open(os.path.join(c, "jsonslot.py"), "a").write("\n# x\n"); r = run(c, os.path.join(c, "o"), "x", JF); self.assertEqual(r.returncode, 6, r.stdout)
    def test_v05_eval_into_outTjf_refused_7(self):
        c = copy_stage(); o = os.path.join(c, "out-T-jf"); self.assertEqual(run(c, o, "bluebird-v1.0-e2-jf", JF).returncode, 0); before = dirsha(o)
        v = tempfile.mkdtemp(prefix="jf-v05-")
        for f in ("eval.py", "evalcore.py", "eval_rows.jsonl", "fewshot.json", "RUN-INPUTS.SHA256"): shutil.copy2(os.path.join(V05, f), v)
        r = run(v, o, "bluebird-v1.0-e2-jf", ["--limit", "16"]); self.assertEqual(r.returncode, 7, r.stdout); self.assertEqual(dirsha(o), before)
    def test_constraint_on_fewshot_refused_8(self):
        c = copy_stage(); r = run(c, os.path.join(c, "o"), "x", ["--mode", "fewshot", "--fewshot", os.path.join(c, "fewshot.json"), "--constraint", "json-slot", "--limit", "8"])
        self.assertEqual(r.returncode, 8, r.stdout)
    def test_score_py_v05_accepts_new_pin_refuses_old(self):
        c = copy_stage(); o = os.path.join(c, "out-T-jf")
        r = run(c, o, "bluebird-v1.0-e2-jf", ["--max_new_tokens", "256", "--constraint", "json-slot"]); self.assertEqual(r.returncode, 0, r.stdout[-500:])
        adsha = sha(FX + "/adapter/ADAPTER.SHA256"); s = tempfile.mkdtemp(prefix="jf-score-")
        base = [PY, "-B", os.path.join(V05, "score.py"), "--rows", os.path.join(V05, "eval_rows.jsonl"), "--expect_score_manifest_sha", "8c4b3042ba5abf0134b9d0075170ec55585e41092e60e51f411642b59b59bd1e",
                "--expect_adapter_sha", adsha, "--pred", "T=" + os.path.join(o, "predictions-bluebird-v1.0-e2-jf.jsonl"), "--primary", "T", "--allow_stub", "--no_ci"]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        ok = subprocess.run(base + ["--expect_run_manifest_sha", sha(os.path.join(J, "RUN-INPUTS.SHA256")), "--out", os.path.join(s, "a")], capture_output=True, text=True, env=env)
        self.assertEqual(ok.returncode, 0, ok.stderr[-800:])
        bad = subprocess.run(base + ["--expect_run_manifest_sha", "0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d", "--out", os.path.join(s, "b")], capture_output=True, text=True, env=env)
        self.assertEqual(bad.returncode, 15, bad.stderr[-500:])
        self.assertFalse(os.path.exists(os.path.join(V05, "__pycache__")))

class EvalPatch(unittest.TestCase):
    """Source-level checks of the jf0.0 lines that the stub backend cannot reach (GPU branch; the shim replay covers them end to end)."""
    src = open(os.path.join(J, "eval.py")).read()
    def test_budget_rule(self):
        import types
        ns = {"a": types.SimpleNamespace(max_new_tokens=256, mode="zero"), "SEQ": 1536}
        exec(re.search(r"def budget\(chunk, key\):.*?\n(?=[^ ])", self.src + "\nX", re.S).group(0), ns)
        self.assertEqual(ns["budget"]([{"p": 434}, {"p": 624}], "p"), 256); self.assertEqual(ns["budget"]([{"p": 1385}], "p"), 151)
        self.assertEqual(ns["budget"]([{"p": 1408}], "p"), 128)
        ns["a"].mode = "fewshot"; self.assertEqual(ns["budget"]([{"p": 2000}], "p"), 256)
    def test_processor_expectation_and_cap_check(self):
        self.assertIn('probe["logits_processors"] == (["JsonSlotConstraint"] if a.constraint == "json-slot" else [])', self.src)
        self.assertIn('g["max_new_tokens"] == probe.get("cap")', self.src)
        self.assertIn("max_new_tokens=cap", self.src)
    def test_exit9_floor(self):
        self.assertIn("len(ids) + min(a.max_new_tokens, MAX_NEW) > SEQ", self.src)
    def test_diff_is_only_the_jf_lines(self):
        import difflib
        a_ = open(os.path.join(V05, "eval.py")).read().splitlines(); b_ = self.src.splitlines()
        ch = [l for l in difflib.unified_diff(a_, b_, lineterm="", n=0) if l[:1] in "+-" and not l.startswith(("+++", "---"))]
        self.assertLessEqual(len(ch), 80, len(ch))

class Shim(unittest.TestCase):
    """The REAL jf eval.py GPU branch + transformers generate() on CPU (tests/shim_jf.py, tiny Qwen2 teacher-forced to want its out-T text).
    Four whole out-T batches: 282 (slot_mismatch), 287 (bad_span_key), 296 (bad_span_obj), 113 (truncated)."""
    @classmethod
    def setUpClass(cls):
        from evalcore import plan_batches
        rows = [json.loads(l) for l in open(os.path.join(J, "eval_rows.jsonl"), encoding="utf-8")]; bs = plan_batches(rows, "zero", 8)
        cls.T = {p["id"]: p for p in RAWS}; sub = [r for k in (113, 282, 287, 296) for r in bs[k]]; cls.sub = sub
        w = tempfile.mkdtemp(prefix="jf-shim-"); cls.w = w
        for f in ("eval.py", "evalcore.py", "jsonslot.py", "fewshot.json"): shutil.copy(os.path.join(J, f), w)
        open(os.path.join(w, "eval_rows.jsonl"), "w", encoding="utf-8").write("".join(json.dumps(r, sort_keys=True) + "\n" for r in sub))
        open(os.path.join(w, "RUN-INPUTS.SHA256"), "w").write("".join(f"{sha(os.path.join(w, f))}  {f}\n" for f in ("eval_rows.jsonl", "fewshot.json", "eval.py", "evalcore.py", "jsonslot.py")))
        open(os.path.join(w, "script.jsonl"), "w", encoding="utf-8").write("".join(json.dumps({"ids_sha256": r["ids_sha256"], "target": cls.T[r["id"]]["raw"]}) + "\n" for r in sub))
        cls.res = {}
        for name, extra in (("off128", ["--max_new_tokens", "128"]), ("on256", ["--max_new_tokens", "256", "--constraint", "json-slot"])):
            cmd = [os.environ.get("LBE_SHIM_PY", "/workspace/littleblue-fullrun-review/venv/bin/python"), "-B", os.path.join(J, "tests", "shim_jf.py"), os.path.join(w, "eval.py"),
                   "--rows", os.path.join(w, "eval_rows.jsonl"), "--expect_manifest_sha", sha(os.path.join(w, "RUN-INPUTS.SHA256")), "--model", FX + "/model", "--adapter", AD,
                   "--out_dir", os.path.join(w, name), "--tag", "t", "--expect_versions", json.dumps({"peft": "0.21.3", "torch": "2.15.0+cpu"})] + extra
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=w, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "SHIM_SCRIPT": os.path.join(w, "script.jsonl")})
            pp = os.path.join(w, name, "predictions-t.jsonl")
            P = {json.loads(l)["id"]: json.loads(l) for l in open(pp, encoding="utf-8")} if os.path.exists(pp) else {}
            R = json.load(open(os.path.join(w, name, "run-t.json"))) if os.path.exists(os.path.join(w, name, "run-t.json")) else {}
            cls.res[name] = (r, P, R)
    def test_mock_reproduces_outT_without_constraint(self):
        r, P, R = self.res["off128"]; self.assertEqual(r.returncode, 0, r.stdout[-600:] + r.stderr[-600:])
        self.assertEqual({i: p["raw"] for i, p in P.items()}, {x["id"]: self.T[x["id"]]["raw"] for x in self.sub})
        self.assertEqual(R["sessions"][-1]["logits_processors"], [])
    def test_constraint_on(self):
        r, P, R = self.res["on256"]; self.assertEqual(r.returncode, 0, r.stdout[-600:] + r.stderr[-600:])
        self.assertEqual(R["sessions"][-1]["logits_processors"], ["JsonSlotConstraint"]); self.assertEqual(R["sessions"][-1]["merged_generation_config"]["max_new_tokens"], 256)
        self.assertEqual(R["cfg"]["constraint"], "json-slot"); self.assertEqual(R["sessions"][-1]["constraint"]["byte_tokens"], 151643)
        for i, p in P.items():
            self.assertIsNone(parse_strict(p["raw"])[1], (i, p["raw"]))
            if parse_strict(self.T[i]["raw"])[1] is None: self.assertEqual(p["raw"], self.T[i]["raw"], i); self.assertEqual(p["forced"], 0, i)
            else: self.assertGreater(p["forced"], 0, i)
        for i in ("test:SYN-SYNCP000076-MSA1-Q21", "test:SYN-SYNCP000154-MSA1-Q21", "test:SYN-SYNCP000023-MSA1-Q21"):
            if i in P: self.assertEqual(P[i]["raw"], '{"answer": "The Customer turned the terms down.", "spans": {}}')
        self.assertIn("{S2}", P["test:SYN-SYNCP000174-MSA1-Q29"]["raw"]); self.assertEqual(list(json.loads(P["test:SYN-SYNCP000174-MSA1-Q29"]["raw"])["spans"]), ["S2"])
if __name__ == "__main__": unittest.main()
