# Bluebird v1.0 eval report (@0.2)

Verdict (T, strict): **INCONCLUSIVE**

- A-T test accuracy floor (strict correct, all test rows)
- P-AR anchor removal: refusal vs same rows answered
- P-SH clause shuffle: drop vs same rows
- P-PP paraphrase: drop vs same rows
- P-PP-REF paraphrase: extra refusal on answerable vs same rows

## Conditions of the false-alarm figure

- The <= 5% false-alarm rate (an honest reader that reads the prompt is called something other than READS) assumes (1) its true strict accuracy on the 2,090 test rows is at least the stated 0.85, and (2) probe rows are as hard as their source rows (probe parity).
- Our simulation (sim/SIM-RESULTS.md, 4,000 reps): at 0.85, 3.45% (Wilson 95% 2.9-4.1%); at 0.83, 58.7% (the floor bar fails).
- Independent simulation (Kaylee, review evidence 40-ksim.md, 4,000 reps) at 0.85: independent rows 3.20% [2.70, 3.79]; probes correlated with their source rows (rho 0.7) 4.28% [3.69, 4.95]; heterogeneous by question type 3.87% [3.32, 4.52]; wrong answers = the training-mode value 2.95% [2.47, 3.52] (MEMORISES 0/4000); at 0.83, 57.95%.
- Probe parity broken (Kaylee 40-ksim.md): sh/pp probes 2 points harder than their sources -> 8.5% false alarms (8.53%); sh/pp/rn 4 points harder -> 35.9% (35.85%), INCONCLUSIVE in every such rep. A probe-bar FAIL is therefore evidence only if probe parity is credible.
- An INCONCLUSIVE whose only failing bar is A-T means: accuracy below the stated floor; no memorisation evidence. It is not a finding that the model ignores the prompt.

## Scorer provenance

- score manifest sha256 (SCORE PIN): 8c4b3042ba5abf0134b9d0075170ec55585e41092e60e51f411642b59b59bd1e
- run manifest sha256 (RUN PIN, as recorded by every run): c5db63e4a0194582245692c73ef7333297bf27dc46dd298ce55f98fa58903871
- scorer files: score.py a4d7a3746e17549ba5e21965df3dcad916758faecaf2425dfaebdda99d424045, evalcore.py 2d1d2f9bc0716938278a6d9dee9d19830ec673721c68d0753390127c3104ba75, evalstats.py 9464f55d3d993557a5d48cc30e180feb8a24ba65742ecc494f5dc423787bc537
- scorer drift: none

Promotable (READS and G-G pass): False

| Bar | Source | Value | Threshold | Status | n / b / c / p |
|---|---|---|---|---|---|
| G-F format: strict schema-valid JSON on test | carried §f / brief (hard gate) | 2090/2090 | = all test rows | PASS |  /  /  /  |
| G-G guardrail: denylist hits on test | carried §f (must be 0); promotion gate, not part of the verdict | 0 | = 0 | PASS |  /  /  /  |
| A-T test accuracy floor (strict correct, all test rows) | proposed (@0.1, ruling 1) | 1559/2090 = 0.7459 | Wilson95 LB >= 0.8149 (count >= 1738); stated true accuracy 0.85, miss rate at stated <= 0.01 | FAIL |  /  /  /  |
| P-CF counterfactual: new value vs same rows original | proposed (@0.1: exact one-sided McNemar on discordant pairs) | -0.0323 | FAIL iff p < 0.0067 AND drop > 0.05 | PASS | 279 / 3 / 12 / 0.996 |
| P-AR anchor removal: refusal vs same rows answered | proposed (@0.1: exact one-sided McNemar on discordant pairs) | 0.3633 | FAIL iff p < 0.0067 AND drop > 0.05 | FAIL | 300 / 159 / 50 / 9.89e-15 |
| P-SH clause shuffle: drop vs same rows | proposed (@0.1: exact one-sided McNemar on discordant pairs) | 0.1267 | FAIL iff p < 0.0067 AND drop > 0.03 | FAIL | 300 / 58 / 20 / 9.76e-06 |
| P-RN supplier+brand rename: drop vs same rows | proposed (@0.1: exact one-sided McNemar on discordant pairs) | -0.03 | FAIL iff p < 0.0067 AND drop > 0.03 | PASS | 300 / 4 / 13 / 0.994 |
| P-PP paraphrase: drop vs same rows | proposed (@0.1: exact one-sided McNemar on discordant pairs) | 0.1367 | FAIL iff p < 0.0067 AND drop > 0.05 | FAIL | 300 / 59 / 18 / 1.53e-06 |
| P-PP-REF paraphrase: extra refusal on answerable vs same rows | proposed (@0.1: exact one-sided McNemar on discordant pairs) | 0.0514 | FAIL iff p < 0.0067 AND drop > 0.05 | FAIL | 292 / 20 / 5 / 0.00204 |
| P-RN-LEAK real supplier/brand name in output after rename | proposed (case-insensitive, word-bounded) | 0 | = 0 | PASS |  /  /  /  |

Memorisation test (MEMORISES iff it fires): {"n": 577, "b_old_not_placebo": 0, "c_placebo_not_old": 0, "effect": 0.0, "p_value": 1.0, "fires": false, "rule": "old value (cf: the replaced original; ar: the removed value) returned more often than a placebo value absent from the prompt: exact one-sided McNemar p < 0.01 AND effect >= 0.02"}

## T (strict)

| Metric | Value | 95% CI |
|---|---|---|
| valid_json_schema | 1.0 |  |
| correct_all | 0.7459 | [0.7273, 0.7641] |
| answer_value_match | 0.6873 | [0.6651, 0.709] |
| answer_exact_match_template_dependent | 0.0 |  |
| rendered_match_template_dependent | 0.0 |  |
| span_grounded | 0.9367 |  |
| span_ok_anchor_resolves_and_contains_text | 0.303 |  |
| anchor_exact | 0.3048 |  |
| refusal_precision | 0.8856 |  |
| refusal_recall | 0.9721 |  |
| refusal_f1 | 0.9268 | [0.9089, 0.9446] |

Exact match and rendered match depend on the answer template; family B never shares a template with training, so they are ~0 by construction and not comparable across families (review I5).

| Probe | n | correct | drop vs src | correct given src correct | extra |
|---|---|---|---|---|---|
| cf | 279 | 0.7921 | -0.0323 | 0.9858 | {"new_value": 0.7921, "old_value": 0.0, "placebo_value": 0.0, "old_value_given_src_correct": 0.0, "anchor_exact": 0.3477} |
| ar | 300 | 0.3033 | 0.3633 | 0.205 | {"placebo_value": 0.0, "old_value_given_src_correct": 0.0, "refusal": 0.3033, "old_value_hallucinated": 0.0, "anchor_exact": 0.0} |
| sh | 300 | 0.58 | 0.1267 | 0.7264 | {"anchor_exact": 0.1233} |
| rn | 300 | 0.7533 | -0.03 | 0.9816 | {"name_leak": 0, "anchor_exact": 0.25} |
| pp | 300 | 0.5267 | 0.1367 | 0.7035 | {"over_refusal_on_answerable": 0.1027, "anchor_exact": 0.3267} |
