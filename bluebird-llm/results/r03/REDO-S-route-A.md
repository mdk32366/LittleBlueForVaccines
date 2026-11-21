# Bluebird eval: baseline (S) redo, route A

**Document status:** partial record, written 2026-11-16. Final run results, hashes, scores, and the result note are **pending**.

**Purpose.** Class deliverable for Matt Kelly recording why the full baseline (S) run of the Bluebird LLM v1.0 post-run eval stopped, what analysis replaced the first resume plan, what options were put to Matt, and how route A (a fresh S run at batch 4 in a new folder) was specified and gated. This file is a record, not an order. The governing procedure remains `ORDER-bluebird-eval@0.7.md`.

**Method.** Every factual claim below is taken from a file on the box that was read while writing this document, and is cited by path (and by line or sha256 where that helps). Laptop command output that was not copied to the box is marked **not recorded**. Where a later step has not happened, it is marked **pending**. Times that appear in laptop JSON without a zone are quoted as written; the order labels the abort session as Pacific Time (PT, America/Los_Angeles). Box file timestamps below are also in that zone (UTC−8 on this date).

Roles, as specified in the order: Trinity writes the order; Kaylee reviews it; Emma operates the laptop, each command on its own Matt approval card.

---

## 1. Summary

The trained-model (T) and baseline (S) evals are specified in `ORDER-bluebird-eval@0.7.md` (sha256 `6c13d07eaf9f5184c51fd40129f07bb6afddc6c256c37de578a2ffafb219058a`), written 2026-11-15 by Trinity. The run-time stage is `/workspace/littleblue-eval-v0.5/` (RUN PIN and SCORE PIN unchanged from earlier stages). S is the untrained Qwen2.5-3B-Instruct baseline, few-shot, tag `qwen25-3b-base-fs`, 3,569 rows, originally planned as 447 batches of 8.

The first full S launch (`E5-pin`, transformers 5.22.2 pinned, default `--peak_limit` 7.0e9, out dir `out-S`) stopped with exit 3. The last line of the copied `eval-S.out` and the cause in `ABORT-1.json` are the same:

`ABORT 3 peak_alloc 7001188352 > 7000000000.0 after row 2920`

The session in the copied run JSON is pid 9448, started `2026-11-15 18:05:28`, ended `2026-11-15 19:12:12`, exit 3, `batches_done_at_start` 0. The order labels those times 6:05:28–7:12:12 PM PT. 2,920 prediction lines were kept (365 whole batches of 8). 82 batches remained.

Order @0.6 had treated the abort as gradual growth inside one long session and recommended resuming with the identical `E5-pin` line. The real per-batch curve, copied by `E5-S1-keep` and checked on the box, falsified that premise. `peak_alloc` is a session maximum. After the load ramp, every batch that raised it was a zero-padding batch (all eight prompts the same length). Those batches fit

own peak ≈ 2.5358e9 + 1410.88 · L² bytes

(49 record-raising points). Six of the 82 remaining batches project to 7.63e9–8.02e9, above the 7.0e9 guard, so identical resume (`E5-pin-resume`) was withdrawn.

Order @0.7 put four options to Matt (A recommended): A, a fresh S at `--batch 4` in a new dir `out-S-b4`; B, resume `out-S` with `--peak_limit 8500000000`; C, a code change and reruns of T and S; D, hold. Kaylee's re-check of @0.7 is **PASS** (`RECHECK-eval@0.7.md`, sha256 `496f8f0ffe35e45971703f8dc17c5cf079f6beb3cbe1702ee0311436c2cfed2a`); findings N39–N45 are all INFO. Route A was judged sound to card after a Matt ruling.

Matt ruled A on card `t382s1311` at 2:39 AM PT on 2026-11-16 (filed in the gate record cited in §8). The `E5-S-gate` process check hit two pre-existing `python.exe` processes (the littleblue-app Streamlit server, not eval, not on the GPU). Trinity pre-ruled an exception; the gate was recorded as PASS with that exception logged; neither process was touched. The next prescribed step is `E5-b4-pin` (set P, `--batch 4`, new logs `eval-S4.out` / `eval-S4.err`). Raw launch and poll output for that run has not been copied to the box; see §9 and §11.

---

## 2. Identifiers and pins

These values are taken from order @0.7 §0, §g and §j, and were re-hashed on the box while writing this file.

| Item | Path | sha256 |
|---|---|---|
| Order @0.7 (governing) | `/workspace/littleblue-specs/ORDER-bluebird-eval@0.7.md` | `6c13d07eaf9f5184c51fd40129f07bb6afddc6c256c37de578a2ffafb219058a` |
| Order @0.6 (superseded, left unchanged) | `/workspace/littleblue-specs/ORDER-bluebird-eval@0.6.md` | `ff8f6f57e9108a11df16bf165f45ff83872cd49678e8b62e56eb7cbb6916b6e6` |
| Order @0.5 (superseded, left unchanged) | `/workspace/littleblue-specs/ORDER-bluebird-eval@0.5.md` | `7187d5adf48bb525b68f945791fa8dd39feace54bf6aca9698095d7fc08a7f51` |
| Addendum A1–A2 (still applies) | `/workspace/littleblue-specs/ADDENDUM-bluebird-eval@0.5-A1-A2@0.0.md` | `6402ac634d6c512483a37d3330d94fb05d0bef0a02e3c937b3cbdd3edbeafa1c` |
| DIFF @0.6 → @0.7 | `/workspace/littleblue-eval-v0.7/DIFF-0.6-to-0.7.md` | `0e029eeb7f11bd5582a10a4b8038c3bdcd96c32179f336d254835a46f53e3a6e` |
| @0.7 stage manifest | `/workspace/littleblue-eval-v0.7/V07-FILES.SHA256` | `a1d7db35fc9c6b1480f8653b4dc141dea7f7d14cbcf9ebde90dd34f89dfa0a43` |
| Box check (replaces @0.6 `ed4208b7`) | `/workspace/littleblue-eval-v0.7/tools/e5s1_check.py` | `814a5657fc7c138bda705ad1460993ee6690fb30f9ca0a7ad5ed635e6531c3f6` |
| Kaylee re-check of @0.7 | `/workspace/littleblue-eval-review/RECHECK-eval@0.7.md` | `496f8f0ffe35e45971703f8dc17c5cf079f6beb3cbe1702ee0311436c2cfed2a` |

