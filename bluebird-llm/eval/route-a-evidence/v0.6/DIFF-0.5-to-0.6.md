# DIFF ORDER-bluebird-eval@0.5 → @0.6 (for Kaylee's diff-only check)

Base: `ORDER-bluebird-eval@0.5.md` `7187d5adf48bb525b68f945791fa8dd39feace54bf6aca9698095d7fc08a7f51` (unchanged). Cause: Matt's card t369s1265 (7:42 PM PT, relayed by Emma): E5-pin exit 3 on `out-S` → order amendment, Kaylee diff-check before any card. Mechanical diff: `diff -u ORDER-bluebird-eval@0.5.md ORDER-bluebird-eval@0.6.md` (`evidence/order-0.5-0.6.diff`).

## Not changed
- No code, no test: eval.py `429751f6…`, evalcore.py `2d1d2f9b…`, `eval_rows.jsonl` `dd3fc66d…`, `fewshot.json` `a27d1f08…`, score.py `a4d7a374…`, evalstats.py `9464f55d…` are the v0.5 stage's files, not copied. **RUN PIN `0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d` and SCORE PIN `8c4b3042ba5abf0134b9d0075170ec55585e41092e60e51f411642b59b59bd1e` unchanged.** No suite run, no mutation run (nothing to kill).
- §10 GO card byte-identical (checked by slicing `## 10. GO card` … `## 10a.` in both files).
- Every @0.5 §g PowerShell block is present byte-identical and in order (30 blocks; `evidence/ps-parse-0.6.txt` (4)). Set P stays; no floor change; `--peak_limit` stays 7.0e9; landing root stays `/workspace/littleblue-eval-v0.5/runs/r03/`. Addendum A1-A2@0.0 still applies.

## Changed (order text)
| # | Where | Change |
|---|---|---|
| D1 | header L1–L9 | @0.6 status; @0.5 + addendum shas; record stage; recommendation; @0.5 gate kept |
| D2 | §0 | rows: Matt card t369s1265; order @0.5; addendum; RECHECK@0.5; smoke S as a source |
| D3 | §g, new subsection before **Resume** | *E5-pin stopped with exit 3 on out-S*: Emma-reported facts (labelled); eval.py mechanism (peak = `max_memory_allocated`, session-cumulative, checked after the batch is written; identity incl. `batch`, excl. `peak_limit`/`min_free`/pin; M2); 82 remaining batches, not 83; why prompt length is not the cause (fresh smoke S ran batches 381 and 445 at ≤ 4.03e9); options table R / (a) / (b) / (c) with projected peaks; validity and comparability; pin and floor unchanged; sequence; **new blocks E5-S1-keep, E5-pin-resume (= E5-pin byte for byte), E5-S2-keep**; box landing + `e5s1_check.py` GO/STOP rule; exit reading and stop rule; E7 note; proposed card texts |
| D4 | §g **Resume** line | appended: copy `.out`/`.err` to the box before any relaunch |
| D5 | §j | @0.6 evidence list; stage note (my `__pycache__` write, removed); not tested on the box |
| D6 | §k | EV-F3 (in-session allocation growth; post-run) |
| D7 | §9 | item 10 |
| D8 | §11 | new 11-00a table answering Emma's relay |
| D9 | changelog | @0.6 line |

## New files (record stage `/workspace/littleblue-eval-v0.6/`, listed in `V06-FILES.SHA256`)
- `tools/e5s1_check.py`: box-only, read-only check of the copied stopped session (I0–I7 integrity; curve; projection; GO iff integrity holds, no single-batch jump > 1.0e9, projection ≤ 6.5e9; slope = max of whole-session average, last-200 and last-50 least-squares fits, each × its prompt-token ratio).
- `evidence/MECHANISM-0.6.md`, `peak_model.py` → `peak-model-0.6.md`, `resume_replay.py` → `resume-replay-0.6.jsonl`, `check_replay.py` → `check-replay-0.6.txt`, `ps_check06.py` → `ps-parse-0.6.txt`, `order-0.5-0.6.diff`.

## What to check (suggested)
1. E5-pin-resume == E5-pin (text and argv); it resumes the reported state with no exit 7 and keeps the 2,920 rows byte-identical (`resume-replay-0.6.jsonl`).
2. The smoke-S argument: full-run batch indices of the 8 smoke batches (`peak-model-0.6.md`; asserted against `plan_batches(..., limit=64)`), and its peaks.
3. `e5s1_check.py` rules and the 8 cases in `check-replay-0.6.txt` (expected GO only for the reported-numbers case).
4. E5-S1-keep happens before any relaunch (N28), and the stop rule forbids a second resume card after another exit 3 or a 5.
5. Not tested on the box: the growth's cause; CUDA bit-identity across processes; Windows `Get-CimInstance` / `Get-FileHash` / `nvidia-smi` lines (parsed; hash and Test-Path lines run under pwsh on Linux only); the driver's system-memory fallback.
