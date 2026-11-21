# Bluebird T: before (out-T, 128, no constraint) vs after (out-T-jf, 256, json-slot)

**RESULT: score.py on out-T-jf (primary only), recomputed here with the same functions.**

The owner-override T PASS (card t391s1356, OWNER-OVERRIDE-T-PASS.md) stands regardless of these numbers. The after figures are reported, not re-certified, unless Matt cards otherwise. The after run measures the model **plus** the constrained decoder.

| Item | Before | After |
|---|---|---|
| G-F | 2079/2090 FAIL | 2090/2090 PASS |
| G-G | 0 PASS | 0 PASS |
| A-T | 1559/2090 = 0.7459 FAIL | 1559/2090 = 0.7459 FAIL |
| P-CF | -0.0323 PASS | -0.0323 PASS |
| P-AR | 0.3633 FAIL | 0.3633 FAIL |
| P-SH | 0.1267 FAIL | 0.1267 FAIL |
| P-RN | -0.03 PASS | -0.03 PASS |
| P-PP | 0.1367 FAIL | 0.1367 FAIL |
| P-PP-REF | 0.0514 FAIL | 0.0514 FAIL |
| P-RN-LEAK | 0 PASS | 0 PASS |
| verdict (strict) | DEGENERATE | INCONCLUSIVE |
| verdict reasons | format gate failed (11 of 2090 test outputs not strict-valid) | A-T test accuracy floor (strict correct, all test rows); P-AR anchor removal: refusal vs same rows answered; P-SH clause shuffle: drop vs same rows; P-PP paraphrase: drop vs same rows; P-PP-REF paraphrase: extra refusal on answerable vs same rows |
| T correct_all | 0.7459 [0.7273, 0.7641] | 0.7459 [0.7273, 0.7641] |
| T valid_json_schema (test) | 0.9947 | 1.0 |
| T invalid reasons (test) | {'not_json': 7, 'slot_mismatch': 1, 'bad_span_key': 2, 'bad_span_obj': 1} | {} |
| T hit_max (all 3,569 rows) | 8 | 0 |
| S correct_all (out-S-b4, unchanged) | 0.0278 | same rows, not rerun |
| T−S answer_value_match (paired, test) | 0.6873 [0.6651, 0.7084] b/c [1141, 0] p 0.0 | 0.6873 [0.6651, 0.7084] b/c [1141, 0] p 0.0 |
| memorisation test fires | False | False |

No-op check: 3556 of 3569 raw outputs byte-identical to out-T; 13 changed. Strict-invalid before: 13; after: 0.
Changed rows: ['ar:SYN-SYNCP000054-AMD1-Q01:0', 'sh:SYN-SYNCP000116-MSA1-Q21:0', 'test:SYN-SYNCP000004-MSA1-Q12', 'test:SYN-SYNCP000015-MSA1-Q12', 'test:SYN-SYNCP000023-MSA1-Q21', 'test:SYN-SYNCP000040-MSA1-Q28', 'test:SYN-SYNCP000069-MSA1-Q12', 'test:SYN-SYNCP000076-MSA1-Q21', 'test:SYN-SYNCP000082-MSA1-Q12', 'test:SYN-SYNCP000134-MSA1-Q28', 'test:SYN-SYNCP000154-MSA1-Q21', 'test:SYN-SYNCP000168-MSA1-Q12', 'test:SYN-SYNCP000174-MSA1-Q29']
Rows changed that were strict-valid before: []
Rows where the decoder overrode the model (forced > 0): ['sh:SYN-SYNCP000116-MSA1-Q21:0', 'test:SYN-SYNCP000023-MSA1-Q21', 'test:SYN-SYNCP000076-MSA1-Q21', 'test:SYN-SYNCP000154-MSA1-Q21', 'test:SYN-SYNCP000174-MSA1-Q29']