Pins, unchanged in @0.7 (order L149–150, L700–701):

- RUN PIN (sha256 of `RUN-INPUTS.SHA256`) = `0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d`
- SCORE PIN (sha256 of `SCORE-INPUTS.SHA256`) = `8c4b3042ba5abf0134b9d0075170ec55585e41092e60e51f411642b59b59bd1e`
- Adapter `ADAPTER.SHA256` (score.py `--expect_adapter_sha`) = `35589c33dcc605024b44f6cadecae002998ffff4ecb75a7c52d5432f2988251b`
- `EVAL-INPUTS.SHA256` (v0.5 stage audit, 67/67) = `366202f5db0a731ad9929337fc175d720e145000da61c796b34540b2ca675ef1`

Laptop work dir named in every §g command: `C:\Users\mdk32\lb-eval-bluebird-v1.0-r03`. Interpreter: `C:\Users\mdk32\venvs\bia562-train\Scripts\python.exe`. Model path: `C:\Users\mdk32\models\Qwen2.5-3B-Instruct`.

What is evaluated (order §a): T = base Qwen2.5-3B-Instruct, nf4 as in training, plus LoRA e2, zero-shot. S = the same base, no adapter, 2-shot (`fewshot.json`). Test = 2,090 family-B rows plus memorisation probes, 3,569 rows in all.

---

## 3. Timeline (PT)

| When (PT) | Event | Source |
|---|---|---|
| 2026-11-15 3:08:21 PM | First preflight (`PREFLIGHT-bluebird-v1.0-e2-1.json` / `ABORT-1.json` in `pre-T/`): transformers 5.22.2, `transformers_check` FAIL, `min_free_check` PASS, `gpu_free_at_start` 7,385,120,768 of `gpu_total` 8,546,484,224, exit 13. This is the order's set-P row (pin required; free memory was above the 7.0e9 default). | `/workspace/littleblue-eval-v0.5/runs/r03/pre-T/ABORT-1.json`, `PREFLIGHT-bluebird-v1.0-e2-1.json`; order @0.7 L270 |
| 2026-11-15 3:53:15 PM | Pinned preflight (`PREFLIGHT-bluebird-v1.0-e2-2.json`): `transformers_check` `PINNED_UNVERIFIED`, `min_free_check` PASS, same free/total, peak 2,253,176,832. Later smoke and full-S launches use set P (`--pin_transformers 5.22.2`, no `--min_free` override). | `PREFLIGHT-bluebird-v1.0-e2-2.json` |
| 2026-11-15, files landed 4:39 PM | Smoke T and smoke S both exited 0. Last lines: `EVAL_DONE bluebird-v1.0-e2 64 complete dc0046e2…d5c5a7` and `EVAL_DONE qwen25-3b-base-fs 64 complete fac508d7…9cd1ab`. Box scoring: both `E3_pass` true, no verdict. T `strict_valid` 0.9844, `hit_max_rate` 0.0156; S `strict_valid` 0.2344 (report-only), `hit_max_rate` 0.0781, `peak_alloc_bytes` 4,030,207,488. Smoke S `replay_b1.raw_differs` = 3 of 8 (batch-size effect on greedy text). | `runs/r03/smoke-T.out`, `smoke-S.out`; `smoke-score-T/SMOKE-T.json`; `smoke-score-S/SMOKE-S.json`. `smoke-S.out` sha256 `4b8b2cab351ced18d554494e64f1af0580e2498e01d159db26f4302a0f3819b9` (the I11 pin). File mtimes 16:39:36 and 16:39:38 PT. |
| **Full T run (`E4-pin`)** | **Not recorded on the box.** `runs/r03/out-T/` is empty (the route-A hash-and-copy step E7-A has not been done). | directory listing, 2026-11-16 |
| 2026-11-15 6:05:28–7:12:12 PM | Full S (`E5-pin`) session pid 9448. argv includes `--out_dir out-S`, `--pin_transformers 5.22.2`, no `--batch` (cfg.batch = 8), no `--peak_limit` override. `GPU_FREE` at start: free 7,385,120,768, total 8,546,484,224, `min_free` 7,000,000,000.0. Versions: torch `2.11.0+cu128`, cuda `12.8`, transformers `5.22.2`, peft `0.21.2`, bitsandbytes `0.50.2`. GPU name in the run JSON: `NVIDIA RTX PRO 2000 Blackwell Generation Laptop GPU`. 364 progress lines (batches 0–363 of 447). Last line and abort cause as in §1. Exit 3. | `e5-s1/eval-S.out` (369 lines; last line 369); `e5-s1/out-S/ABORT-1.json`; `e5-s1/out-S/run-qwen25-3b-base-fs.json`; order L483 |
| 2026-11-15 7:42 PM | Matt card `t369s1265`: send the E5-pin abort to Trinity for an order amendment; Kaylee diff-checks before any card. Answered first by @0.6, then superseded by @0.7. | order @0.7 L11, L822, L860, changelog L949 |
| 2026-11-15 about 9:00 PM | `E5-S1-keep` (read-only hash, then copy). nvidia-smi compute apps: pid 12452 `C:\Windows\explorer.exe`; pid 1344 `[Insufficient Permissions]`. `Get-Process -Id 1344` = `dwm`. Trinity ruled the process gate is live python/eval.py only; explorer and dwm are logged, not stopped. `eval.lock` was absent; no eval.py `Win32_Process`. Five files copied; laptop `Get-FileHash` matched box `sha256sum` (Emma-reported in the evidence file). Box copy mtimes: 9:00:03–9:00:08 PM PT. | `e5-s1/E5-S1-EVIDENCE.txt`; order L538–544, L566–576 |
| same keep | @0.6 `e5s1_check.py` (`ed4208b7`) on the copy printed `E5S1 STOP` (C1 jump 2,422,646,272 B at batch 356; C2 projection 8,223,608,809 > 6.5e9). That is the keep-time result that refuted gradual-growth resume. The @0.7 check, which replaced that tool, is in §4. | `E5-S1-EVIDENCE.txt` |
| 2026-11-15, order file 9:46 PM | Trinity issued `ORDER-bluebird-eval@0.7.md` (header: written Sun 11/15/2026). @0.6 in-session-growth premise withdrawn; `E5-pin-resume` withdrawn; options A–D and a Matt question added. | order L1–6, L470–515, changelog L950; file mtime 21:46:06 PT |
| 2026-11-15 10:15–10:55 PM | Kaylee re-check of @0.7: **PASS**, no MED or higher; N39–N45 all INFO. Routes A, B and D sound to card once Matt answers; C is not cardable until a new order round. File mtime 10:51:35 PM PT. | `RECHECK-eval@0.7.md` L1–10, L114–118 |
| 2026-11-16 2:39 AM | Matt ruled route A on card `t382s1311`. | `e5-b4-s1/E5-S-GATE-RECORD.txt` L1 |
| 2026-11-16, record written 2:40:53 AM | `E6-S` (read-only): `NO LOCK`; `STATUS aborted`; `ABORT-1.json pid=9448 exit=3`; GPU `0/8151` MiB; `BatteryStatus` 2, 100%. `E5-S-gate` hit two `python.exe` processes and STOP'd. Full `CommandLine` read and Trinity pre-ruling: see §8. Gate recorded as PASS with exception logged. Neither process was touched. | `E5-S-GATE-RECORD.txt` (mtime 02:40:53 PT) |
| After that record | `E5-b4-pin` launch, later `E6-S4` polls, `EVAL_DONE`, E7-A, scoring, A1, E8, E9, and the result note | **pending** / launch and poll output **not recorded** on the box (see §9 and §11) |

