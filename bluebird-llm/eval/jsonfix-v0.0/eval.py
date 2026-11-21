# Bluebird v1.0 post-run eval runner @0.2 (ORDER-bluebird-eval@0.2 §d, §e). Generates predictions only; scoring is score.py (box, CPU).
# JSON-fix @jf0.0 (ORDER-bluebird-json-fix@0.0): + --constraint json-slot (jsonslot.py, in-tree, greedy-exact schema masking) and the zero-shot
#   per-batch budget min(--max_new_tokens, SEQ - longest prompt in the batch), so no row runs past the 1536 training length; both are in
#   the run identity (cfg). Every other line is the v0.5 eval.py (sha 429751f6...); the diff is DIFF-v0.5-to-jf0.0.md.
# GPU path: 4-bit nf4 base (same quant config as train.py) + optional LoRA adapter, greedy, fixed max_new_tokens, seed 562.
# Stub path (--backend stub:<mode>): no torch, no weights; box CPU tests only. Shares the batch/resume/write code with the GPU path.
# Exit codes. Every code except 0, 2 and 7 writes a NEW <out_dir>/ABORT-<n>.json (never overwritten) and, if the run json exists,
# sets its status to "aborted". 7 writes NOTHING into out_dir (reason on stdout).
# @0.2 (review N5): single runner per out_dir: <out_dir>/eval.lock (O_EXCL; pid, start time) is held for the whole run and removed on
# every exit path except a hard kill. A launch while the lock's pid is alive (or, lock absent, status running and sessions[-1].pid alive)
# is refused with 7 and writes nothing. A lock whose pid is dead is stale: taken over and recorded in session.repairs.
# Invocation/integrity errors (exit 6, 8) in an out_dir that already holds a run json write NOTHING there (no ABORT-n, run json
# untouched; reason on stdout only), so a mistyped launch never changes what E6 reads.
#   0 complete | 2 argparse usage error (out_dir unknown, no marker) | 3 peak_alloc > --peak_limit | 4 tokenizer mismatch (count or ids sha256)
#   5 CUDA OOM | 6 sha256 mismatch (manifest pin, rows / fewshot / scripts vs manifest, adapter vs ADAPTER.SHA256)
#   7 refused: out_dir holds a completed run, a run with a different config/model/adapter/library versions, predictions without a
#     run json, or unknown files | 8 bad invocation (e.g. --mode fewshot without --fewshot, missing file) | 9 zero-shot prompt + max_new > 1536
#   10 no CUDA, or GPU free memory < --min_free at start | 11 any other unhandled exception (cause + traceback in ABORT)
#   12 predictions file corrupt beyond a torn last line (bad line, duplicate or unplanned id) | 13 decoding/version check failed:
#     library versions != --expect_versions, transformers != VERIFIED_TRANSFORMERS without a matching --pin_transformers, or the generation config generate() actually merged is not plain greedy, or it cannot be read
#   14 generation finished but predictions are not exactly the planned ids (should not happen)
import argparse, atexit, glob, hashlib, json, os, re, sys, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from evalcore import SEQ, MAX_NEW, messages, plan_batches, content_sha256, file_sha256 as sha, read_manifest, parse_strict
import jsonslot

TRAIN_VERSIONS = {"torch": "2.11.0+cu128", "bitsandbytes": "0.50.2", "peft": "0.21.2"}   # train json (run order §g); transformers is checked separately:
VERIFIED_TRANSFORMERS = "5.23.0"   # the greedy override was verified on this version only (review I3). Any other installed version (the laptop has
                                   # 5.22.2, per the train json) stops with exit 13 unless the run pins it explicitly with --pin_transformers <installed>.
GEN_FIELDS = ("do_sample", "num_beams", "temperature", "top_p", "top_k", "min_p", "typical_p", "repetition_penalty", "no_repeat_ngram_size",
              "max_new_tokens", "min_new_tokens", "eos_token_id", "pad_token_id", "num_return_sequences", "bad_words_ids", "suppress_tokens", "begin_suppress_tokens")

