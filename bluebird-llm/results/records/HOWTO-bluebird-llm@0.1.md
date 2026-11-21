# How we chose and fine-tuned a small local LLM: Bluebird LLM v1.0 (draft @0.1)

BIA 562 class deliverable, DRAFT. Little Blue for Vaccine Sales project.

**How to read this paper.**
- **MEASURED** means the number comes from a run we did and kept the raw logs for.
- **PROPOSED / NOT YET RUN** means a design that has not been executed. Everything about the full training run (§6) and the evaluation (§7) is in this category at the time of writing.
- **Estimate** means arithmetic or judgement, not a measurement.
- We make **no accuracy or efficacy claims.** All data used is synthetic. The benchmark texts have no gold labels, so the benchmark measures speed, memory and output format only.

## 1. The problem
The app helps a sales rep record a visit. For each talking point the rep raised, the app should suggest the customer's response as one of four labels (Positive, Neutral, Negative, Objection) with a short rationale. The rep can always override it. Requirements that shaped the model choice:
- It must run **locally on the app server's CPU**, in its own container, with no internet egress.
- Its output must be **machine-checkable JSON**: `{"response": <one of 4 labels>, "rationale": <string ≤ 120 chars>}`. Anything else is rejected and the field stays empty for the rep to fill.
- Proposed latency targets: **p95 ≤ 8 s per point** and **p95 ≤ 60 s for a 7-point visit**.
- It must be fine-tunable on a single **8 GB laptop GPU** using QLoRA.
- The licence must allow our use, and the fine-tuned model is named "Bluebird LLM v1.0".

## 2. Candidates and licence screening
We shortlisted four 3–8B instruct models that have public, ungated GGUF quantizations and fit the CPU and GPU budgets:

| # | Base model | Params | Licence (read from the upstream model card) | Screening outcome |
|---|---|---|---|---|
| C1 | microsoft/Phi-3.5-mini-instruct | 3.8B | MIT | Eligible |
| C2 | Qwen/Qwen2.5-3B-Instruct | 3.1B | Qwen RESEARCH licence, **non-commercial only** | Eligible only after an explicit project-owner ruling that this class project is non-commercial; ruling given |
| C3 | meta-llama/Llama-3.2-3B-Instruct | 3.2B | Llama 3.2 Community licence | **Dropped before benchmarking**: a distributed fine-tune must be named starting with "Llama" and show "Built with Llama", which conflicts with the product name; the base repo is also gated |
| C4 | Qwen/Qwen2.5-7B-Instruct | 7.6B | Apache-2.0 | Eligible |

Lessons:
- **Licences differ inside one model family.** Qwen2.5-3B and Qwen2.5-7B carry different licences. Read the card for the exact size you use.
- **Naming clauses matter** as much as commercial-use clauses.
- **Weights never go into a public repo**, whatever the licence. That covers base weights, adapters, merged models and GGUFs.

## 3. CPU serving benchmark (MEASURED)

### 3.1 Method
- **Runtime:** llama.cpp `llama-server` (official container image, pinned by digest; build 12375), CPU only (`-ngl 0`), context `-c 4096`, one slot (`-np 1`).
- **Models:** the Q4_K_M GGUF of each candidate from one public quantizer, with each file's sha256 checked against the repo's LFS id before use.
- **Hardware:** a 16-thread mobile-class x86 CPU (AVX2, no AVX-512) with 32 GB RAM, shared with a running app.
- **Isolation:** the server container ran with no network, read-only root, all capabilities dropped, a non-root user, and a memory cap (6 GiB for 3–4B, 9 GiB for 7B). The client ran in a second container that shared only the server's loopback. A guard script sampled the running app's health endpoint every ~2–4 s and would have killed the benchmark if latency or memory crossed thresholds. **It never fired** (0 aborts, 0 failed health checks in about 1,565 samples).
- **Workload:** 27 talking points from 5 synthetic visit narratives. Each prompt gives the point text and a two-sentence evidence window, wrapped in data delimiters (`<<<DATA … DATA>>>`) with the instruction that the delimited text is data, never instructions.
- **Decoding:** temperature 0, fixed seed, JSON-schema grammar (`response_format: json_schema`), prompt cache on, one discarded warm-up call, 3 runs per configuration.
- **Thread counts:** Tier 1 ran all candidates at 8 threads. Tier 2 ran the top two at 4 and 6 threads.
- **p95** is `statistics.quantiles(data, n=20, method="exclusive")[18]`.

