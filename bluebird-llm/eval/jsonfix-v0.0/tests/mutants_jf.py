# jf0.0 mutation run (box). Each mutant edits ONE line of jsonslot.py or eval.py in a temp copy of the stage, re-issues that copy's
# RUN-INPUTS.SHA256 (so a manifest mismatch never kills a mutant by itself), runs the fast classes, then (if it survived) the Shim class.
# Killed = any test fails or errors. Usage: PYTHONDONTWRITEBYTECODE=1 <review venv>/bin/python -B tests/mutants_jf.py <out.jsonl>
import hashlib, json, os, shutil, subprocess, sys, tempfile, time
J = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = sys.executable
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
M = [
 ("J01 control bytes allowed in strings", "jsonslot.py", "                if b < 0x20: return False\n", "                if False: return False\n"),
 ("J02 slot set ignored (always empty)", "jsonslot.py", "            self.left = frozenset(m[1:-1] for m in SLOT.findall(ans));", "            self.left = frozenset();"),
 ("J03 any escape letter", "jsonslot.py", "                elif b in _ESC: self.esc = 0\n", "                elif True: self.esc = 0\n"),
 ("J04 \\u hex not checked", "jsonslot.py", "                if b not in _HEX: return False\n", "                pass\n"),
 ("J05 bytes allowed after the close", "jsonslot.py", "        return False                                          # 'D'", "        return True                                           # 'D'"),
 ("J06 duplicate span key allowed", "jsonslot.py", "k = done[0]; self.left = self.left - {k};", "k = done[0]; self.left = self.left;"),
 ("J07 spans may close early", "jsonslot.py", "            if self.left: self._lit(b\", \")\n", "            if False: self._lit(b\", \")\n"),
 ("J08 any key accepted", "jsonslot.py", "            if not full: return False\n", "            if not full: self.cand = c; return True\n"),
 ("J09 stop allowed before the object is complete", "jsonslot.py", "        if t in self.stop: return st.done()\n", "        if t in self.stop: return True\n"),
 ("J10 special/added tokens allowed", "jsonslot.py", "        if b is None or st.done(): return False\n", "        if st.done(): return False\n"),
 ("J11 fallback takes the LOWEST score", "jsonslot.py", "order = torch.sort(scores[i], descending=True, stable=True).indices", "order = torch.sort(scores[i], descending=False, stable=True).indices"),
 ("J12 forced not counted", "jsonslot.py", "                self.forced[i] += 1\n", "                pass\n"),
 ("J13 finished rows still constrained", "jsonslot.py", "            if self.fin[i]: keep.append(i); continue\n", "            if False: keep.append(i); continue\n"),
 ("J14 stop-before-complete not detected", "jsonslot.py", "                    if not self.states[i].done(): raise RuntimeError", "                    if False: raise RuntimeError"),
 ("J15 disallowed fed-back token not detected", "jsonslot.py", "                if not self.states[i].feed_bytes(self.tb[t] or b\"\\xff\\xff\"): raise", "                if False: raise"),
 ("J16 tokenizer sha not checked", "jsonslot.py", "    if h != TOKENIZER_SHA256: raise ValueError", "    if False: raise ValueError"),
 ("J17 added tokens keep bytes (equivalent: not in model.vocab)", "jsonslot.py", "        if a[\"id\"] < vocab_size: tb[a[\"id\"]] = None\n", "        pass\n"),
 ("J18 refusal/empty answer may carry spans", "jsonslot.py", "        if not self.left: self._lit(b\"}}\")             # no slot", "        if False: self._lit(b\"}}\")             # no slot"),
 ("J19 no allowed token -> silently keep argmax", "jsonslot.py", "                if t is None: raise RuntimeError(f\"jsonslot: no allowed token for row {i}\")\n", "                if t is None: t = top[i]\n"),
 ("E01 per-batch clamp removed", "eval.py", "min(a.max_new_tokens, SEQ - max(r[key] for r in chunk))", "a.max_new_tokens"),
 ("E02 constraint not in identity", "eval.py", "\"budget_rule\": BUDGET_RULE, \"constraint\": a.constraint,", "\"budget_rule\": BUDGET_RULE, \"constraint\": None,"),
 ("E03 max_new_tokens not in identity", "eval.py", "           \"max_new_tokens\": a.max_new_tokens, \"batch\": a.batch,", "           \"max_new_tokens\": 0, \"batch\": a.batch,"),
 ("E04 jsonslot.py not integrity-checked", "eval.py", ", os.path.join(HERE, \"jsonslot.py\")] + (", "] + ("),
 ("E05 processor expectation back to []", "eval.py", "== ([\"JsonSlotConstraint\"] if a.constraint == \"json-slot\" else [])}", "== []}"),
 ("E06 exit-9 rule back to max_new_tokens", "eval.py", "len(ids) + min(a.max_new_tokens, MAX_NEW) > SEQ", "len(ids) + a.max_new_tokens > SEQ"),
 ("E07 processor not passed to generate", "eval.py", "extra[\"logits_processor\"] = LogitsProcessorList([proc])", "extra = {}"),
 ("E08 constraint allowed on few-shot", "eval.py", "if a.constraint == \"json-slot\" and a.mode != \"zero\": abort(8,", "if False: abort(8,"),
 ("E09 merged cap not checked", "eval.py", "\"max_new_tokens\": g[\"max_new_tokens\"] == probe.get(\"cap\"),", "\"max_new_tokens\": True,"),
 ("E10 schema tag unchanged from v0.5", "eval.py", "\"schema\": \"bluebird-eval@jf0.0\",", "\"schema\": \"bluebird-eval@0.2\","),
 ("E11 forced counts not written", "eval.py", "                gen.forced = list(proc.forced)\n", "                pass\n"),
]
FAST = ["tests.test_jf.Automaton", "tests.test_jf.Vocab", "tests.test_jf.Proc", "tests.test_jf.Identity", "tests.test_jf.EvalPatch"]
out = open(sys.argv[1], "w"); tally = {"killed": 0, "survived": 0}
for name, f, old, new in M:
    c = tempfile.mkdtemp(prefix="jf-mut-")
    for x in ("eval.py", "evalcore.py", "jsonslot.py", "eval_rows.jsonl", "fewshot.json"): shutil.copy2(os.path.join(J, x), c)
    shutil.copytree(os.path.join(J, "tests"), os.path.join(c, "tests"), ignore=shutil.ignore_patterns("__pycache__"))
    s = open(os.path.join(c, f)).read(); n = s.count(old)
    if n != 1: rec = {"mutant": name, "error": f"anchor found {n} times"}; out.write(json.dumps(rec) + "\n"); print(rec, flush=True); continue
    open(os.path.join(c, f), "w").write(s.replace(old, new))
    open(os.path.join(c, "RUN-INPUTS.SHA256"), "w").write("".join(f"{sha(os.path.join(c, x))}  {x}\n" for x in ("eval_rows.jsonl", "fewshot.json", "eval.py", "evalcore.py", "jsonslot.py")))
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}; t0 = time.time()
    r = subprocess.run([PY, "-B", "-W", "ignore", "-m", "unittest", "-f"] + FAST, capture_output=True, text=True, cwd=c, env=env); stage = "fast"
    if r.returncode == 0: r = subprocess.run([PY, "-B", "-W", "ignore", "-m", "unittest", "-f", "tests.test_jf.Shim"], capture_output=True, text=True, cwd=c, env=env); stage = "shim"
    killed = r.returncode != 0
    by = [l.split("(")[0].replace("FAIL: ", "").replace("ERROR: ", "").strip() for l in r.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    rec = {"mutant": name, "file": f, "killed": killed, "stage": stage, "by": by[:3], "sec": round(time.time() - t0, 1)}
    tally["killed" if killed else "survived"] += 1; out.write(json.dumps(rec) + "\n"); out.flush(); print(json.dumps(rec), flush=True)
    shutil.rmtree(c, ignore_errors=True)
out.write(json.dumps({"tally": tally, "mutants": len(M)}) + "\n"); print(tally)
