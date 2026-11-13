# findings

Populated by the first build PR.

## Generator (gen/, PR 1)
Proposed numbering after F-0004.

- **F-0005:** read literally, D-0020 rule 1 ("the `answer` string contains any digit") rejects the §9.6 example itself (`{S1}`, `{S2}`, "Tier 2"). The generator exempts slot tokens only; "Tier 2" in an answer is rejected.
- **F-0006:** the first family-B leak check went vacuous under mutation: B text copied into A templates was exempted as "shared". It was fixed by requiring A/B template 4-gram disjointness (T-0031); nine generic B/A 4-gram overlaps were reworded out of family B.
- **F-0007:** seed 562 on the synthetic CSV gives 180 systems (135 train / 45 test), 455 docs, 4,775 QA rows, about 20.6 % unanswerable. The max section body is 277 bytes and the max leaf is 1,170 bytes, so stub v0 never triggers a cap split.

## App (app/, PR 2): findings (continue after gen's F-0007)
- **F-0008:** the spec's counts reproduce on the synthetic file: 299 returns totalling −$1,285,193.13; MenB:MenACWY 16,302 / 24,674 = 0.661; 4 systems with no MenACWY; 102 systems with a stated ratio; 11 of 28 states with 5 or more systems.
- **F-0009:** the z-test rule flags 66/180 systems (36.7%), against 92% for the old 15-point rule. That is under 50%, but many flags are Influenza, where the two windows sit in different seasons.
- **F-0010:** the national file's MenB:MenACWY is 3,318,943 / 6,136,215 = 0.541, the "0.54" in §0. It has no system or state columns.
- **F-0011:** red-proof run 1: the isolation mutation turned only `test_free_text_isolated` red. The example-question path is also pinned to the qa row's doc_id, so the expectation was narrowed to the isolation test.
- **F-0012:** after netting returns, some manufacturers have negative net dollars for a system (e.g. Moderna, SYNCP000036), and their bars plot below zero.
- **F-0013:** the dev environment runs Python 3.13.5 (CI uses the runner's 3.13); Streamlit 1.67.0 is pinned (`app/requirements.txt`).

## Review rulings (Trinity, PR 3)
- F-0008 accepted.
- F-0009 accepted, with the follow-up AS-0039 (exclude Influenza or use same-season windows).
- F-0010 accepted. Trinity re-derived both ratios: 0.661 is F-0008 (synthetic) and 0.54088 is F-0010 (national); cited together as F-0008 (synthetic) / F-0010 (national).
- F-0011, F-0012 and F-0013 accepted.

## v0.2-a client metrics (app/, PR 5): numbering per the v0.2 spec
Evidence: the box probe output for this PR (counts below), re-checked by T-0042 and T-0044.
- **F-0014:** the national file has no system, state or outlet columns (restates F-0010), so national comparisons are pooled only. It has 45,462 rows, $29.42B and 258.8M doses; 19 specialties against 14 in the synthetic file (national-only: Dialysis, Long Term Care, Non-Retail Walk-In, Retail, Retail Walk-In). 52 national rows (62,407 doses) have a blank age group, so national Ped, Adult and Mixed shares of all doses are 0.1546, 0.1927 and 0.6525 (the spec's Mixed 0.653 is the complement of Ped and Adult). National R1 0.5483, R2 1.2570, R3 5.6960, R5 0.1928, R6 0.0802.
- **F-0015:** synthetic HepB Ped is 0 in all 180 systems; national HepB Ped is 6,711,748 doses (46.9% of national HepB doses).
- **F-0016:** subsidiary ids cross parents (80 of 80; 20,000 of 25,000 rows have a blank subsidiary); 2,395 of 2,400 outlets cross specialties; no outlet crosses parents. A7 is 14–35 per system and A8 13–14.
- **F-0017:** the client's babies heuristic gives private > total in 62 of 180 synthetic systems: 61 show "inconsistent (private exceeds total)" and SYNCP000162 (no Varicella doses, total 0) shows "undefined".
- **F-0021:** state comparison is available for 140 of 180 systems (TX 33, OH 30, CA 22, UT 12, MN 11, PA 9, FL 8, LA 8, ID 7); the other 40 show "too few in-state peers" (for example SYNCP000036, 4 peers). SYNCP000025 (FL, 7 peers): R1 150/240 against pooled peers 952/1144.