### 3.2 Four output modes
| Mode | One call per | Output | Token cap |
|---|---|---|---|
| **PR** | point | label + rationale | 64 |
| **PE** | point | label only | 12 |
| **BR** | visit (all points batched) | array of {key, label, rationale} | 64 × n |
| **BE** | visit | array of {key, label} | 16 × n |

### 3.3 Results (MEASURED)
**PR mode is the product mode.** It was the only mode that was 100 % valid JSON for every model and thread count.

| Model | Threads | PR per-point p50 / p95 (s) | 7-point visit p95 (s) | Gen tok/s (median) | Valid JSON | Container memory peak |
|---|---|---|---|---|---|---|
| Qwen2.5-3B | 8 | 3.69 / **4.73** | 32.98 | 15.1 | 100 % | 2.98 GiB (49.7 % of cap) |
| Qwen2.5-3B | 6 | 3.89 / **5.05** | 31.84 | 15.0 | 100 % | 1.85 GiB |
| Qwen2.5-3B | 4 | 4.20 / **5.29** | 37.14 | 14.8 | 100 % | 1.84 GiB |
| Phi-3.5-mini | 8 | 5.30 / **6.63** | 43.05 | 12.5 | 100 % | OOM-killed at the default prompt cache (see §8) |
| Phi-3.5-mini (prompt cache capped) | 6 | 6.40 / **7.39** | 49.03 | 12.5 | 100 % | 3.78 GiB |
| Phi-3.5-mini (prompt cache capped) | 4 | 7.33 / **8.38 (over 8 s)** | 51.36 | 12.0 | 100 % | 3.77 GiB |
| Qwen2.5-7B | 8 | 8.11 / **9.94 (over 8 s)** | **67.52 (over 60 s)** | 7.1 | 100 % | 3.86 GiB (42.9 % of cap) |

Valid-JSON rates in the other modes at 8 threads:

| Model | PE | BR | BE |
|---|---|---|---|
| Qwen2.5-3B | 100 % | 33.3 % | 0 % |
| Phi-3.5-mini | 48.1 % | 0 % | 0 % (Tier 2 / re-test) |
| Qwen2.5-7B | 100 % | 66.7 % | 80 % |

### 3.4 Format check
Every response was parsed and checked against the contract: valid JSON, no extra keys, the label in the enum, the rationale a string of ≤ 120 characters, and for batched modes exactly the visit's keys once each. A run counts toward the latency decision only if its mode is clean. We also counted a call as **cap-truncated** when generated tokens ≥ the token cap.

## 4. GPU fit test (MEASURED)
**Question:** does QLoRA at full sequence length fit an 8 GB laptop GPU? An earlier smoke test on short rows (~236 tokens) peaked at 2.588 GB, which says nothing about 1,536 tokens.

**Method.**
- 20 optimizer steps × gradient accumulation 16 = 320 training rows.
- Each row was built deliberately long (≥ 9,000 characters of contract text), then truncated so **every row is exactly 1,536 tokens** (asserted). The answer is always kept and the context is cut.
- 4-bit nf4 with double quantization, bf16 compute, SDPA attention; LoRA r 16, α 32, dropout 0.05, `target_modules="all-linear"`; gradient checkpointing; PagedAdamW8bit, lr 2e-4, cosine; batch 1.
- Rows came from the **training split only**. No adapter was saved.
- **Pass rule:** `torch.cuda.max_memory_allocated() ≤ 7.0×10⁹` bytes, all 20 steps complete, no NaN loss. A peak between 7.0×10⁹ and 7.0×2³⁰ bytes would have been flagged as ambiguous (GB vs GiB) rather than auto-passed.
- **Stack:** torch 2.11.0+cu128, bitsandbytes 0.50.2, transformers 5.22.2, peft 0.21.2, trl 1.17.1, Python 3.12, Windows native (no WSL), Blackwell laptop GPU (sm_120, 8 GB).