a = argparse.ArgumentParser()
a.add_argument("--rows", required=True); a.add_argument("--out_dir", required=True); a.add_argument("--tag", required=True)
a.add_argument("--expect_manifest_sha", required=True, help="RUN PIN: sha256 of RUN-INPUTS.SHA256, from the order (review L5, @0.2 N1)")
a.add_argument("--model", default=None); a.add_argument("--adapter", default=None, help="final-adapter dir; omit for the stock base")
a.add_argument("--mode", choices=["zero", "fewshot"], default="zero"); a.add_argument("--fewshot", default=None)
a.add_argument("--manifest", default=None, help="default: RUN-INPUTS.SHA256 next to --rows")
a.add_argument("--max_new_tokens", type=int, default=MAX_NEW); a.add_argument("--batch", type=int, default=8)
a.add_argument("--peak_limit", type=float, default=7.0e9)
a.add_argument("--min_free", type=float, default=7.0e9, help="exit 10 floor, bytes. 7.0e9 is UNVERIFIED until E0b measures the laptop")
a.add_argument("--limit", type=int, default=0, help="smoke: ceil(N/batch) whole batches evenly spaced over the length order")
a.add_argument("--kinds", default=""); a.add_argument("--replay_b1", type=int, default=0, help="smoke only: re-generate the first N rows at batch 1, record diffs")
a.add_argument("--expect_versions", default=json.dumps(TRAIN_VERSIONS), help='JSON {lib: version}; GPU path exits 13 on any mismatch')
a.add_argument("--pin_transformers", default="", help="accept this (unverified) installed transformers version explicitly; must equal the installed one (ruling 8)")
a.add_argument("--preflight", action="store_true", help="E0b: all checks + load + 1-row generate to read the merged generation config; no predictions")
a.add_argument("--backend", default="hf", help="hf | stub:<gold|invalid|wrongspan|oldvalue|norefuse|replay=FILE>")
a.add_argument("--constraint", choices=["none", "json-slot"], default="none", help="jf0.0: json-slot = jsonslot.py schema-constrained greedy decoding")
a = a.parse_args()

OUT = os.path.abspath(a.out_dir); PRED = os.path.join(OUT, f"predictions-{a.tag}.jsonl"); RUN = os.path.join(OUT, f"run-{a.tag}.json")
MF = os.path.join(OUT, "EVAL.SHA256"); LOCK = os.path.join(OUT, "eval.lock"); ABORT_RE = re.compile(r"^ABORT-\d+\.json$"); PREFL_RE = re.compile(r"^PREFLIGHT-.+-\d+\.json$")
meta = None                      # run json once written
RUN_DIR = False                  # out_dir held a run json at start (N5: no invocation/integrity ABORT is written there)
owns_lock = False
stale_raw = None                 # bytes of a stale lock this process took over (restored if it never starts a session)
def now(): return time.strftime("%Y-%m-%d %H:%M:%S")
BUDGET_RULE = "zero-shot: min(max_new_tokens, SEQ 1536 - longest prompt in the batch); fewshot: max_new_tokens"
def budget(chunk, key):            # jf0.0: per-batch max_new_tokens (zero-shot rows never run past the training length SEQ)
    return a.max_new_tokens if a.mode == "fewshot" else min(a.max_new_tokens, SEQ - max(r[key] for r in chunk))
def wjson(p, obj):               # atomic write
    t = p + ".tmp"
    with open(t, "w") as f: json.dump(obj, f, indent=1, sort_keys=True); f.flush(); os.fsync(f.fileno())
    os.replace(t, p)
def next_numbered(prefix):
    n = 1 + max([int(m.group(1)) for f in os.listdir(OUT) for m in [re.match(re.escape(prefix) + r"(\d+)\.json$", f)] if m] or [0])
    while True:
        p = os.path.join(OUT, f"{prefix}{n}.json")
        try: return p, os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError: n += 1
def pid_alive(pid):
    """True if a process with this pid exists. Never signals it (on Windows os.kill would TERMINATE it, so it is not used there)."""
    if not isinstance(pid, int) or pid <= 0: return False
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32; h = k.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h: return ctypes.GetLastError() == 5                                 # access denied: it exists
        code = ctypes.c_ulong(); ok = k.GetExitCodeProcess(h, ctypes.byref(code)); k.CloseHandle(h)
        return bool(ok) and code.value == 259                                       # STILL_ACTIVE
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True
def release_lock():
    """Remove our lock. If we took over a stale lock but never started a session (refused / early exit), put the stale lock back
    byte-identical, so a refused launch leaves the out dir exactly as it found it."""
    global owns_lock
    if not owns_lock: return
    try:
        if json.load(open(LOCK)).get("pid") == os.getpid():
            if stale_raw is not None and meta is None:
                t = LOCK + ".tmp"
                with open(t, "wb") as f: f.write(stale_raw)
                os.replace(t, LOCK)
            else: os.remove(LOCK)
    except Exception: pass
    owns_lock = False
