# assumptions

Populated by the first build PR.

## Generator (gen/, PR 1)
Proposed numbering after AS-0013; Trinity to confirm.

- **AS-0014 (see D-0029, synthetic supplier and products):** the counterparty is "Synthetic Supplier Co." The brief's rule against real manufacturer/vendor names overrides AS-0005's manufacturer-side wording; no manufacturer name from the CSV is written.
- **AS-0015 (see D-0029, synthetic supplier and products):** covered products are fictional ids `PRD-syn-<class-slug>`, not CSV product names (brand names avoided).
- **AS-0016 (see D-0025, family split; G-07 ruling):** split holds out 25 % of systems (seeded shuffle): 135 train / 45 test of 180. Train = family A only, test = family B only; no cross cells (train-systems×B, test-systems×A) are emitted.
- **AS-0017:** TermSet keys for multi-cardinality fields are `<field>-<n>` (matches the Term id suffix); bool and id values use TermSet type `enum` (TermSet types lack bool/id).
- **AS-0018 (see D-0023, slot tokens exempt from digit rule):** D-0020 rule 1 is applied to `answer` with slot tokens `{S1}`, `{S2}` removed.
- **AS-0019 (RESOLVED, D-0020 (answer format) + G-04 ruling, Trinity 2026-11-12):** the canonical answer form is the §9.6 `spans` dict with anchors `<doc_id>#<section>`. The duplicate §7.7 single `span` field is dropped from output, checks and tests. `source_anchor` stays: it equals `spans.S1.anchor` and is the §7.7 retrieval-eval key (hit@k); it is null for unanswerable rows. The Clause id is `CL-<doc_id>-<anchor>`. Records also carry `value`, `field_name`, `question_type`, `synthetic` and `spec_version`.
- **AS-0020 (see G-06 ruling):** proposals render as a Doc with `doc_type: "PROPOSAL"` (not in doc_type vocab); their anchors are doc sections, not Clause leaves.
- **AS-0021:** a section's `clause_type` comes from the catalog clause_type of its terms; a section with no terms is `other`.
- **AS-0022:** Contract leaf `title` is derived and `effective_date` comes from the TermSet (AMD reuses the `effective_date` field).
- **AS-0023 (see D-0028, seam additions):** `ContractSpec` gains `plan(system, rng, family)`, `families` and `template_text(family)`; §7.2 names no constructor for `doc_spec`.
- **AS-0024:** commitments are ±30 % of trailing-12-month (202510–202609) class doses from the synthetic CSV; tiers sit at 0.6/0.9/1.2× primary-class doses.
- **AS-0025 (see G-13 ruling):** one `qa.jsonl` per split, not one per document.
- **AS-0026:** the 1,500-byte section limit is a hard raise in the generator (spec says "targets").
- **AS-0027:** the cap is ≤ 15,360 bytes (L001), not strictly under.