---

## 4. Failure and root-cause analysis

### 4.1 What stopped

Copied abort file `/workspace/littleblue-eval-v0.5/runs/r03/e5-s1/out-S/ABORT-1.json` (sha256 `c0e97ac59269dfa01a116e3234ce1889913faf5cbd2b57f6adcc7092f646be9e`):

```json
{
 "abort": "peak_alloc 7001188352 > 7000000000.0 after row 2920",
 "exit": 3,
 "pid": 9448,
 "tag": "qwen25-3b-base-fs",
 "time": "2026-11-15 19:12:12"
}
```

Exit 3 is defined in order §e L66: `max_memory_allocated` > `--peak_limit` (7.0e9) after any batch.

Copied run JSON (sha256 `0b0e2d523aa1406c995b7653012d3a8a33ddd9f222b38d98decdace74fcf79fe`): `status` `aborted`; `cfg.mode` `fewshot`; `cfg.batch` 8; `cfg.limit` 0; `cfg.tag` `qwen25-3b-base-fs`; no adapter; `manifest_sha256` equals the RUN PIN; one session, pid 9448, `batches_done_at_start` 0, `abort_file` `ABORT-1.json`. I2 of the @0.7 check records planned size as 3,569 rows / 447 batches.

`eval-S.out` (sha256 `d7278a0d7bd4bfdaa3ddfc9ea444cf0001ad36efab1a7dd6d4a7b9ce66e1bc61`) has 364 progress lines, batches 0–363, then the ABORT 3 line. There is no progress line for the aborting batch (check I7: progress ends one batch before the abort batch). `predictions-qwen25-3b-base-fs.jsonl` has 2,920 lines, 365 whole batches, no partial batch (check I5). 2,920 = 365 × 8, and 82 batches (365–446) remained (order L483; check-real remaining_batches 82).

`eval-S.err` (sha256 `4c3bbc54d154b53b7cfab61699b7e6020302e7695413b7c171d560f4a0ddfa0d`) holds two torch warnings (Windows redirect note; triton not found) and the weight-loading progress bar for pid 9448, starting `W1115 18:05:31`. No traceback.

The order (L483) also records, as Emma-reported and agreed with this copy: `eval.lock` was absent after the stop, and 82 batches / 649 rows remained.

### 4.2 What `peak_alloc` measures

