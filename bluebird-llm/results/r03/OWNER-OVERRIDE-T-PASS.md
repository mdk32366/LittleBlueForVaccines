# Owner override: Bluebird T judged PASS (2026-11-16)

**Status: CERTIFIED.** Matt Kelly certified it on card t391s1356 at 5:02 AM PT on 2026-11-16 ("Certified: Bluebird T is a PASS by owner override."). It was first stated in chat at 4:59 AM (t389u) and 5:01 AM (t390u).

## Scorer verdict (unchanged, on the record)
score/REPORT.md (sha256 eecf22aad959fb80df64c40a87a01abf7bcff31fba92c82c5033a4fc6dfed4e5): T verdict **DEGENERATE**.
- G-F format gate FAIL: 2079/2090 strict-valid (11 not).
- A-T accuracy floor FAIL: 1559/2090 = 0.7459; bar Wilson95 LB >= 0.8149 (stated true accuracy 0.85).
- Probe bars FAIL: P-AR, P-SH, P-PP, P-PP-REF. PASS: P-CF, P-RN, P-RN-LEAK, G-G.
- Memorisation test did not fire (n 577, effect 0.0, p 1.0).

## Owner ruling (certified)
Matt Kelly judges T a **PASS** by owner override.

**Why (Matt's words, 5:01 AM PT 11/16):** "It crushed what a normal LLM would be expected to meet."
Also (4:59 AM PT, t389u): "Then we set the bar incorrectly. I'm judging it a pass. The JSON malformation is fixable."

**Supporting figures (score/REPORT.md):**
- Baseline S (the same base model, few-shot, with no fine-tune): correct_all 0.0278, valid JSON 0.255.
- T: correct_all 0.7459 [0.7273, 0.7641], valid JSON 0.9947, refusal F1 0.9268.
- Paired T−S answer_value_match: +0.6873 [0.6651, 0.7084], discordant 1141 / 0, McNemar p ~ 0.
- No memorisation evidence.

## Notes for the reader
- The 0.85 accuracy floor was set before any real results came in; the owner judges it was set too high.
- The probe-bar failures count as evidence only if probe parity holds (REPORT.md, conditions section).
- Follow-up: fix the 11 malformed JSON outputs (format), then re-score.