def take_lock():
    """N5: O_EXCL lock; live holder -> refuse 7 (nothing written); dead holder -> stale, taken over. Returns the stale record or None."""
    global owns_lock, stale_raw
    stale = None
    for _ in range(3):
        try:
            os.makedirs(OUT, exist_ok=True); fd = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            try: raw = open(LOCK, "rb").read(); held = json.loads(raw)
            except Exception: raw, held = None, {}
            if pid_alive(held.get("pid")):
                refuse(f"another eval.py holds {LOCK} (pid {held.get('pid')}, started {held.get('started')}, tag {held.get('tag')}); it is "
                       f"still running. If you are certain no eval.py runs (Get-Process -Id {held.get('pid')}), delete eval.lock and relaunch")
            if not held:                                                            # torn/empty lock (crash while writing it)
                try:
                    if time.time() - os.path.getmtime(LOCK) < 5: time.sleep(5); continue
                except FileNotFoundError: continue
            stale = {"stale_lock": held or "unreadable", "time": now()}; stale_raw = raw if raw is not None else b""
            try: os.remove(LOCK)
            except FileNotFoundError: pass
            continue
        with os.fdopen(fd, "w") as f:
            json.dump({"pid": os.getpid(), "started": now(), "tag": a.tag}, f); f.flush(); os.fsync(f.fileno())
        owns_lock = True; atexit.register(release_lock); return stale
    refuse(f"could not take {LOCK} (contention)")
def abort(code, why, **extra):
    """Never overwrites: writes ABORT-<n>.json with the next free n. Marks the run json aborted if it exists."""
    rec = {"tag": a.tag, "exit": code, "abort": why, "time": now(), "pid": os.getpid(), **extra}
    if code in (6, 8) and RUN_DIR and meta is None:                                 # N5: invocation/integrity error against a run dir
        print("ABORT", code, why, "(NOT recorded in out_dir: it holds a run; run json and markers untouched)", flush=True); sys.exit(code)
    try:
        os.makedirs(OUT, exist_ok=True); p, fd = next_numbered("ABORT-")
        with os.fdopen(fd, "w") as f: json.dump(rec, f, indent=1, sort_keys=True)
        rec["file"] = os.path.basename(p)
        if meta is not None:
            meta["status"] = "aborted"; meta["sessions"][-1].update(ended=now(), exit=code, abort_file=rec["file"]); wjson(RUN, meta)
    except Exception as e:
        print("ABORT marker could not be written:", repr(e), flush=True)
    print("ABORT", code, why, flush=True); sys.exit(code)
def refuse(why):
    """exit 7: writes nothing into out_dir (a lock this process took is removed again)."""
    print("REFUSED (exit 7, nothing written):", why, flush=True); sys.exit(7)