Order @0.7 L485 (and Kaylee's re-check, PASS): `peak_alloc` is `torch.cuda.max_memory_allocated()`, reset once after the model load (eval.py L264) and read after each batch is written. It is the **session maximum so far**. A progress line shows a batch's own peak only when that batch raised the maximum; otherwise it repeats the earlier maximum. The value never decreases. In this session it is flat from batch 300 to 355 at 4,526,430,720 and from 356 to 361 at 6,949,076,992 (`eval-S.out`; order L485).

### 4.3 The @0.6 premise, and the jump that refuted it

Order @0.6 read the abort as gradual growth inside one long session, with a fresh process expected to clear it, and recommended resume on the identical `E5-pin` line, projected about 4.7e9–5.2e9 (order L471, L949). That reading is **withdrawn** in @0.7.

The keep-time @0.6 check already printed a C1 jump of 2,422,646,272 B at batch 356 (`E5-S1-EVIDENCE.txt`). The same step is in `eval-S.out`:

- batch 355: `"peak_alloc": 4526430720`
- batch 356: `"sec_per_row": 3.481, "peak_alloc": 6949076992`

The difference is 2,422,646,272 bytes. The @0.7 check classifies batch 356 as pad 0, L 1,769 (check-real C1; order L487). After the load ramp (batches 0–15), **every** batch that raised the session maximum was a zero-padding batch. Padded batches never raised it after batch 15, at any length up to 1,780 (order L487; Kaylee: after batch 15, all 7 new-longest zero-padding batches raised the max and none of 135 padded ones did).

Smoke S does not refute this and does not support the @0.6 comparison. The smoke-S mapping is full batches 0, 64, 127, 191, 254, 318, 381, 445. Their padding is 21, 0, 0, 0, 1, 2, 3, 2. Smoke never ran batch 356. Smoke batches 381 (1,879 tokens) and 445 (1,994) are padded, so their peak of 4,030,207,488 proves only that padded batches at those lengths are cheap in a fresh process (order L497; `smoke-S.out` last progress line). The @0.6 sentence that compared those padded smoke batches with zero-padding full-run batches is withdrawn.

### 4.4 Mechanism and the L² fit

Order L495 (mechanism, box-verified in source; the kernel itself is *unverified*, no GPU on the box). In transformers 5.23.0, a batch whose padding mask is all ones gets no attention mask, and SDPA is called with `is_causal=True`; a batch with any padding gets an explicit mask. The laptop runs pinned 5.22.2, *assumed* to share this logic. The data say the no-mask path on this laptop (torch 2.11.0+cu128, Blackwell, Windows) materialises memory that grows with L²; the masked path does not.

**Fit** over all 49 record-raising zero-padding batches with L ≥ 900, as stated in the order (L495) and reproduced by the @0.7 check (C2: `a` 2,535,834,082, `c` 1410.88, `max_rel_resid` 0.005, 49 points):

own peak = **2.5358e9 + 1410.88 × L²** bytes

Kaylee (N41) recomputed the same coefficients (a 2.53583e9, c 1410.88) and found the maximum residual is **0.503 %**, not “≤ 0.49 %” as the order says in §g and in EV-F3; the order also says “0.5 %” in one place. The points are clustered: 43 of 49 at L 992–1,041, 3 at 1,176–1,181, 3 at 1,769–1,780. The extrapolation for the remaining batches runs from 1,780 to 1,971 tokens. Kaylee also tried linear and quadratic alternatives; **all models put all six remaining zero-padding batches above 7.0e9**.

Kaylee N39: the order cites `masking_utils.py` L339–L344, which is `_can_skip_bidirectional_mask_xpu`. The correct span is `_ignore_causal_mask_sdpa` L267–308, key line L307. The conclusion (mask skipped when the padding mask is all ones) stands. Which kernel actually runs (math, L×L materialised) remains speculation (N45).

Generated length does not explain the step: batches 361 and 362 generated the same maximum length; only the zero-padding one raised the peak. Zero-padding batches also ran slower per row (order L493: 3.4–3.5 s against 1.3–2.0 s in that stretch). The abort itself is at batch 364, L 1,780, peak 7,001,188,352 (order L487).

### 4.5 Why resume was withdrawn

`e5s1_check.py` @0.7, on the real copy, projects remaining batches in a fresh process. Zero-padding batches use the fit; padded batches use the smoke-S padded bound 4,030,207,488. Printed remaining zero-padding projections (`evidence/check-real-0.7.txt`, and a re-run of the same tool against the same copy while writing this file, last line identical, exit 1):

| Remaining batch | L (tokens) | Projected own peak (bytes) |
|---|---|---|
| 391 | 1,901 | 7,634,479,667 |
| 401 | 1,914 | 7,704,452,343 |
| 408 | 1,923 | 7,753,174,320 |
| 420 | 1,942 | 7,856,782,415 |
| 431 | 1,964 | 7,978,022,299 |
| 437 | 1,971 | 8,016,885,034 |
| 446 (1 row) | 1,994 | 3,237,048,620 (per-row model; see N42) |

The six batches 391–437 all exceed both the 7.0e9 guard and the 7,385,120,768 free memory recorded at the original session start. The check therefore prints, and the order requires every citing card to quote:

`E5S1 STOP: C4 failed; max projected per-batch peak 8016885034 B at batch 437 (go_max 6500000000, limit 7000000000); no relaunch, Trinity re-plans`

Integrity checks I0–I12 and curve checks C1–C3 all passed on this copy. C4 failed (`n_over` 6, first over batch 391). `E5-pin-resume` is withdrawn and is not to be carded (order L580).

Kaylee N42: batch 446 is a one-row no-mask batch, not a padded one. 3.24e9 holds only if the L² term is per row; otherwise it is about 8.15e9. Under route B that would still be under 8.5e9 but above the card's quoted maximum. Under route A the 7.0e9 guard applies, so the point is irrelevant to the A launch itself.

### 4.6 Kaylee N39–N45 (all INFO)

From `RECHECK-eval@0.7.md` L105–112, in brief:

- **N39.** masking_utils line citation wrong; conclusion stands (see §4.4).
- **N40.** The order's “score.py L313 plans each run with its own batch” is the `smoke()` path. Full scoring loads by row id (L360–366) and does not check batch. The conclusion that score.py accepts S@4 with T@8 stands; a shim replay gave rc 0.
- **N41.** Max residual 0.503 %, not ≤ 0.49 %; points clustered; extrapolation 1,780 → 1,971.
- **N42.** Batch 446 is no-mask; 8.15e9 if the L² term is not per row.
- **N43.** Route A runtime is inconsistent and probably low. The options table says 1.7–2.5 h; the question and card say 2–2.5 h. At batch 4, 611 of 893 batches (about 68 % of rows) are zero-padding. At batch 8, zero-padding batches in 300–363 ran at about 2.9 s/row vs about 1.4 s/row for padded batches. **2.5–3 h is plausible.**
- **N44.** `E5-S-gate`'s filter can match a wrapper or parent whose command line contains `eval.py`. That is a false STOP and fails safe.
- **N45.** `enable_gqa=True` is set only when there is no mask; “math kernel” stays unverified.

---

## 5. Options considered and the decision

Order L505–515 and §9 item 11. Trinity's recommendation was A. Kaylee: A, B and D are sound to card after a Matt ruling; C is sound only as a question option (no code, line or block exists to card).

| Option | What it is | Peak / identity | Ruling needed |
|---|---|---|---|
| R0. Identical `E5-pin` resume | Withdrawn. Would resume `out-S` and is projected to stop at batch 391 (exit 5, or exit 3 after spilling). Six such stops if spilling banks one batch at a time. | 7.63e9 at 391 | Rejected in the order; not to be carded |
| **A (recommended)** | Fresh S at `--batch 4` in a new dir `out-S-b4`. RUN PIN, SCORE PIN and code unchanged. A `--batch 4` launch against `out-S` would be exit 7, nothing written. | Longest full zero-padding batch at batch 4: 1,973 tokens. *Estimate* 5.1e9–5.3e9 if the L² term is per row (Kaylee reproduced 5.282e9 at batch 879). If that assumption is wrong, the estimate is 8.03e9 and the unchanged 7.0e9 guard stops the run with exit 3 after a written batch (fails safe). Runtime *estimate* 1.7–2.5 h in the table; 2–2.5 h in the question; Kaylee N43: 2.5–3 h is plausible. S would be batched 4 while T is batched 8, which can change greedy text (smoke `replay_b1`: 3 of 8 rows). The stopped `out-S` (2,920 batch-8 rows) stays as a record and is not scored under A. | **Needs Matt's ruling** (departure from “batch 8 for both”) |
| B | Resume `out-S` with `--peak_limit 8500000000`. `--peak_limit` is not in the run identity. | 8.017e9 at batch 437, under 8.5e9 but above 7.385e9 free. Works only if the Windows driver spills into system RAM (*unverified* on this laptop; the GPU also drives the display). Without spilling: exit 5 at 391, then A or C anyway. | **Needs Matt's ruling** (accept running past VRAM) |
| C | Code change so no batch takes the no-mask path (example given: left-pad every batch by one token). New RUN PIN; T and S both rerun. | Padded path, ≤ about 4.4e9 | Not cardable in @0.7; would need a new order round |
| D | Hold | No baseline, no S comparison scored | Sound as a hold |

The question put to Matt is quoted in full at order L515 (recommended wording: “**A** (recommended): rerun the baseline from the start in a new folder with batches of 4 instead of 8.…”).

**Decision.** Matt ruled A on card `t382s1311` at 2:39 AM PT, 2026-11-16 (`E5-S-GATE-RECORD.txt` L1). The exact widget wording of that card is **not recorded** in a box file (see §11). Under A, the 2,920 already-written batch-8 rows remain on the laptop until E9 and on the box at `e5-s1/out-S`; they are not the scored baseline (order L517).

---

## 6. Route A procedure and gates

From order L588–641, L656–660, L677, L683. Each laptop step is its own Matt card. Kaylee diff-checked the lines before they were to be carded (`RECHECK-eval@0.7.md` §2, PASS).

1. **E6-S** (read-only). Must show `NO LOCK`, `STATUS aborted`, `ABORT-1.json pid=9448 exit=3`, so nothing is running in `out-S`. `out-S` is left as it is.
2. **E5-S-gate** (own card), then **E5-gpu-pid** for each hidden nvidia-smi name, then **E5-free** recorded.
3. **E5-b4-pin** (own card; only after Matt rules A). New dir `out-S-b4`, new logs `eval-S4.out` / `eval-S4.err`. It must not touch `out-S` or `eval-S.out`.
4. **E6-S4** polls while it runs. After E4 and E5-b4 have both exited 0: **E7-A** (hash and copy), then box scoring (route A), the **A1** check, **E8**, then **E9**, then the result note with **A2**'s verbatim wording.

**E5-S-gate** (order L557–563), read-only:

```powershell
Get-CimInstance -ClassName Win32_Process | Where-Object { ($_.Name -like 'python*' -or $_.CommandLine -like '*eval.py*') -and $_.ProcessId -ne $PID } | Select-Object ProcessId,Name,CreationDate,CommandLine
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```

Expect: no `Win32_Process` line (else STOP, Trinity rules); compute-app rows logged. Trinity's 9:00 PM PT ruling (order L538–544): the gate is no live python or eval.py, judged by `Win32_Process` Name and CommandLine, never by the nvidia-smi name column. `explorer.exe` and `dwm.exe` do not stop the gate. A hidden nvidia-smi name is resolved with **E5-gpu-pid**.

**E5-free** (order L552–555), before any S launch:

```powershell
nvidia-smi --query-gpu=memory.free,memory.used,memory.total --format=csv,noheader,nounits
```

Expect one line `<free MiB>, <used MiB>, <total MiB>`, recorded on the card. The launch guard remains eval.py's `--min_free` (default 7.0e9): exit 10 at start, then Matt sets a floor, then the matching floor line (`E5-b4-pin-floor`).

**E5-b4-pin** (order L594–599), set P, batch 4:

```powershell
Start-Process -FilePath C:\Users\mdk32\venvs\bia562-train\Scripts\python.exe -ArgumentList 'eval.py','--model','C:\Users\mdk32\models\Qwen2.5-3B-Instruct','--mode','fewshot','--fewshot','fewshot.json','--rows','eval_rows.jsonl','--expect_manifest_sha','0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d','--out_dir','out-S-b4','--tag','qwen25-3b-base-fs','--pin_transformers','5.22.2','--batch','4' -WorkingDirectory C:\Users\mdk32\lb-eval-bluebird-v1.0-r03 -RedirectStandardOutput C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\eval-S4.out -RedirectStandardError C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\eval-S4.err -WindowStyle Hidden -PassThru
```

Expected last line (order L599): `EVAL_DONE qwen25-3b-base-fs 3569 complete <content sha>`. The batch-4 plan is 893 batches (892 × 4 + 1). Kaylee's plan file agrees: 893 batches, 611 zero-padding, last batch 1 row (`evidence-eval@0.7/12-batch4-plan.txt`).

Card text specified for E5-b4-pin (order L677): “Start the baseline run again from the beginning in a new folder, with batches of 4 instead of 8 (version pin 5.22.2, memory guard unchanged at 7.0 GB). The stopped run's 2,920 answers stay where they are as a record. Estimated peak 5.1–5.3 GB (an estimate; the guard stops the run on its own if it is wrong), about 2–2.5 hours. If it stops, nothing is retried without you.” → **Start** / **Hold**.

**E6-S4** (order L606–615) is a read-only poll of `out-S-b4\eval.lock`, the run JSON status and sessions, any `ABORT-*.json`, tails of `eval-S4.out` and `eval-S4.err`, `nvidia-smi` (name, memory used/total, temperature), and battery status. Exit of a detached run is read from the last `.out` line (order L292–303): `EVAL_DONE` means 0; `ABORT n` means n; `REFUSED` means 7; an empty `.out` with `eval.py: error:` in `.err` means 2. A progress line plus a live lock pid means still running.

**Stop handling.** On any stop of `E5-b4-pin`, run **E5-S4-keep** (order L617–626) before any relaunch (a relaunch truncates `.out` / `.err`). Copy named files to `/workspace/littleblue-eval-v0.5/runs/r03/e5-b4-s1/` and hash-check them. Exit 10 at the start (an ABORT whose pid matches no session) also requires the keep block first, then a Matt-set floor and `E5-b4-pin-floor` (L660, N35). No retry without Matt.

**E7-A** (order L627–637), after both E4 and E5-b4 have exited 0: hash `out-T`, `out-S-b4`, smoke dirs, `pre-T`, and the `.out`/`.err` logs; CopyToBox the named result files into `runs/r03/out-T/`, `runs/r03/out-S-b4/`, and `runs/r03/`; every laptop hash must equal the box `sha256sum`; then `sha256sum -c EVAL.SHA256` in both result dirs.

**Box scoring, route A** (order L639–641; no card): `score.py` with the same RUN PIN, SCORE PIN and adapter sha as the default scoring line; the S path is `runs/r03/out-S-b4/predictions-qwen25-3b-base-fs.jsonl` (not `out-S`).

**A1** (addendum, still applies): immediately before E8, a read-only `powercfg` check. `STANDBYIDLE` and `HIBERNATEIDLE` Current AC Power Setting Index must both be `0x00000000`, and the active scheme must be `381b4222-f694-41f0-9685-ff5bb260df2e` (Balanced). If any of these differs or cannot be read, stop; do not run E8. Restore values are the pre-E1 AC indices E0a logged, in decimal; Emma is to cite the E0a log line on the E8 card. Emma reported E0a logged 0x0 and 0x0, so the addendum's default fill-ins are `0` and `0`, void if the log line is not that.

**E8** (order L456–464): restore those AC indices only if the active scheme is still the recorded GUID; re-check PID 21896's Id, StartTime and Path against E0a.

**E9** (order L466–468), later, after the box hash check and scoring, own card: `Remove-Item` of the laptop work dir `C:\Users\mdk32\lb-eval-bluebird-v1.0-r03`.

**A2** (addendum): the result note must state verbatim: “transformers 5.22.2, pinned by your ruling (b) at 15:26 PT (check PINNED_UNVERIFIED; greedy merged config and processors [] recorded every session)”.

---

## 7. Governance and review chain

- **Matt** certifies each laptop command on its own approval card (order header L3; addendum L3; every §g step). Order @0.7 itself is marked “ORDER DRAFT @0.7, NOT GO'D” in its header; the per-command cards are the live authorisations.
- **Trinity** (Architect) writes and amends the order. @0.7 answers Kaylee's `RECHECK-eval@0.6.md` (FAIL on N29 MED, plus N30–N38), Trinity's 9:00 PM PT process-gate ruling, and the real E5-S1 copy (order L3).
- **Kaylee** (review) diff-checks before cards go out. `RECHECK-eval@0.7.md`: PASS, 2026-11-15 10:15–10:55 PM PT. She did not run Trinity's `tests/e5s1_suite.py` or `tests/e5s1_mutants.py` (independence rule); she replaced them with her own fixtures. Trinity's 27/27 and 27/29 counts are therefore not verified by Kaylee.
- **Emma** (Chief of Staff) operates the laptop commands, copies named files to the box, and records gates. She does not rewrite the order.
- Prior abort ruling: card `t369s1265` (7:42 PM PT, order L11) sent the exit-3 facts to Trinity for amendment rather than authorising a resume.
- Route-A ruling: card `t382s1311`, 2:39 AM PT 2026-11-16 (`E5-S-GATE-RECORD.txt`).
- Live-app processes are not to be stopped as a side effect of this eval (the Streamlit pids in §8 were logged and left untouched). E8 later re-checks pid 21896 against the E0a record (order L462–464).

---

## 8. Results so far

**On the box, filed.**

- Smoke T and smoke S are complete (64 rows each, exit 0, `E3_pass` true). See the timeline.
- Full S at batch 8 is aborted: 2,920 / 3,569 rows kept, exit 3, cause and hashes in §4.1. The @0.7 check on that copy is STOP C4, printed line quoted in §4.5. I0–I12 and C1–C3 passed. Re-run of `/workspace/littleblue-eval-v0.7/tools/e5s1_check.py` against the same copy while writing this file printed the same last line and exited 1.
- `out-S` on the laptop is to be left as that aborted record. The box copy is `runs/r03/e5-s1/out-S/`. The stage path `runs/r03/out-S/` is empty (E7's default copy target, not used under route A).
- `runs/r03/out-T/` is empty. Full T results have not been copied to the box.
- Gate record `/workspace/littleblue-eval-v0.5/runs/r03/e5-b4-s1/E5-S-GATE-RECORD.txt` (sha256 `eabf1d905ab4d37b76a73aa34bbfd1bdba0e60d3dd54cab6c691f68d2a1f468c`, mtime 2026-11-16 2:40:53 AM PT), quoted in full:

```
E5-S-gate record, route A (Matt ruled A, card t382s1311, 2026-11-16 2:39 AM PT). Recorded by Emma.
E6-S: NO LOCK; STATUS aborted; ABORT-1.json pid=9448 exit=3; GPU 0/8151 MiB; BatteryStatus 2, 100%.
E5-S-gate Win32_Process hit 2 python.exe -> STOP; Trinity requested full CommandLine.
Full read (Format-List), verbatim:
1344 parent 1428 dwm.exe created 11/12/2026 3:20:04 AM, CommandLine empty
21896 parent 2304 python.exe created 11/12/2026 2:20:35 PM: "C:\Users\mdk32\venvs\littleblue-app\Scripts\python.exe" "C:\Users\mdk32\venvs\littleblue-app\Scripts\streamlit.exe" run app.py --server.address 127.0.0.1 --server.headless true
2580 parent 21896 python.exe created 11/12/2026 2:20:35 PM: "C:\Users\mdk32\AppData\Local\Programs\Python\Python312\python.exe" "C:\Users\mdk32\venvs\littleblue-app\Scripts\streamlit.exe" run app.py --server.address 127.0.0.1 --server.headless true
Disposition under Trinity's pre-ruling (1): 21896, 2580 = pre-existing app server, not eval, not on GPU. 1344 = dwm.exe (non-python). Gate PASS with exception logged. Neither process touched.
```

- E6-S therefore matched the route-A precondition in order L589. The two python processes are a parent/child Streamlit pair for the pre-existing littleblue-app server (created 2026-11-12 2:20:35 PM). 1344 is `dwm.exe`. Under the pre-ruling recorded here, the gate passed with that exception. Neither process was touched.
- `E5-free`'s numeric line is **not recorded** in this file (the record has E6-S's `GPU 0/8151 MiB`, which is used/total, not the `E5-free` free/used/total line).
- `runs/r03/e5-b4-s1/` contains only this gate record. There is no `eval-S4.out`, no `out-S-b4/` copy, and no `E5-S4-keep` hash list on the box. `EVAL_DONE` for the batch-4 rerun is **pending**.

---

## 9. Pending

Leave the following clearly open until the named artifacts exist on the box. Do not fill them from memory or from an unfiled poll.

1. **`E5-b4-pin` launch record** (Start-Process PID, lock pid, `VERSIONS` / `TRANSFORMERS` / `GPU_FREE` / `MERGED_GENERATION_CONFIG` lines). Not filed on the box.
2. **`E6-S4` polls** while the run is in progress (lock, status, abort list, `.out` / `.err` tails, nvidia-smi, battery). Not filed on the box.
3. **`EVAL_DONE`.** Expected last line of `eval-S4.out`: `EVAL_DONE qwen25-3b-base-fs 3569 complete <content sha>` (order L599). Confirm exit 0 from that line, run JSON `status` `complete`, 3,569 predictions, no `ABORT-n.json` that belongs to a failed session.
4. **`E7-A`** (own card): laptop hashes and CopyToBox of `out-T`, `out-S-b4`, smoke and pre-T files, and `eval-T.out` / `eval-T.err` / `eval-S4.out` / `eval-S4.err`, then box `sha256sum -c EVAL.SHA256` in both result dirs.
5. **Box scoring, route A** (order L641), into `runs/r03/score`. Verdict **pending**.
6. **A1** powercfg check (addendum), immediately before E8.
7. **E8** (own card), quoting the E0a log line for the AC indices, scheme GUID `381b4222-f694-41f0-9685-ff5bb260df2e` unless A1 fails.
8. **E9** (own card), after the box hash check and scoring: delete the laptop work dir.
9. **Result note**, including A2's verbatim sentence: “transformers 5.22.2, pinned by your ruling (b) at 15:26 PT (check PINNED_UNVERIFIED; greedy merged config and processors [] recorded every session)”.
10. Optional post-run comparison, named in the order (L510, L517): the 2,920 shared ids in `e5-s1/out-S` (batch 8) versus the new `out-S-b4` outputs (batch 4), to measure the batch-size effect on greedy text.

If the batch-4 run stops before `EVAL_DONE`, the next filed step is `E5-S4-keep`, then Trinity, not a relaunch.

---

## 10. Additional source files

sha256 values recomputed on the box while writing this file, unless noted as taken from the named manifest.

| File | sha256 |
|---|---|
| `runs/r03/e5-s1/eval-S.out` | `d7278a0d7bd4bfdaa3ddfc9ea444cf0001ad36efab1a7dd6d4a7b9ce66e1bc61` |
| `runs/r03/e5-s1/eval-S.err` | `4c3bbc54d154b53b7cfab61699b7e6020302e7695413b7c171d560f4a0ddfa0d` |
| `runs/r03/e5-s1/out-S/ABORT-1.json` | `c0e97ac59269dfa01a116e3234ce1889913faf5cbd2b57f6adcc7092f646be9e` |
| `runs/r03/e5-s1/out-S/run-qwen25-3b-base-fs.json` | `0b0e2d523aa1406c995b7653012d3a8a33ddd9f222b38d98decdace74fcf79fe` |
| `runs/r03/e5-s1/E5-S1-EVIDENCE.txt` | `85e988ab6681d2bbd7b194d27de0b3b65bd47afb6f2614f4fd2dbf4763b9a995` |
| `runs/r03/e5-b4-s1/E5-S-GATE-RECORD.txt` | `eabf1d905ab4d37b76a73aa34bbfd1bdba0e60d3dd54cab6c691f68d2a1f468c` |
| `runs/r03/smoke-S.out` | `4b8b2cab351ced18d554494e64f1af0580e2498e01d159db26f4302a0f3819b9` |
| `runs/r03/out-smoke-S/run-qwen25-3b-base-fs.json` | `2b30d3fc409db148fb5027206ed14f24f1bf36d3a3614df1176e4a2b1384739f` |
| `littleblue-eval-v0.7/evidence/check-real-0.7.txt` | listed in `V07-FILES.SHA256` as `75076fc1f1912f7b1df2f11214a9a1ba484d16262951520508a1c12e0a782020` |
| `littleblue-eval-review/evidence-eval@0.7/12-batch4-plan.txt` | used for the 893-batch / 611 zero-padding plan; not re-listed in V07-FILES |

Kaylee's input-sha list (`RECHECK-eval@0.7.md` L18–25) matches the order, DIFF, tool, and e5-s1 shas above.

---

## 11. Facts not recorded on the box, or not verified from files

These items appeared in the operator brief for this write-up and/or in staff journal memory. They are **not** copied into §§1–8 as established results, because no supporting file was found on the box, and transcript search from this writing session did not return the parent chat or the raw laptop command output.

- **Exact text of card `t382s1311`.** The gate record states that Matt ruled A on that card at 2:39 AM PT. The widget wording itself is not in a box file.
- **Full T completion** (claimed exit 0, 3,569/3,569, around 5:50 PM PT on 2026-11-15). `runs/r03/out-T/` is empty. The order mentions an Emma-reported E4 peak of about 5.28e9 (L495) as a cross-check of the fit, not as a filed T result.
- **`E5-free` line** (free/used/total MiB immediately before launch). The gate record has only E6-S's `GPU 0/8151 MiB`.
- **`E5-b4-pin` Start-Process PID, lock pid, start time, and the first `eval-S4.out` lines.** No launch log is in `e5-b4-s1/` or elsewhere under `runs/r03/`.
- ~~Any `E6-S4` poll~~ Now filed: the 3:59 AM PT poll output is at `e6-s4/E6-S4-poll-2026-11-16-0359PT.txt` (status running, 723/893 batches, peak_alloc 4,533,673,472 B, GPU 4724/8151 MiB at 75 C, lock pid 27020 started 02:41:04, no ABORT files, battery line empty). This also fixes the run's start time and lock pid.
- **Trinity's pre-ruling text** beyond the one-sentence disposition in `E5-S-GATE-RECORD.txt`.

When E7-A (or, on a stop, E5-S4-keep) lands the missing files, this document should be updated from those copies, not from recollection.


## 12. Result and owner override (added 2026-11-16 ~5:05 AM PT)

The route A S rerun finished exit 0 at 4:26 AM PT (EVAL_DONE qwen25-3b-base-fs 3569 complete c47eda6e…9930; peak_alloc 5,032,707,072 B; e6-s4/E6-S4-poll-2026-11-16-0455PT.txt). For E7-A, all 10 files were copied, every laptop hash matched the box sha256sum, and `sha256sum -c` passed for both folders. Box scoring (score/REPORT.md sha eecf22aa…d4e5) gave T the verdict DEGENERATE (format 2079/2090; accuracy 0.7459 vs a floor of 0.8149; four probe bars failed), against a baseline of 0.0278. Matt judged T a PASS by owner override; see OWNER-OVERRIDE-T-PASS.md (certified on card t391s1356, 5:02 AM PT).

## 13. JSON fix follow-up (added 2026-11-16 ~5:09 AM PT)
Breakdown of the 11 malformed outputs: 7 truncated at the 128-token cap, 3 spans written as bare strings, and 1 slot mismatch. Planned fix: raise the cap and add schema-constrained decoding, then one full T rerun and a re-score, on Matt's GO at 5:08 AM PT. Details are in JSON-FIX-PLAN.md. E9 is held until the rerun is done.
