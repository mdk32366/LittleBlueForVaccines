# DIFF ORDER-bluebird-eval@0.6 → @0.7 (Trinity, Sun 11/15/2026 PT)

@0.6 `ORDER-bluebird-eval@0.6.md` (`ff8f6f57e9108a11df16bf165f45ff83872cd49678e8b62e56eb7cbb6916b6e6`) and its stage `/workspace/littleblue-eval-v0.6/` are left byte-unchanged, as are @0.0–@0.5, the v0.5 stage (67/67) and the addendum. The full textual diff is in `evidence/order-0.6-0.7.diff`.

## Unchanged
- RUN PIN `0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d`, SCORE PIN `8c4b3042ba5abf0134b9d0075170ec55585e41092e60e51f411642b59b59bd1e`; eval.py, evalcore.py, score.py, evalstats.py, rows and fewshot are untouched.
- §10 card, byte-identical. The addendum A1-A2@0.0 still applies.
- The E5-pin line, and E5-pin-resume (= E5-pin byte for byte; line sha `a81b81ff…`).
- All 32 other @0.6 §g PowerShell blocks are byte-identical and in order (`ps-parse-0.7.txt` (4)). E5-S1-keep is kept as run.

## Changed
1. **Header and §0.** @0.7 status; sources add RECHECK-eval@0.6, Trinity's 9:00 PM PT ruling, the E5-S1 copy and @0.6.
2. **§g subsection "E5-pin stopped with exit 3": rewritten.**
   - The @0.6 premise (in-session growth, fresh process clears it) is falsified by the real copy. Peaks are set by zero-padding batches, with own peak = 2.5358e9 + 1410.88·L² (49 points, ≤ 0.49 % residual). Smoke never ran batch 356, and its 381/445 batches are padded. The 6 remaining zero-padding batches are projected at 7.63e9–8.02e9.
   - **E5-pin-resume is withdrawn.** Options R0/A/B/C/D, with the Matt question. Recommendation A: a fresh S at `--batch 4` in `out-S-b4`.
   - New check text: I8–I12, C1–C4, N31.
   - Trinity's 9:00 PM PT ruling (process gate by `Win32_Process` Name/CommandLine; explorer/dwm logged; per-pid CIM; free memory recorded before any launch).
   - New blocks: **E5-gpu-pid, E5-free, E5-S-gate, E5-b4-pin, E5-b4-pin-floor, E6-S4, E5-S4-keep, E7-A, E5-pin-limit**, plus **E5-S2-keep** (replaced: new process line).
   - Box scoring for route A; stop rules for A and B; N33, N35 and N36 folded; new card texts.
3. **Resume line:** adds the @0.7 keep steps (N35).
4. **§j:** @0.7 evidence, the tool sha, and what is untested.
5. **§k:** EV-F3 corrected; EV-T8 added.
6. **§9:** item 11 (the Matt question); item 10's recommendation is withdrawn.
7. **§11:** new 11-00b (N29–N38, the ruling, the falsified premise).
8. **Changelog:** @0.7 entry.

## Stage /workspace/littleblue-eval-v0.7/
- `tools/e5s1_check.py`: replaces @0.6's `ed4208b7`. On the real copy it prints `E5S1 STOP: C4 failed; max projected per-batch peak 8016885034 B at batch 437` (exit 1).
- `tests/e5s1_suite.py`: 27/27. `tests/e5s1_mutants.py`: 27/29 killed on real verdict lines; the 2 equivalent survivors drop I11 sub-checks that are implied by the sha pin.
- `evidence/`: `curve07.py` → `CURVE-0.7.txt`; `batches07.py` → `batches-350-364.txt`; `check-real-0.7.txt`; `suite07.jsonl`; `mutants07.jsonl`; `replay07.py` → `replay-0.7.jsonl`; @0.6's `resume_replay.py` re-run on @0.7 → `resume-replay-on-0.7.jsonl`; `ps_check07.py` → `ps-parse-0.7.txt`; `order-0.6-0.7.diff`.
- `build/`: the generator of the @0.7 text (`build07.py`, `sub07.py`, `sub07.md`, `disp07.md`, the extracted @0.6 blocks).
- `V07-FILES.SHA256`: every file of the stage.
