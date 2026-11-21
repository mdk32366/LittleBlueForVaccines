# DIFF: v0.5 eval.py -> jf0.0 eval.py (ORDER-bluebird-json-fix@0.0)

- v0.5 `/workspace/littleblue-eval-v0.5/eval.py` sha256 `429751f6b8e05f8cba63ca1e858f883ef71022d8cdb2aee736200d71b7ffdb25`
- jf0.0 `eval.py` sha256 `772189be5b30ea03dccef4f49b77260d91b17f1d52ab1ddfa6945621082d6874`
- `jsonslot.py` is new (sha256 `38c79c58be1049f04ac18f6973db5e54c7ddaf5a01b62d4d870d56a08612f956`), not diffed; `evalcore.py`, `eval_rows.jsonl`, `fewshot.json` are byte-identical to v0.5.
- Checked by `tests/test_jf.py` EvalPatch.test_diff_is_only_the_jf_lines.

```diff
--- v0.5/eval.py
+++ jf0.0/eval.py
@@ -1,4 +1,7 @@
 # Bluebird v1.0 post-run eval runner @0.2 (ORDER-bluebird-eval@0.2 §d, §e). Generates predictions only; scoring is score.py (box, CPU).
+# JSON-fix @jf0.0 (ORDER-bluebird-json-fix@0.0): + --constraint json-slot (jsonslot.py, in-tree, greedy-exact schema masking) and the zero-shot
+#   per-batch budget min(--max_new_tokens, SEQ - longest prompt in the batch), so no row runs past the 1536 training length; both are in
+#   the run identity (cfg). Every other line is the v0.5 eval.py (sha 429751f6...); the diff is DIFF-v0.5-to-jf0.0.md.
 # GPU path: 4-bit nf4 base (same quant config as train.py) + optional LoRA adapter, greedy, fixed max_new_tokens, seed 562.
 # Stub path (--backend stub:<mode>): no torch, no weights; box CPU tests only. Shares the batch/resume/write code with the GPU path.
 # Exit codes. Every code except 0, 2 and 7 writes a NEW <out_dir>/ABORT-<n>.json (never overwritten) and, if the run json exists,
@@ -18,7 +21,8 @@
 #   14 generation finished but predictions are not exactly the planned ids (should not happen)
 import argparse, atexit, glob, hashlib, json, os, re, sys, time, traceback
 HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
-from evalcore import SEQ, MAX_NEW, messages, plan_batches, content_sha256, file_sha256 as sha, read_manifest
+from evalcore import SEQ, MAX_NEW, messages, plan_batches, content_sha256, file_sha256 as sha, read_manifest, parse_strict
+import jsonslot
 
 TRAIN_VERSIONS = {"torch": "2.11.0+cu128", "bitsandbytes": "0.50.2", "peft": "0.21.2"}   # train json (run order §g); transformers is checked separately:
 VERIFIED_TRANSFORMERS = "5.23.0"   # the greedy override was verified on this version only (review I3). Any other installed version (the laptop has
@@ -41,6 +45,7 @@
 a.add_argument("--pin_transformers", default="", help="accept this (unverified) installed transformers version explicitly; must equal the installed one (ruling 8)")
 a.add_argument("--preflight", action="store_true", help="E0b: all checks + load + 1-row generate to read the merged generation config; no predictions")
 a.add_argument("--backend", default="hf", help="hf | stub:<gold|invalid|wrongspan|oldvalue|norefuse|replay=FILE>")
+a.add_argument("--constraint", choices=["none", "json-slot"], default="none", help="jf0.0: json-slot = jsonslot.py schema-constrained greedy decoding")
 a = a.parse_args()
 
 OUT = os.path.abspath(a.out_dir); PRED = os.path.join(OUT, f"predictions-{a.tag}.jsonl"); RUN = os.path.join(OUT, f"run-{a.tag}.json")
@@ -50,6 +55,9 @@
 owns_lock = False
 stale_raw = None                 # bytes of a stale lock this process took over (restored if it never starts a session)
 def now(): return time.strftime("%Y-%m-%d %H:%M:%S")
+BUDGET_RULE = "zero-shot: min(max_new_tokens, SEQ 1536 - longest prompt in the batch); fewshot: max_new_tokens"
+def budget(chunk, key):            # jf0.0: per-batch max_new_tokens (zero-shot rows never run past the training length SEQ)
+    return a.max_new_tokens if a.mode == "fewshot" else min(a.max_new_tokens, SEQ - max(r[key] for r in chunk))
 def wjson(p, obj):               # atomic write
     t = p + ".tmp"
     with open(t, "w") as f: json.dump(obj, f, indent=1, sort_keys=True); f.flush(); os.fsync(f.fileno())
@@ -166,7 +174,7 @@
     msha = sha(mp)
     if msha != a.expect_manifest_sha: abort(6, f"manifest sha256 {msha} != --expect_manifest_sha")
     want = read_manifest(mp)
-    checks = [os.path.abspath(a.rows), os.path.join(HERE, "eval.py"), os.path.join(HERE, "evalcore.py")] + ([os.path.abspath(a.fewshot)] if a.fewshot else [])
+    checks = [os.path.abspath(a.rows), os.path.join(HERE, "eval.py"), os.path.join(HERE, "evalcore.py"), os.path.join(HERE, "jsonslot.py")] + ([os.path.abspath(a.fewshot)] if a.fewshot else [])
     inputs = {}
     for p in checks:
         inputs[os.path.basename(p)] = h = sha(p)
@@ -184,17 +192,20 @@
     if a.model:                                            # review L7: every top-level file of the base model dir (config, generation_config, weights, tokenizer)
         for f in sorted(os.listdir(a.model)):
             if os.path.isfile(os.path.join(a.model, f)): model_files[f] = sha(os.path.join(a.model, f))
-    cfg = {"schema": "bluebird-eval@0.2", "tag": a.tag, "mode": a.mode, "rows_sha256": inputs[os.path.basename(a.rows)], "manifest_sha256": msha,
+    cfg = {"tag": a.tag, "mode": a.mode, "rows_sha256": inputs[os.path.basename(a.rows)], "manifest_sha256": msha,
            "run_manifest_lines": open(mp, "rb").read().decode("utf-8"),
            "inputs_sha256": inputs, "model_path": os.path.abspath(a.model) if a.model else None, "model_files_sha256": model_files,
            "adapter_path": os.path.abspath(a.adapter) if a.adapter else None, "adapter_manifest_sha256": ad_sha, "adapter_files_sha256": ad_files,
-           "max_new_tokens": a.max_new_tokens, "batch": a.batch, "kinds": a.kinds, "limit": a.limit, "backend": a.backend, "seed": 562, "decoding": "greedy"}
+           "max_new_tokens": a.max_new_tokens, "batch": a.batch, "kinds": a.kinds, "limit": a.limit, "backend": a.backend, "seed": 562, "decoding": "greedy",
+           "schema": "bluebird-eval@jf0.0", "budget_rule": BUDGET_RULE, "constraint": a.constraint,
+           "constraint_schema": jsonslot.SCHEMA_ID if a.constraint == "json-slot" else None, "constraint_tokenizer_sha256": jsonslot.TOKENIZER_SHA256 if a.constraint == "json-slot" else None}
     if prev is not None and prev.get("cfg") != cfg:        # review M1: model / adapter / inputs are part of the identity
         diff = sorted(k for k in set(cfg) | set(prev.get("cfg", {})) if cfg.get(k) != prev.get("cfg", {}).get(k))
         refuse(f"out_dir holds a run with a different config (differs in: {diff}); use a fresh out_dir")
     rows = [json.loads(l) for l in open(a.rows, encoding="utf-8")]
     fs = json.load(open(a.fewshot, encoding="utf-8")) if a.mode == "fewshot" else None
-    batches = plan_batches(rows, a.mode, a.batch, a.kinds, a.limit)
+    batches = plan_batches(rows, a.mode, a.batch, a.kinds, a.limit); PKEY = "fs_prompt_tokens" if a.mode == "fewshot" else "prompt_tokens"
+    if a.constraint == "json-slot" and a.mode != "zero": abort(8, "--constraint json-slot is for the zero-shot (T) run only")
     if a.preflight: batches = [[min((r for r in rows if r["kind"] == "test"), key=lambda r: (r["prompt_tokens"], r["id"]))]]
     planned = [r["id"] for b in batches for r in b]; bidx = {i: k for k, b in enumerate(batches) for i in (r["id"] for r in b)}
     session = {"started": now(), "argv": sys.argv[1:], "pid": os.getpid(), "repairs": [stale] if stale else []}
@@ -252,9 +263,16 @@
             n_want, h_want = (r["fs_prompt_tokens"], r["fs_ids_sha256"]) if fs else (r["prompt_tokens"], r["ids_sha256"])
             if len(ids) != n_want: abort(4, f"tokenizer_mismatch count {r['id']} {len(ids)}!={n_want}")
             if hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest() != h_want: abort(4, f"tokenizer_mismatch ids {r['id']}")
-            if not fs and len(ids) + a.max_new_tokens > SEQ: abort(9, f"prompt_too_long {r['id']} {len(ids)}+{a.max_new_tokens} > {SEQ}")
+            if not fs and len(ids) + min(a.max_new_tokens, MAX_NEW) > SEQ: abort(9, f"prompt_too_long {r['id']} {len(ids)}+{min(a.max_new_tokens, MAX_NEW)} > {SEQ}")   # jf0.0: budget is clamped per batch, never below min(max_new, 128)
             enc[r["id"]] = ids
         stop = [tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")]
+        TB = None
+        if a.constraint == "json-slot":                    # jf0.0: byte table from the model dir's own tokenizer.json, sha-pinned (exit 6 otherwise)
+            tjp = os.path.join(a.model, "tokenizer.json")
+            if model_files.get("tokenizer.json") != jsonslot.TOKENIZER_SHA256: abort(6, f"constraint: {tjp} sha256 != pinned {jsonslot.TOKENIZER_SHA256}")
+            TB = jsonslot.token_bytes_from_tokenizer_json(tjp, max(len(tok), max(stop) + 1))
+            session["constraint"] = {"schema": jsonslot.SCHEMA_ID, "tokenizer_sha256": jsonslot.TOKENIZER_SHA256, "byte_tokens": sum(b is not None for b in TB),
+                                     "table_size": len(TB), "stop_ids": stop}
         try:
             q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
             m = AutoModelForCausalLM.from_pretrained(a.model, quantization_config=q, attn_implementation="sdpa", dtype=torch.bfloat16, device_map={"": 0})
@@ -282,19 +300,25 @@
             want = {"do_sample": g["do_sample"] is False, "num_beams": g["num_beams"] == 1, "temperature": g["temperature"] in (None, 1.0),
                     "top_p": g["top_p"] in (None, 1.0), "top_k": g["top_k"] in (None, 0), "min_p": g["min_p"] is None, "typical_p": g["typical_p"] in (None, 1.0),
                     "repetition_penalty": g["repetition_penalty"] in (None, 1.0), "no_repeat_ngram_size": g["no_repeat_ngram_size"] in (None, 0),
-                    "max_new_tokens": g["max_new_tokens"] == a.max_new_tokens, "min_new_tokens": g["min_new_tokens"] in (None, 0),
+                    "max_new_tokens": g["max_new_tokens"] == probe.get("cap"), "min_new_tokens": g["min_new_tokens"] in (None, 0),
                     "eos_token_id": eos == set(stop), "pad_token_id": g["pad_token_id"] == tok.pad_token_id, "num_return_sequences": g["num_return_sequences"] in (None, 1),
                     "bad_words_ids": not g["bad_words_ids"], "suppress_tokens": not g["suppress_tokens"], "begin_suppress_tokens": not g["begin_suppress_tokens"],
-                    "logits_processors": probe["logits_processors"] == []}
+                    "logits_processors": probe["logits_processors"] == (["JsonSlotConstraint"] if a.constraint == "json-slot" else [])}
             return [k for k, ok in want.items() if not ok]
         def gen(chunk):
-            L = max(len(enc[r["id"]]) for r in chunk)
+            L = max(len(enc[r["id"]]) for r in chunk); cap = budget(chunk, PKEY)
+            if not fs and L != max(r["prompt_tokens"] for r in chunk): abort(4, "tokenizer_mismatch batch length")
             ids = torch.tensor([[tok.pad_token_id] * (L - len(enc[r["id"]])) + enc[r["id"]] for r in chunk], device="cuda")
             att = torch.tensor([[0] * (L - len(enc[r["id"]])) + [1] * len(enc[r["id"]]) for r in chunk], device="cuda")
+            extra = {}
+            if TB is not None:
+                from transformers import LogitsProcessorList
+                proc = jsonslot.JsonSlotConstraint(TB, stop, len(chunk)); extra["logits_processor"] = LogitsProcessorList([proc])
+            probe.setdefault("cap", cap)
             with torch.no_grad():
-                g = m.generate(input_ids=ids, attention_mask=att, do_sample=False, num_beams=1, max_new_tokens=a.max_new_tokens,
+                g = m.generate(input_ids=ids, attention_mask=att, do_sample=False, num_beams=1, max_new_tokens=cap,
                                repetition_penalty=1.0, temperature=None, top_p=None, top_k=None,   # override Qwen generation_config (rep 1.05, sampling)
-                               eos_token_id=stop, pad_token_id=tok.pad_token_id)
+                               eos_token_id=stop, pad_token_id=tok.pad_token_id, **extra)
             if "checked" not in probe:                     # first generate of every session: verify what generate() actually used (review I3, E0 check)
                 bad = decoding_problems(); session["merged_generation_config"] = probe.get("merged"); session["logits_processors"] = probe.get("logits_processors")
                 print("MERGED_GENERATION_CONFIG", json.dumps({"merged": probe.get("merged"), "logits_processors": probe.get("logits_processors")}), flush=True)
@@ -304,6 +328,10 @@
             for seq in g[:, L:].tolist():
                 n = next((i for i, t in enumerate(seq) if t in stop), None); body = seq[:n] if n is not None else seq
                 out.append((tok.decode(body, skip_special_tokens=False), len(body), n is None))   # review L1: stray specials stay visible
+            if TB is not None:                             # jf0.0 self-check: every row that stopped is strict-valid, else the constraint is broken
+                gen.forced = list(proc.forced)
+                bad = [r["id"] for r, (raw, nt, hm) in zip(chunk, out) if not hm and parse_strict(raw)[1] is not None]
+                if bad: abort(13, f"constraint: rows stopped but not strict-valid: {bad[:5]}")
             return out
         def after_batch(done):
             pk = torch.cuda.max_memory_allocated()
@@ -364,9 +392,10 @@
     try:
         with open(PRED, "a", encoding="utf-8") as out:
             for j, k in enumerate(todo):
-                chunk = batches[k]; t0 = time.time(); res = gen(chunk); dt = (time.time() - t0) / len(chunk)
-                out.write("".join(json.dumps({"id": r["id"], "raw": raw, "new_tokens": nt, "hit_max": hm, "sec": round(dt, 3), "batch": k}) + "\n"
-                                  for r, (raw, nt, hm) in zip(chunk, res)))
+                chunk = batches[k]; t0 = time.time(); res = gen(chunk); dt = (time.time() - t0) / len(chunk); cap = budget(chunk, PKEY)
+                forced = getattr(gen, "forced", None) or [None] * len(chunk)
+                out.write("".join(json.dumps({"id": r["id"], "raw": raw, "new_tokens": nt, "hit_max": hm, "sec": round(dt, 3), "batch": k, "max_new": cap, "forced": fz}) + "\n"
+                                  for r, (raw, nt, hm), fz in zip(chunk, res, forced)))
                 out.flush(); os.fsync(out.fileno())
                 pk = after_batch(sum(len(batches[x]) for x in todo[:j + 1]))
                 print(json.dumps({"batch": k, "done_batches": len(batches) - len(todo) + j + 1, "of": len(batches), "sec_per_row": round(dt, 3), "peak_alloc": pk}), flush=True)
```
