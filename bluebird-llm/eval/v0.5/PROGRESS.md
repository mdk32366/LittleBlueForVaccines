# Bluebird eval @0.2 — PROGRESS (Trinity)
Started 2026-11-15 10:12 PST. Stage copied from v0.1 (cp -a, pycache removed). Answers Kaylee REVIEW-eval@0.1.md (64eea77c…7b94, ACCEPT-WITH-CHANGES).
Baselines for the end check: /tmp/v01-stage-baseline.sha (42 files), /tmp/v00-stage-baseline.sha (11), /tmp/orders-baseline.sha (@0.0 4f6b6c9c…, @0.1 0d7acd06…).
Rules: ≤4 parallel jobs, TMPDIR inside each copy, df before each heavy run, stop if < 8 GB free.

## Steps
- [x] R1 (code+tests written; suite pending) score provenance per run (score.py, tests)
- [x] R2 (HARDEN + scen_kill guard) scen_kill harness hardening (Kaylee HARDEN)
- [x] R3 (scen_outplan + N33b in spec) exit-4 outside --limit test + mutant N33b
- [x] R4 score.py FA_CONDITIONS + verdict_note (order card pending) REPORT.md + §10 card conditions, A-T-only INCONCLUSIVE wording, her sim figures
- [x] #5 E0b card line (no python on GPU): order §g E0b row + §10a #5
- [x] N4 FIXED: PUBLIC_BRANDS + assert, rows rebuilt (rn 300 changed) rn real-brand residual (TENIVAC/MENACTRA)
- [x] N5 eval.lock + no 6/8 ABORT in run dirs + tests running-dir ABORT consistency + single-runner lock
- [x] N7 stub_harness OUT arg, copy_stage allow-list, tearDownModule stage guard suite never writes in stage; copy_h allow-list
- [x] I2 full stderr runmut full stderr / attribution
- [x] suite 93/93 OK, mutation 119/120 (M28 equivalent), EVAL-INPUTS reissued last, order @0.2, DIFF-0.1-to-0.2.md, originals verified

## Log
- ~10:20 code edits done for R1-R4,N4,N5,N7,I2; manifests RUN/SCORE/EVAL written. Next: suite.
- ~10:27 suite A: 4 Provenance errors (copy allow-list lacked build_eval_rows.py for mkmanifest) → fixed; Provenance 5/5 OK.
- ~10:31 Shim: 3 fails = real @0.2 issue: kill -9 leaves a stale eval.lock; a refused resume removed it (dir changed). Fix: refused/early-exit launch restores the stale lock byte-identical; kill test now expects the stale_lock repair first. Mutant N60 added.
- ~10:35 FULL SUITE (LBE_REBUILD=1, Shim 4 jobs): Ran 93, OK (247 s).
- 10:37 sim pools capped at 4 (LBE_SIM_JOBS/LBE_STUB_JOBS); v0.1 mutation artifacts removed from the v0.2 copy (kept in v0.1 stage; logs → /workspace/lbe-tmp/v01-mutlogs). Running sim 4000 + stub harness on the @0.2 rows. Next: mutation run (4 jobs).
- 10:42 sim 4000 done: table identical to @0.1 (rn ids/src unchanged); stub harness 18/18. Starting mutation run (120 entries, 4 jobs, TMPDIR in each copy).
- 10:59 (resumed after interrupt) mutation run pid 1077261 alive, 47/120 lines, SURVIVED_A so far M28 M32b M33-M36 (→ stage B Shim). Not restarted.
- 11:00 #5 done; @0.2 template/fill.py/DISPOSITION-0.2 installed in order/; tests/RESULTS.txt = 10:35 full suite (93 OK).
- 11:03 provisional ORDER-bluebird-eval@0.2.md written (mutation placeholder, sha 8a6cc056…); DIFF-0.1-to-0.2.md written by order/fill_diff.py (mutation killers pending). Both refilled after the run.
- 11:50 (resumed) runmut pid 1077261 alive; stage A done (120; no non-eval.py survivors); stage B 7/19 done: M28 SURVIVED (triaging), M32b M33 M34 M35 M36 N26 KILLED by named Shim tests. Not restarted.
- 12:15 stage B 15/19: only M28 survived (equivalent under @0.2: the post-lock re-check '(prev is None and PRED exists)' duplicates the state-check guard). Plan: after run ends drop that redundant clause (run json written before predictions, so the run-json byte re-check covers the race), rerun suite + all eval.py mutants.

