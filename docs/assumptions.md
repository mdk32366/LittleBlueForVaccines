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

## App (app/, PR 2): assumptions (continue after gen's AS-0027)
- **AS-0028:** F3 "facility type" is `BAC_CHNL_SPEC_DESC`.
- **AS-0029:** F1.rank ranks by net dollars, with 1 as the largest (ties take the min rank). F1.bench_share is the system's dollars over the benchmark's dollars.
- **AS-0030:** system-only facts carry `source_label: "system"`. The spec names only benchmark labels.
- **AS-0031:** in-state peers are the other systems with the same `BAC_CORP_PAR_ST_CD`, excluding the system itself. At least 5 are needed; their ratio pools their doses.
- **AS-0032:** F6 uses all 24 months. Index = ratio ÷ benchmark ratio × 100.
- **AS-0033:** F5 uses net doses. A manufacturer-window below zero is floored at 0; a pooled share of 0 or 1 gives no z. Doses are treated as trials, as §0 item 3 implies.
- **AS-0034:** the national benchmark supplies only total dollars and the MenB:MenACWY ratio (it has no system or state columns), D-0034 (national file public-real).
- **AS-0035 (DEFERRED to the LLM wire-in PR, 11/18–20, after GATE 3):** the LLM path is an injectable callable used only by T-0005. There is no client code and no keys.
- **AS-0036 (DEFERRED to the LLM wire-in PR, 11/18–20, after GATE 3):** Q&A with the LLM off is TermSet lookup. Cross-doc and proposal questions answer D-0027 (refusal string), with the note "needs retrieval".
- **AS-0037:** data paths default to `<repo>/data/<file>`, falling back to `<repo>/<file>`. They are env-overridable.
- **AS-0038 (DEFERRED to the wire-in PR, 11/18–20, after GATE 3, for C1–C6 and the two-column layout):** the PDF's right column shows a cited contract snapshot from the TermSet. It is not C1–C6.

## Review rulings (Trinity, PR 3)
- AS-0028 to AS-0038 are accepted as built. AS-0035 and AS-0036 (LLM wire-in) and AS-0038 (C1–C6 and the two-column layout) are deferred to the 11/18–20 wire-in PR after GATE 3.
- **AS-0039 (OPEN FOLLOW-UP, see F-0009):** F5 switching must either exclude Influenza or compare same-season windows. Today the two windows (202410–202503 and 202604–202609) sit in different flu seasons, so many of the 66/180 flags are Influenza season effects rather than switching. Documented only; not implemented in PR 3.
- **AS-0040 (expired rule; confirmed as numbered, Trinity PR 3 review):** a contract whose end date (`expiration_date`) is before the as-of date, 2026-09-30 (the last day of the data's last month, 202609), is marked `[EXPIRED]` in the PDF "Contracts on file" snapshot, the Q&A tab citations and the TermSet table. 21 of 180 MSAs are expired on this rule, e.g. SYNCP000036 (ended 2026-08-31). SYNCP000094, SYNCP000095 and SYNCP000096 end exactly on 2026-09-30 and are live (the rule is strictly before). An amendment does not extend the end date in stub v0.
- **AS-0040 amendment (auto-renew, field-based; Trinity GATE 2 ruling):** an expired MSA shows `[TERM ENDED · auto-renews]` instead of `[EXPIRED]` when its TermSet `auto_renew` field is `True` AND that field cites the same section (same doc and anchor) as `expiration_date`, with its span verbatim there. Otherwise an expired MSA keeps `[EXPIRED]`. No phrase matching on clause text. It applies to the PDF snapshot, the Q&A citations, the TermSet status column (expander stays collapsed) and the Brief tab "Contracts on file" section. On stub v0 data the 21 expired MSAs split 9 auto-renew / 12 not (PRE-REGEN figure; the count is pinned only after the GATE 2 regeneration). This replaces the earlier open note on auto-renewing MSAs.
- **AS-0041 (schema_v1 keeps auto_renew boolean in term section; owner Trinity):** schema_v1 must keep `auto_renew` on every MSA as a boolean TermSet field citing the same section as `expiration_date`. The marker in AS-0040 (expired rule) depends on it. Dropping or moving it is a spec change routed through Trinity; no silent remap.

## v0.2-a client metrics (app/, PR 5): proposed, numbering per the v0.2 spec
- **AS-0042 (client field mapping):** Specialty = `BAC_CHNL_SPEC_DESC`; Corporate_Parent_Type = `BAC_CORP_PAR_ORG_TYP_DESC`; Corporate_Parent_State = `BAC_CORP_PAR_ST_CD`; DDD_Number = `DDD_OTLT_NBR`; Subsidiary = `BAC_OWN_SUBS_IMS_ORG_ID`; Age_Group = `VAC_AGE_GRP_NM` (a product label, not patient age); OBGYN = "Women's Health". The R7 season is the Oct–Mar month window of the latest full season, 202510–202603 (spec §3.2; the season rule is logged as AS-0046 (season windows) with PR 6). Blank class, subclass, manufacturer and specialty values in the national file read as "Unclassified", the same rule `clean.py` applies to the synthetic file.
- **AS-0043 (comparators):** national = the whole national file pooled; state = synthetic in-state peers, AS-0031 (in-state peers), their components summed. The national file has no state. A1's state figure is the system's dollars as a share of the pooled peers' dollars (peers exclude the system, so it is not a share of the state total); its national figure is the system's share of national dollars. Medians (A7–A9 state) are over the peers' per-system counts, a peer without a row in a specialty counting as zero.
- **AS-0044 (ratio rule):** a ratio is shown when the denominator is at least 50 net doses and the numerator is at least 0. Denominator ≤ 0 gives "undefined", under 50 gives "insufficient volume", a negative numerator gives "net returns"; never inf, never negative. Index = system ÷ comparator × 100, only when both are values and the comparator is above zero. Shares (A1, A11) give "undefined" on a total ≤ 0 and "net returns" on a negative part. A10 (babies, the client's heuristic) gives "undefined" when the total estimate is ≤ 0 and "inconsistent (private exceeds total)" for public and private share when private exceeds total; total and private are still shown as estimates. R7 applies the ratio rule to each of its three parts over their sum.
