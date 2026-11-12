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
