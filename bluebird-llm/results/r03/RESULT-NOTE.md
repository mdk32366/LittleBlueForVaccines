# Bluebird v1.0 eval, r03: result note (2026-11-16)

transformers 5.22.2, pinned by your ruling (b) at 15:26 PT (check PINNED_UNVERIFIED; greedy merged config and processors [] recorded every session)

- T: out-T (exit 0, 3569/3569). S: out-S-b4, route A, batch 4 (exit 0 at 04:26:34 PT, EVAL_DONE qwen25-3b-base-fs 3569 complete c47eda6e3024a497f80b49f106231413f4a5a625d610daa911fa465451439930, peak_alloc 5,032,707,072 B).
- E7-A: 10 files copied; every laptop Get-FileHash equals the box sha256sum; sha256sum -c EVAL.SHA256 OK for out-T and out-S-b4.
- Scoring: score/REPORT.md sha256 eecf22aad959fb80df64c40a87a01abf7bcff31fba92c82c5033a4fc6dfed4e5. Scorer verdict: DEGENERATE (G-F 2079/2090; A-T 0.7459 against a floor LB of 0.8149; P-AR, P-SH, P-PP and P-PP-REF FAIL; MEMORISES not fired). S correct_all 0.0278; T−S answer_value_match +0.6873 [0.6651, 0.7084].
- Owner ruling: PASS by owner override, certified on card t391s1356 at 5:02 AM PT (OWNER-OVERRIDE-T-PASS.md).
- A1 (about 5:05 AM PT, read-only): active scheme 381b4222-f694-41f0-9685-ff5bb260df2e (Balanced); STANDBYIDLE AC 0x00000000; HIBERNATEIDLE AC 0x00000000. PASS.
- E8 (about 5:06 AM PT): restore values 0 and 0. Basis: Emma's E0a report of 11/15 ~3:57 PM PT, "AC sleep and AC hibernate were already both 0". The raw powercfg line is not kept in a box file. Output RESTORED; re-queried AC indices 0x00000000 / 0x00000000. PID 21896 is unchanged: 11/12/2026 2:20:35 PM, C:\Users\mdk32\venvs\littleblue-app\Scripts\python.exe.
- E9 (delete the laptop work dir): NOT RUN. Held pending Matt's call, because the JSON fix and re-score may need it.