**Results (MEASURED):**
| Base | Base load (alloc) | Peak allocated | Peak reserved | Steps | Loss step 1 → 20 | Seconds per step (steps 2–20) | Result |
|---|---|---|---|---|---|---|---|
| Qwen2.5-3B | 2,064,990,208 B | **6,237,824,000 B (5.81 GiB)** | 6,715,080,704 B | 20/20, no NaN | 1.892 → 0.808 | 72.56–76.36, mean 74.51 | PASS |
| Phi-3.5-mini | 2,264,129,536 B | **4,109,368,832 B (3.83 GiB)** | 4,682,940,416 B | 20/20, no NaN | 1.615 → 0.755 | 51.80–55.80, mean 53.87 | PASS |

The falling loss in 20 steps only shows that the loop trains. It is **not** a quality result.

## 5. Base pick
We first required four things of a candidate: CPU latency within targets in the product mode, a fit-test pass, an acceptable licence, and a clean format check. Among the candidates that met them, the lowest PR p95 ranked first.
- **Qwen2.5-3B-Instruct** passed at every thread count tested, with the most margin: PR p95 at 4 threads is 5.29 s against the 8 s target. **It was picked by the project owner.**
- **Phi-3.5-mini** is the **documented fallback**. It is MIT-licensed and has a lower fit peak. However, it misses the 8 s target at 4 threads, and it needs the prompt-cache cap to stay inside its memory limit.
- **Qwen2.5-7B** missed both CPU latency targets at 8 threads, so it was not fit-tested.

## 6. Full QLoRA recipe (PROPOSED, NOT YET RUN; needs the project owner's go-ahead)
**Data.** The training split of the synthetic contract Q&A corpus has **6,273 rows**:
- 4,986 answerable rows with a source anchor;
- 1,287 **unanswerable** rows (20.5 %), kept and given a **refusal target** `{"answer": "not in the contracts", "spans": {}}` so the model learns to refuse.

The **test split** (2,090 rows, separate systems and a separate template family; 0 overlap measured) is never trained on. Answer format: digit-free prose with `{Sn}` slots, plus verbatim span objects tied to clause anchors.