- 12:30 mutation run finished (exit 0): 119/120 KILLED; M28 equivalent survivor (duplicate post-lock orphan-predictions guard). Keeping it as SURVIVED, not deleting a safety check to game the tally. Earlier plan to remove it is superseded. All 119 kills have named tests; no setup-crash kills. N59 additionally trips tearDownModule, but its named stub test also fails. Required M32b/ok, N33/exit4, N33b/outside-plan and M25/tampered-inputs killers are all present.
- 12:35 final suite (LBE_REBUILD=1, 4 shim jobs): Ran 93 tests, OK.
- 12:40 final: order/fill_diff.py → DIFF-0.1-to-0.2.md; order/fill.py → ORDER-bluebird-eval@0.2.md + mut/MUTATION-RESULTS.md + manifests (last stage write). Preservation: v0.1 stage 42 files OK, @0.0 stage 11 files OK, @0.0/@0.1 orders OK. Scratch /workspace/lbe-tmp removed. Final shas are in the order/report (this file is covered by EVAL-INPUTS, so they are not repeated here).

# @0.3 (answers Kaylee RECHECK-eval@0.2.md 4547ad28…5268, PASS conditional)
- 13:20 stage v0.3 = cp -a v0.2 (pycache removed). Baselines: /tmp/v02-stage-baseline.sha (48 files), /tmp/orders02-baseline.sha (@0.0–@0.2).
- 13:22 KayleeM28 class (4 tests: torn lock bytes, no 5 s wait, stale lock inode/mtime, read-only dir → 7) added to tests/test_eval.py only; passes on the original. RUN/SCORE pins unchanged (0769b861…, 8c4b3042…59bd1e).
- 13:23 scope (parent): suite + M28 alone; the other 119 kills carried from @0.2 (code byte-identical; tests only added). M28 run started.
- 13:27 M28 alone (runmut M28, stage A, TMPDIR in its copy): KILLED by KayleeM28.test_orphan_in_readonly_out_dir_refused_7, …fresh_torn_lock_refused_at_once, …stale_lock_same_inode_and_mtime, …torn_lock_refused_7_lock_bytes_untouched. MUTATION-RESULTS.jsonl: 120/120 (M28 updated in place, 119 carried). SURVIVORS.json corrected.
- 13:38 full suite 97/97 OK (236.6 s; first attempt flagged my own mid-run template edits via the stage-write guard, so it was re-run with the stage untouched). Preservation checked: v0.2 48/48 and no additions, v0.1 42/42, @0.0 11/11, ORDER@0.0–@0.2 OK; RUN/SCORE pins unchanged. DIFF-0.2-to-0.3.md written; next: fill.py → ORDER@0.3 + EVAL-INPUTS (last write).

# @0.4 (answers Kaylee RECHECK-eval@0.3.md 4a1cc3f1…1168: §10 card PASS, §g FAIL N15; N16–N18)
- 14:24 stage v0.4 = cp -a v0.3 (pycache removed). Baselines: /tmp/v03-stage-baseline.sha (59 files), /tmp/orders03-baseline.sha (@0.0–@0.3).
- 14:34 §g rewritten in full (N15), E6 (N16), N17 wording, N18 (fill.py: single scope sentence, all killers, pin STOP check); DISPOSITION-0.4.md; suite 97/97 OK (290 s, same names); DIFF-0.3-to-0.4.md; preservation OK; RUN/SCORE pins unchanged. Next: fill.py → ORDER@0.4 + EVAL-INPUTS (last write). No mutation run.

# @0.5 (answers Kaylee RECHECK-eval@0.4.md 5fbd1c03…ed63: SEND BACK, narrow; N19 MED, N20–N22 LOW, N23 INFO)
- 14:50 stage v0.5 = cp -a v0.4 (no pycache present). Baselines: /tmp/lb05/*.sha (v0.4 54 files, v0.3 59, v0.2 48, v0.1 49, @0.0 13; orders @0.0–@0.4).
- 14:50–14:54 suite on a copy of v0.5 (TMPDIR outside): Ran 97, OK (235 s), same 97 names → evidence/suite-0.5.log; tests/RESULTS.txt kept (the @0.4 run).
- 14:54–15:08 §g: E0b outcome table + E0b-pin-floor/E0b-floor (N19), last-.out-line rule + E6-smoke + .err tails (N20), E0a AC stop + weights line (N21), E3a–E5 × 4 sets (N22), N23 a–f. Probes (final template): argv 35/35, e0b variants 15/15, exit markers 20/20, box replay 11/11, PowerShell parse 30 blocks OK (E8 unfilled fails to parse by design; filled OK). DISPOSITION-0.5.md, fill.py → @0.5, DIFF-0.4-to-0.5.md. No code or test change; pins unchanged; no mutation run. Next: fill.py → ORDER@0.5 + EVAL-INPUTS (last write).
- 15:08–15:16 found a live E0b result landed in v0.4/runs/r03/pre-T at 15:08 (not ours; 5.22.2, min_free PASS, free 7385120768): noted in §g/DIFF as row P; set-switch rule added for a later start-of-launch exit 10; §g ellipses replaced by full printed lines; probes re-run on the final template (same results, same evidence shas). Refill ORDER@0.5.
