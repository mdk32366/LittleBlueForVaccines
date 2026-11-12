# findings

Populated by the first build PR.

## Generator (gen/, PR 1)
Proposed numbering after F-0004.

- **F-0005:** read literally, D-0020 rule 1 ("the `answer` string contains any digit") rejects the §9.6 example itself (`{S1}`, `{S2}`, "Tier 2"). The generator exempts slot tokens only; "Tier 2" in an answer is rejected.
- **F-0006:** the first family-B leak check went vacuous under mutation: B text copied into A templates was exempted as "shared". It was fixed by requiring A/B template 4-gram disjointness (T-0031); nine generic B/A 4-gram overlaps were reworded out of family B.
- **F-0007:** seed 562 on the synthetic CSV gives 180 systems (135 train / 45 test), 455 docs, 4,775 QA rows, about 20.6 % unanswerable. The max section body is 277 bytes and the max leaf is 1,170 bytes, so stub v0 never triggers a cap split.