**Row building** (MEASURED on the built rows with the base's own tokenizer):
- Each row contains the question's document plus every anchor's clause (anchors can sit in another document), with documents and clauses in **natural numeric order** (1, 2, … 10, 11, 11.1). The anchor clause stays where it naturally falls, so the model cannot learn "the answer is always the first clause".
- If a row would exceed **1,536 tokens**, whole clauses are dropped **farthest from the anchor first**. Anchor and span clauses are never dropped.
- 74.2 % of rows hold the whole document, and 25.8 % drop some clauses. **0 % lose an anchor or span clause.** No packing.
- The anchor is the first clause in 5.2 % of answerable rows, in the middle in 85.4 %, and last in 9.4 %.
- Row length: mean 777.9 tokens, median 538, max 1,536.
- Each row stores its token count and a hash of its token ids. The trainer re-tokenizes on the training machine and refuses to start on any mismatch.

**Hyperparameters.** The same as the fit test, with two proposed changes:
1. **completion-only loss**: prompt tokens are masked, so the model learns the answer rather than reproducing contract text;
2. variable-length rows.

Proposed **1 epoch**, with 2 epochs as the alternative. Steps = ceil(6,273 / 16) × epochs = **393 per epoch**.

| Option | Steps | Upper bound at measured fit step times (estimate) | Token-scaled estimate |
|---|---|---|---|
| 1 epoch | 393 | 7.9–8.3 h | ~4.0–4.2 h |
| 2 epochs | 786 | 15.8–16.7 h | ~8.0–8.4 h |

The upper bound uses the fit's full-length step times. Real rows are about half as long, so the run is probably shorter (estimate, not measured).

**Guards (proposed).**
- Abort if peak allocated memory goes above 7.0×10⁹ bytes.
- Abort on NaN or Inf loss before the optimizer step.
- Abort if the training-machine and data-build-machine tokenizers disagree on any row's token count or token-id hash.
- Abort on CUDA out-of-memory, a non-finite gradient norm, a row longer than 1,536 tokens, a data or script file whose sha256 does not match the manifest, or a resume with changed settings. Each abort writes a small JSON file with the reason.
- Log the allocated, reserved and device-wide GPU memory every step, so the paged optimizer's use is visible.
- Require AC power, disable sleep for the run and restore it afterwards, and log GPU temperature and throttle reasons each minute.
- Checkpoint the adapter, optimizer, scheduler and RNG state every 50 steps, keep the last two, and resume from the last complete one.
- Hash the final adapter (sha256) and keep it off any public repo.

**After training (PROPOSED, separate approval).**
1. Merge the LoRA into the bf16 base.
2. Convert with `convert_hf_to_gguf.py`.
3. Build an **importance matrix from training rows only** and quantize to Q4_K_M. Plain Q4_K_M failed an earlier agreement check at 5/10.
4. Check that the GGUF agrees with the merged HF model on ≥ 90 % of 30 fixed prompts.
5. Re-run the CPU benchmark on the tuned GGUF.

## 7. Evaluation design (PROPOSED, NOT YET RUN)
- **Hard gate:** 100 % valid, in-enum JSON in PR mode on the 27 benchmark points, with the grammar on. The grammar-off rate is reported, and ≥ 99 % is proposed.
- **Held-out test split**, tuned vs stock base, reported with bootstrap 95 % intervals:
  - answer exact match;
  - citation-anchor accuracy;
  - refusal precision and recall;
  - JSON validity;
  - span-validator pass rate;
  - guardrail violations, which must be 0.

  "Tuned beats stock" is claimed only if the interval clears.
- **Customer-response task**, proposed bars on a separate synthetic eval family:
  - macro-F1 ≥ 0.80, with each class's recall ≥ 0.70;
  - Positive↔Objection confusions ≤ 2 %;
  - raw valid JSON ≥ 99 %;
  - hard-case macro-F1 ≥ 0.70.

  **The labelled response examples are not built yet**, so these bars can't be measured on the first adapter. Real-visit accuracy is never claimed.
- **Leakage controls:**
  - split by system and by template family;
  - exact- and near-duplicate checks across splits;
  - the generator may read only allowlisted inputs;
  - a planted canary string must never reach the training data.

## 8. Lessons learned
1. **The default prompt cache can OOM a capped container.** Phi-3.5-mini at 8 threads was OOM-killed inside its 6 GiB cgroup during batched calls (anon RSS about 6.27 GB). Capping llama-server's host prompt cache (`--cache-ram 1024`) brought the peak to 3.81 GiB. Our inference is that the default cache size was the cause. **Set the cache size explicitly** when you cap memory.
2. **Batched JSON is fragile, even under a grammar.**
   - Enum-only batched (BE) calls failed mostly by **hitting the token cap**: the grammar allowed pretty-printed whitespace, which used up 16 tokens per point.
   - Batched-with-rationale (BR) calls on Qwen2.5-3B failed by **duplicating or skipping keys**: a JSON schema can't enforce unique keys.
   - Latencies from capped runs are lower bounds, not product numbers. Per-point calls cost more time but were 100 % valid.
3. **Tight token caps break small enum outputs.** Phi in PE mode hit the 12-token cap on 42 of 81 calls.
4. **Some chat templates break grammar mode.** Phi's grammar requests returned HTTP 400 with jinja templates on, so it ran with `--no-jinja`. Record such flags.
5. **Null-anchor rows are a policy decision, not noise.** 1,287 training rows (20.5 %) have no source anchor because they are unanswerable by design. A builder that skips them (our fit-test builder did, which was fine for memory) would train a model that never refuses. We keep them with a refusal target.
6. **Anchors can live in another document.** 666 training rows cite a clause in a different document (proposals, amendments), and 540 cite more than one. Resolve each anchor by its own document id and assert that each span's text appears verbatim. A lookup by the question's own document id silently picked the wrong clause for some rows. It did not affect the fit test, because none of its 320 rows were cross-document.
7. **Measure on full-length rows.** A short-row smoke test peaked at 2.6 GB; the same model at 1,536 tokens peaked at 6.24 GB.
8. **Sort clause ids numerically.** A plain string sort puts section 10 before section 2. That silently reordered 135 exhibit documents, and when rows were truncated it kept the wrong clauses.
9. **Don't put the answer clause in a fixed position.** Our first builder always put the anchor clause first, a shortcut the model could learn. We now keep natural order and truncate around the anchor.
10. **Make resume bit-exact, and test it.** A code review found that a resumed run diverged from an uninterrupted one. The fix:
    - seed before the LoRA weights are created;
    - don't re-seed after restoring the saved RNG state;
    - save and restore the CUDA RNG too;
    - truncate the step log to the checkpoint on resume.

    On a tiny CPU stand-in model, fresh vs fresh and killed-then-resumed vs uninterrupted runs are now bit-exact, with identical adapter hashes. GPU kernels may still differ slightly between runs.
11. **Canonicalise saved configs before hashing them.** The PEFT library writes the LoRA `target_modules` list from a Python set, so the config file's bytes changed from process to process. Sort it after saving, or the adapter hash is not reproducible.
12. **Force every guard to trip once.** We injected each failure on the tiny CPU model: peak memory over the limit, NaN loss, an infinite gradient, out-of-memory, token mismatches, a tampered file, an over-long row, and changed settings on resume. Each one aborted with its expected exit code.
13. **Isolate benchmarks from live services and prove it.** Use throwaway containers, no network and capped resources, run a live-health guard, and compare snapshots before and after teardown.

## 9. Reproduce it (generic commands)
Replace `<…>` placeholders. Pin every image and model by digest or commit, and check sha256 before use.

**CPU benchmark server:**
```bash
docker run -d --name bench-srv --network none --cpus <T> --memory 6g --memory-swap 6g \
  --read-only --tmpfs /tmp:size=64m --cap-drop ALL --security-opt no-new-privileges --user 65534:65534 \
  -v <MODELS_DIR>:/models:ro ghcr.io/ggml-org/llama.cpp@sha256:<DIGEST> \
  -m /models/<MODEL>-Q4_K_M.gguf --host localhost --port <PORT> -t <T> -tb <T> -c 4096 -np 1 -ngl 0 \
  --cache-ram 1024            # add --no-jinja if grammar requests return HTTP 400
docker run --rm --network container:bench-srv --cpus 1 --memory 512m --read-only --cap-drop ALL \
  -v <BENCH_DIR>:/bench:ro -v <OUT_DIR>:/out python:3.12-slim \
  python /bench/bench_client.py --model <tag> --threads <T> --modes PR,PE,BR,BE --runs 3 --out /out
docker rm -f bench-srv
```
The client posts to `/v1/chat/completions` with `temperature 0`, a fixed `seed`, `cache_prompt: true` and `response_format: {"type": "json_schema", …}`. It logs wall time, llama-server `timings`, and whether the output is valid.

**Download the training base at a pinned revision:**
```bash
python -c "from huggingface_hub import snapshot_download as s; s('Qwen/Qwen2.5-3B-Instruct', revision='aa8e72537993ba99e69dfaafa59ed015b17504d1', local_dir='<MODELS>/Qwen2.5-3B-Instruct')"
```

**Fit test (core of the loop):**
```python
q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
m = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=q, attn_implementation="sdpa", dtype=torch.bfloat16, device_map={"": 0})
m = prepare_model_for_kbit_training(m, use_gradient_checkpointing=True)
m = get_peft_model(m, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear", task_type="CAUSAL_LM"))
opt = bnb.optim.PagedAdamW8bit([p for p in m.parameters() if p.requires_grad], lr=2e-4)
sched = transformers.get_cosine_schedule_with_warmup(opt, 0, STEPS)
torch.cuda.reset_peak_memory_stats()
for step in range(STEPS):                      # 20 steps x accum 16, rows exactly 1,536 tokens
    for _ in range(16):
        x = next_row(); (m(input_ids=x, labels=x).loss / 16).backward()
    opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
print(torch.cuda.max_memory_allocated())        # pass if <= 7.0e9
```
For the full run (proposed), use `labels` with prompt positions set to `-100`, seed before `get_peft_model`, checkpoint every 50 steps (adapter, optimizer, scheduler, all RNG states), and save only the adapter (`save_pretrained`).

**Export (proposed, later):** merge the adapter → `convert_hf_to_gguf.py` → `llama-imatrix` on training rows → `llama-quantize … Q4_K_M` → agreement check vs the HF model.

## 10. Status at time of writing
- **Done and measured:** licence screening, the CPU benchmark, the GPU fit test, the base pick.
- **Proposed, awaiting approval:** the full QLoRA run, GGUF export, evaluation, and the customer-response training data.
- No accuracy result exists yet.