def main():
    global meta, RUN_DIR
    # 1. out_dir state, before anything is written (review H4, M4)
    prev = None; prev_raw = None
    if os.path.isdir(OUT):
        names = sorted(os.listdir(OUT))
        unknown = [f for f in names if f not in (os.path.basename(PRED), os.path.basename(RUN), "EVAL.SHA256", "eval.lock")
                   and not ABORT_RE.match(f) and not PREFL_RE.match(f)]
        if unknown: refuse(f"out_dir holds files this run did not write: {unknown[:5]}; use a fresh out_dir")
        if a.preflight and (os.path.exists(RUN) or os.path.exists(PRED)): refuse("--preflight needs an out_dir without a run")
        if os.path.exists(RUN):
            try: prev_raw = open(RUN, "rb").read(); prev = json.loads(prev_raw)
            except Exception as e: refuse(f"run json unreadable ({e!r})")
            if prev.get("status") == "complete": refuse("out_dir holds a COMPLETED run; nothing to do. Use a fresh out_dir for a new run")
        elif os.path.exists(PRED): refuse("predictions without a run json (unknown provenance); use a fresh out_dir")
        # only ABORT-<n>.json left (early abort before the run json existed): a clean start, old markers kept
        RUN_DIR = prev is not None
        if prev is not None and prev.get("status") == "running" and not os.path.exists(LOCK):
            lp = (prev.get("sessions") or [{}])[-1].get("pid")
            if pid_alive(lp) and lp != os.getpid(): refuse(f"run json says running and its last session's pid {lp} is alive (no lock); not touching it")
    # 1b. single runner (N5): before anything else is written
    stale = take_lock()
    if (open(RUN, "rb").read() if os.path.exists(RUN) else None) != prev_raw or (prev is None and os.path.exists(PRED)):
        refuse("out_dir changed between the state check and taking the lock (another eval.py ran); relaunch to re-check")
    # 0. invocation (checked after the state check, so a mistyped rerun never writes into a completed run)
    if a.mode == "fewshot" and not a.fewshot: abort(8, "--mode fewshot needs --fewshot")
    if a.replay_b1 and not a.limit: abort(8, "--replay_b1 is for smoke runs (--limit) only")
    # 2. integrity (review L5: the manifest itself is pinned on the command line)
    for p in [a.rows] + ([a.fewshot] if a.fewshot else []) + ([a.model] if a.model else []) + ([a.adapter] if a.adapter else []):
        if not os.path.exists(p): abort(8, f"missing input: {p}")
    # @0.2 (review N1): the run pin is RUN-INPUTS.SHA256 (rows, fewshot, eval.py, evalcore.py only), not the whole-stage audit manifest;
    # its exact text is recorded in the run json so score.py verifies the run against what the run itself used.
    mp = a.manifest or os.path.join(os.path.dirname(os.path.abspath(a.rows)), "RUN-INPUTS.SHA256")
    if not os.path.exists(mp): abort(8, f"missing manifest: {mp}")
    msha = sha(mp)
    if msha != a.expect_manifest_sha: abort(6, f"manifest sha256 {msha} != --expect_manifest_sha")
    want = read_manifest(mp)
    checks = [os.path.abspath(a.rows), os.path.join(HERE, "eval.py"), os.path.join(HERE, "evalcore.py"), os.path.join(HERE, "jsonslot.py")] + ([os.path.abspath(a.fewshot)] if a.fewshot else [])
    inputs = {}
    for p in checks:
        inputs[os.path.basename(p)] = h = sha(p)
        if want.get(os.path.basename(p)) != h: abort(6, f"{os.path.basename(p)} sha256 != manifest")
    ad_sha = None; ad_files = {}
    if a.adapter:
        ad = os.path.dirname(os.path.abspath(a.adapter)); am = os.path.join(ad, "ADAPTER.SHA256")
        if not os.path.exists(am): abort(8, f"missing {am}")
        for ln in open(am):
            if not ln.strip(): continue
            h, f = ln.split(); f = f.lstrip("*"); ad_files[f] = h
            if not os.path.exists(os.path.join(ad, f)) or sha(os.path.join(ad, f)) != h: abort(6, f"adapter {f} sha256 != ADAPTER.SHA256")
        ad_sha = sha(am)
    model_files = {}
    if a.model:                                            # review L7: every top-level file of the base model dir (config, generation_config, weights, tokenizer)
        for f in sorted(os.listdir(a.model)):
            if os.path.isfile(os.path.join(a.model, f)): model_files[f] = sha(os.path.join(a.model, f))
    cfg = {"tag": a.tag, "mode": a.mode, "rows_sha256": inputs[os.path.basename(a.rows)], "manifest_sha256": msha,
           "run_manifest_lines": open(mp, "rb").read().decode("utf-8"),
           "inputs_sha256": inputs, "model_path": os.path.abspath(a.model) if a.model else None, "model_files_sha256": model_files,
           "adapter_path": os.path.abspath(a.adapter) if a.adapter else None, "adapter_manifest_sha256": ad_sha, "adapter_files_sha256": ad_files,
           "max_new_tokens": a.max_new_tokens, "batch": a.batch, "kinds": a.kinds, "limit": a.limit, "backend": a.backend, "seed": 562, "decoding": "greedy",
           "schema": "bluebird-eval@jf0.0", "budget_rule": BUDGET_RULE, "constraint": a.constraint,
           "constraint_schema": jsonslot.SCHEMA_ID if a.constraint == "json-slot" else None, "constraint_tokenizer_sha256": jsonslot.TOKENIZER_SHA256 if a.constraint == "json-slot" else None}
    if prev is not None and prev.get("cfg") != cfg:        # review M1: model / adapter / inputs are part of the identity
        diff = sorted(k for k in set(cfg) | set(prev.get("cfg", {})) if cfg.get(k) != prev.get("cfg", {}).get(k))
        refuse(f"out_dir holds a run with a different config (differs in: {diff}); use a fresh out_dir")
    rows = [json.loads(l) for l in open(a.rows, encoding="utf-8")]
    fs = json.load(open(a.fewshot, encoding="utf-8")) if a.mode == "fewshot" else None
    batches = plan_batches(rows, a.mode, a.batch, a.kinds, a.limit); PKEY = "fs_prompt_tokens" if a.mode == "fewshot" else "prompt_tokens"
    if a.constraint == "json-slot" and a.mode != "zero": abort(8, "--constraint json-slot is for the zero-shot (T) run only")
    if a.preflight: batches = [[min((r for r in rows if r["kind"] == "test"), key=lambda r: (r["prompt_tokens"], r["id"]))]]
    planned = [r["id"] for b in batches for r in b]; bidx = {i: k for k, b in enumerate(batches) for i in (r["id"] for r in b)}
    session = {"started": now(), "argv": sys.argv[1:], "pid": os.getpid(), "repairs": [stale] if stale else []}
    # 3. backend setup
    if a.backend.startswith("stub:"):
        smode = a.backend.split(":", 1)[1]; session["versions"] = {"backend": a.backend}
        replay = {}
        if smode.startswith("replay="):                    # tests/sim only: outputs read from a {id, raw} jsonl
            replay = {o["id"]: o["raw"] for o in (json.loads(l) for l in open(smode[7:], encoding="utf-8"))}
        def gen(chunk):
            out = []
            for r in chunk:
                if replay: out.append((replay[r["id"]], None, False)); continue
                g = json.loads(json.dumps(r["gold"]))
                if smode == "invalid": out.append(('{"answer": "' + g["answer"], None, False)); continue
                if smode == "wrongspan" and g["spans"]:
                    for v in g["spans"].values(): v["text"] = v["text"] + " 9zz"; v["anchor"] = v["anchor"].split("#")[0] + "#99"
                if smode == "oldvalue" and r["kind"] == "cf":
                    for v in g["spans"].values(): v["text"] = r["old_value"]
                if smode == "norefuse" and r["kind"] == "ar":
                    g = {"answer": "Value: {S1}.", "spans": {"S1": {"anchor": r["removed"][0], "text": r["old_value"][0]}}}
                out.append((json.dumps(g), None, False))
            return out
        after_batch = lambda done: None
    else:
        import torch, transformers, peft, bitsandbytes as bnb
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        torch.manual_seed(562)
        vers = {"torch": torch.__version__, "cuda": torch.version.cuda, "bitsandbytes": bnb.__version__, "transformers": transformers.__version__, "peft": peft.__version__}
        session["versions"] = vers
        if prev is not None and prev["sessions"] and prev["sessions"][0].get("versions") != vers:
            refuse(f"library versions differ from this run's first session: {prev['sessions'][0].get('versions')} vs {vers}")
        expect = json.loads(a.expect_versions)
        bad = {k: (vers.get(k), v) for k, v in expect.items() if vers.get(k) != v}
        print("VERSIONS", json.dumps(vers), flush=True)
        if bad: abort(13, f"library versions != --expect_versions: {bad}", versions=vers)
        tv, pin_t = vers["transformers"], a.pin_transformers
        if pin_t and pin_t != tv: tf_problem = f"--pin_transformers {pin_t} != installed transformers {tv}"
        elif tv != VERIFIED_TRANSFORMERS and pin_t != tv:
            tf_problem = (f"transformers {tv} is not the verified {VERIFIED_TRANSFORMERS} (greedy override verified there only); "
                          f"to run on {tv} anyway it must be pinned explicitly: --pin_transformers {tv}")
        else: tf_problem = None
        session.update(transformers_verified=VERIFIED_TRANSFORMERS, transformers_pin=pin_t or None, transformers_check="FAIL" if tf_problem else ("PINNED_UNVERIFIED" if tv != VERIFIED_TRANSFORMERS else "PASS"))
        print("TRANSFORMERS", json.dumps({"installed": tv, "verified": VERIFIED_TRANSFORMERS, "pin": pin_t or None, "check": session["transformers_check"]}), flush=True)
        if tf_problem and not a.preflight: abort(13, tf_problem, versions=vers)      # preflight goes on to print the merged config, then exits 13
        if not torch.cuda.is_available(): abort(10, "no CUDA device")
        free, total = torch.cuda.mem_get_info(); session.update(gpu=torch.cuda.get_device_name(0), gpu_free_at_start=free, gpu_total=total, min_free=a.min_free)
        print("GPU_FREE", json.dumps({"free": free, "total": total, "min_free": a.min_free}), flush=True)
        if free < a.min_free and not a.preflight: abort(10, f"GPU not free: {free} B free < {a.min_free}", gpu_free=free, gpu_total=total)
        tok = AutoTokenizer.from_pretrained(a.model); tok.padding_side = "left"
        if tok.pad_token is None: tok.pad_token = tok.eos_token
        enc = {}
        for r in rows:                                     # every row, whatever --limit/--kinds (review: E4 subset gap)
            ids = tok.apply_chat_template(messages(r, fs), tokenize=True, add_generation_prompt=True, return_dict=False)
            n_want, h_want = (r["fs_prompt_tokens"], r["fs_ids_sha256"]) if fs else (r["prompt_tokens"], r["ids_sha256"])
            if len(ids) != n_want: abort(4, f"tokenizer_mismatch count {r['id']} {len(ids)}!={n_want}")
            if hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest() != h_want: abort(4, f"tokenizer_mismatch ids {r['id']}")
            if not fs and len(ids) + min(a.max_new_tokens, MAX_NEW) > SEQ: abort(9, f"prompt_too_long {r['id']} {len(ids)}+{min(a.max_new_tokens, MAX_NEW)} > {SEQ}")   # jf0.0: budget is clamped per batch, never below min(max_new, 128)
            enc[r["id"]] = ids
        stop = [tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")]
        TB = None
        if a.constraint == "json-slot":                    # jf0.0: byte table from the model dir's own tokenizer.json, sha-pinned (exit 6 otherwise)
            tjp = os.path.join(a.model, "tokenizer.json")
            if model_files.get("tokenizer.json") != jsonslot.TOKENIZER_SHA256: abort(6, f"constraint: {tjp} sha256 != pinned {jsonslot.TOKENIZER_SHA256}")
            TB = jsonslot.token_bytes_from_tokenizer_json(tjp, max(len(tok), max(stop) + 1))
            session["constraint"] = {"schema": jsonslot.SCHEMA_ID, "tokenizer_sha256": jsonslot.TOKENIZER_SHA256, "byte_tokens": sum(b is not None for b in TB),
                                     "table_size": len(TB), "stop_ids": stop}
        try:
            q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
            m = AutoModelForCausalLM.from_pretrained(a.model, quantization_config=q, attn_implementation="sdpa", dtype=torch.bfloat16, device_map={"": 0})
            if a.adapter:
                from peft import PeftModel
                m = PeftModel.from_pretrained(m, a.adapter)
            m.eval(); torch.cuda.reset_peak_memory_stats()
        except torch.cuda.OutOfMemoryError as e:
            abort(5, f"cuda_oom at load {str(e)[:200]}")
        hf = m.get_base_model() if hasattr(m, "get_base_model") else m
        probe = {}
        if not (hasattr(hf, "_prepare_generation_config") and hasattr(hf, "_get_logits_processor")):
            abort(13, "cannot read the merged generation config on this transformers version (no _prepare_generation_config/_get_logits_processor)")
        _p, _l = hf._prepare_generation_config, hf._get_logits_processor
        def _plain(v): return v if isinstance(v, (int, float, str, bool, type(None))) else (list(v) if isinstance(v, (list, tuple)) else repr(v))
        def p_hook(*x, **k):
            r = _p(*x, **k); gc = r[0] if isinstance(r, tuple) else r
            probe["merged"] = {f: _plain(getattr(gc, f, None)) for f in GEN_FIELDS}; return r
        def l_hook(*x, **k):
            r = _l(*x, **k); probe["logits_processors"] = [type(z).__name__ for z in r]; return r
        hf._prepare_generation_config = p_hook; hf._get_logits_processor = l_hook
        def decoding_problems():
            if "merged" not in probe or "logits_processors" not in probe: return ["merged generation config / logits processors were not observed"]
            g = probe["merged"]; eos = g["eos_token_id"]; eos = set(eos if isinstance(eos, list) else [eos])
            want = {"do_sample": g["do_sample"] is False, "num_beams": g["num_beams"] == 1, "temperature": g["temperature"] in (None, 1.0),
                    "top_p": g["top_p"] in (None, 1.0), "top_k": g["top_k"] in (None, 0), "min_p": g["min_p"] is None, "typical_p": g["typical_p"] in (None, 1.0),
                    "repetition_penalty": g["repetition_penalty"] in (None, 1.0), "no_repeat_ngram_size": g["no_repeat_ngram_size"] in (None, 0),
                    "max_new_tokens": g["max_new_tokens"] == probe.get("cap"), "min_new_tokens": g["min_new_tokens"] in (None, 0),
                    "eos_token_id": eos == set(stop), "pad_token_id": g["pad_token_id"] == tok.pad_token_id, "num_return_sequences": g["num_return_sequences"] in (None, 1),
                    "bad_words_ids": not g["bad_words_ids"], "suppress_tokens": not g["suppress_tokens"], "begin_suppress_tokens": not g["begin_suppress_tokens"],
                    "logits_processors": probe["logits_processors"] == (["JsonSlotConstraint"] if a.constraint == "json-slot" else [])}
            return [k for k, ok in want.items() if not ok]
        def gen(chunk):
            L = max(len(enc[r["id"]]) for r in chunk); cap = budget(chunk, PKEY)
            if not fs and L != max(r["prompt_tokens"] for r in chunk): abort(4, "tokenizer_mismatch batch length")
            ids = torch.tensor([[tok.pad_token_id] * (L - len(enc[r["id"]])) + enc[r["id"]] for r in chunk], device="cuda")
            att = torch.tensor([[0] * (L - len(enc[r["id"]])) + [1] * len(enc[r["id"]]) for r in chunk], device="cuda")
            extra = {}
            if TB is not None:
                from transformers import LogitsProcessorList
                proc = jsonslot.JsonSlotConstraint(TB, stop, len(chunk)); extra["logits_processor"] = LogitsProcessorList([proc])
            probe.setdefault("cap", cap)
            with torch.no_grad():
                g = m.generate(input_ids=ids, attention_mask=att, do_sample=False, num_beams=1, max_new_tokens=cap,
                               repetition_penalty=1.0, temperature=None, top_p=None, top_k=None,   # override Qwen generation_config (rep 1.05, sampling)
                               eos_token_id=stop, pad_token_id=tok.pad_token_id, **extra)
            if "checked" not in probe:                     # first generate of every session: verify what generate() actually used (review I3, E0 check)
                bad = decoding_problems(); session["merged_generation_config"] = probe.get("merged"); session["logits_processors"] = probe.get("logits_processors")
                print("MERGED_GENERATION_CONFIG", json.dumps({"merged": probe.get("merged"), "logits_processors": probe.get("logits_processors")}), flush=True)
                if bad: abort(13, f"merged generation config is not plain greedy: {bad}", merged=probe.get("merged"), logits_processors=probe.get("logits_processors"))
                probe["checked"] = True
            out = []
            for seq in g[:, L:].tolist():
                n = next((i for i, t in enumerate(seq) if t in stop), None); body = seq[:n] if n is not None else seq
                out.append((tok.decode(body, skip_special_tokens=False), len(body), n is None))   # review L1: stray specials stay visible
            if TB is not None:                             # jf0.0 self-check: every row that stopped is strict-valid, else the constraint is broken
                gen.forced = list(proc.forced)
                bad = [r["id"] for r, (raw, nt, hm) in zip(chunk, out) if not hm and parse_strict(raw)[1] is not None]
                if bad: abort(13, f"constraint: rows stopped but not strict-valid: {bad[:5]}")
            return out
        def after_batch(done):
            pk = torch.cuda.max_memory_allocated()
            if pk > a.peak_limit: abort(3, f"peak_alloc {pk} > {a.peak_limit} after row {done}")
            return pk
    # 4. preflight (E0b): one row, no predictions file
    if a.preflight:
        os.makedirs(OUT, exist_ok=True)
        try:
            raw = gen(batches[0])[0]
        except Exception as e:
            if type(e).__name__ == "OutOfMemoryError": abort(5, f"cuda_oom in preflight {str(e)[:200]}")
            raise
        rep = {"tag": a.tag, "cfg": cfg, "session": session, "row": batches[0][0]["id"], "raw": raw[0], "time": now()}
        if a.backend == "hf":
            import torch
            rep.update(peak_alloc_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                       min_free_check="PASS" if session["gpu_free_at_start"] >= a.min_free else "FAIL", transformers_check=session["transformers_check"])
        p, fd = next_numbered(f"PREFLIGHT-{a.tag}-")
        with os.fdopen(fd, "w") as f: json.dump(rep, f, indent=1, sort_keys=True)
        print("PREFLIGHT_DONE", json.dumps({k: rep.get(k) for k in ("min_free_check", "peak_alloc_bytes")}), os.path.basename(p), flush=True)
        if a.backend == "hf" and tf_problem: abort(13, tf_problem + f" (preflight; merged config and free memory recorded in {os.path.basename(p)}; min_free_check {rep.get('min_free_check')})")
        if rep.get("min_free_check") == "FAIL": abort(10, f"GPU not free: {session['gpu_free_at_start']} B free < {a.min_free} (preflight; all other checks passed)")
        return 0
    # 5. run json first (status running, this session appended), then resume: repair a torn tail, drop partial batches
    #    (fixed boundaries; review M2), refuse corruption (exit 12, run json marked aborted)
    os.makedirs(OUT, exist_ok=True)
    meta = prev or {"cfg": cfg, "sessions": [], "planned_rows": len(planned), "planned_batches": len(batches),
                    "planned_ids_sha256": hashlib.sha256("\n".join(sorted(planned)).encode()).hexdigest()}
    meta["status"] = "running"; meta["sessions"].append(session); wjson(RUN, meta)
    have = {}
    if os.path.exists(PRED):
        data = open(PRED, "rb").read(); lines = data.split(b"\n"); tail = lines.pop()       # tail = bytes after the last newline
        good = []
        for n, ln in enumerate(lines):
            try:
                o = json.loads(ln); assert isinstance(o, dict) and isinstance(o.get("id"), str) and isinstance(o.get("raw"), str)
            except Exception:
                if n == len(lines) - 1 and not tail: tail = ln + b"\n"; break
                abort(12, f"predictions line {n + 1} is not a valid record (not the last line); not auto-repairable")
            if o["id"] in have: abort(12, f"duplicate id in predictions: {o['id']}")
            if o["id"] not in bidx: abort(12, f"unplanned id in predictions: {o['id']}")
            have[o["id"]] = o; good.append(ln)
        kept_b = {k for k in range(len(batches)) if all(r["id"] in have for r in batches[k])}
        drop = [i for i in have if bidx[i] not in kept_b]
        if tail or drop:
            session["repairs"].append({"torn_tail_bytes": len(tail), "dropped_partial_batch_rows": len(drop),
                                       "partial_batches": sorted({bidx[i] for i in drop}), "time": now()})
            keep = [ln for ln in good if json.loads(ln)["id"] not in set(drop)]
            t = PRED + ".tmp"
            with open(t, "wb") as f: f.write(b"".join(x + b"\n" for x in keep)); f.flush(); os.fsync(f.fileno())
            os.replace(t, PRED); print("REPAIRED", json.dumps(session["repairs"][-1]), flush=True)
            for i in drop: del have[i]
    todo = [k for k in range(len(batches)) if not all(r["id"] in have for r in batches[k])]
    session["batches_done_at_start"] = len(batches) - len(todo); wjson(RUN, meta)
    # 6. generate, one fsync'd write per whole batch
    t_all = time.time()
    try:
        with open(PRED, "a", encoding="utf-8") as out:
            for j, k in enumerate(todo):
                chunk = batches[k]; t0 = time.time(); res = gen(chunk); dt = (time.time() - t0) / len(chunk); cap = budget(chunk, PKEY)
                forced = getattr(gen, "forced", None) or [None] * len(chunk)
                out.write("".join(json.dumps({"id": r["id"], "raw": raw, "new_tokens": nt, "hit_max": hm, "sec": round(dt, 3), "batch": k, "max_new": cap, "forced": fz}) + "\n"
                                  for r, (raw, nt, hm), fz in zip(chunk, res, forced)))
                out.flush(); os.fsync(out.fileno())
                pk = after_batch(sum(len(batches[x]) for x in todo[:j + 1]))
                print(json.dumps({"batch": k, "done_batches": len(batches) - len(todo) + j + 1, "of": len(batches), "sec_per_row": round(dt, 3), "peak_alloc": pk}), flush=True)
    except Exception as e:
        if type(e).__name__ == "OutOfMemoryError": abort(5, f"cuda_oom {str(e)[:200]}")
        raise
    session["gen_seconds"] = round(time.time() - t_all, 1)
    if a.backend == "hf":
        import torch
        session.update(peak_alloc_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved())
    # 7. smoke only: batch-1 replay of the first N planned rows (review L6)
    preds = [json.loads(l) for l in open(PRED, encoding="utf-8")]
    if a.replay_b1:
        byid = {p["id"]: p["raw"] for p in preds}; rr = [r for b in batches for r in b][:a.replay_b1]
        diffs = [r["id"] for r in rr if gen([r])[0][0] != byid[r["id"]]]
        session["replay_b1"] = {"rows": len(rr), "raw_differs": len(diffs), "ids": diffs}
    # 8. finish: exactly the planned ids, once each; content hash; EVAL.SHA256 over every file in out_dir
    ids = [p["id"] for p in preds]
    if len(ids) != len(set(ids)) or set(ids) != set(planned): abort(14, f"predictions != planned ids ({len(set(ids))} unique of {len(planned)})")
    meta.update(status="complete", finished=now(), predictions=len(ids), complete=True, content_sha256=content_sha256(preds),
                hit_max=sum(bool(p.get("hit_max")) for p in preds))
    session["ended"] = now(); session["exit"] = 0; wjson(RUN, meta)
    files = sorted(f for f in os.listdir(OUT) if f not in ("EVAL.SHA256", "eval.lock") and not f.endswith(".tmp") and os.path.isfile(os.path.join(OUT, f)))
    with open(MF, "w") as f: f.write("".join(f"{sha(os.path.join(OUT, x))}  {x}\n" for x in files))
    release_lock()
    print("EVAL_DONE", a.tag, len(ids), "complete", meta["content_sha256"], flush=True)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:                              # review M3: any other crash (incl. KeyboardInterrupt) leaves a marker
        abort(11, f"unhandled {type(e).__name__}: {str(e)[:300]}", traceback=traceback.format_exc()[-3000:])
