# testplan

Populated by the first build PR.

## Generator (gen/, PR 1)
Every test must be able to go red; `python gen/tools/redproof.py` proves it (CI runs it).

Ids T-0028..T-0033 are CONFIRMED by Trinity 2026-11-12 (G-18 ruling).

- **T-0014 SYNTHETIC stamp** (`test_qa.py::test_synthetic_stamp`): every doc has `synthetic: true` + the SYNTHETIC header; every leaf `synthetic: true`.
- **T-0017 / T-0023 (generator side) cap** (`test_caps.py`): a 15,361-byte leaf raises `CapError`; exactly 15,360 passes; a 30 KB section yields ≥ 3 `continues`-linked sub-leaves each ≤ 15,360; all emitted leaves ≤ cap. Red-proof: REDPROOF=cap. (T-0023 retrieval part is not built here.)
- **T-0021 (extended) split** (`test_split.py`): no system in both train and test (manifest, docs, qa, leaves); train is family A only, test family B only; a planted test doc in train is flagged. Red-proof: REDPROOF=overlap, REDPROOF=famsplit.
- **T-0022 seam (generator slice)** (`test_seam.py`): toy 3-field spec runs through the unchanged generator via `tests.toy_spec:ToySpec`. Leaves/facts/brief/eval parts of T-0022 are out of scope here. Red-proof: REDPROOF=overlap also turns it red.
- **T-0027 vault contamination** (`test_vault.py`, ontology spec §5): V1 a leaf under any path containing a `VAULT_PATH_MARKERS` entry (the denylist in `gen/bia562gen/vault_guard.py`) is rejected, and the generator refuses such an out-root; V2 a decision-shaped id such as `D-0001` (and AS/T/F, non-grammar ids) is rejected; V3 a body carrying any `PROVENANCE_MARKERS` entry is rejected; V4 a `.md` dropped into a `src/brief/leafstore/` dir rejected. Temp paths only. Red-proof: REDPROOF=vault.
- **T-0028 determinism** (`test_determinism.py`): same seed into two temp dirs gives an identical manifest (sha256 of every file); different seed differs; a tampered file fails `manifest_ok`. `test_real_out.py` checks gen/out's manifest and guards and, when the synthetic CSV is present, regenerates the run and byte-compares with gen/out (it skips the regeneration otherwise). Red-proof: REDPROOF=nondet.
- **T-0029 span verbatim** (`test_spans.py`): every QA `spans` entry and TermSet span is verbatim in its anchor section; the generator raises on `1,250` vs `1,200` and on a cross-system anchor; a reintroduced single `span` field is flagged (G-04). Red-proof: REDPROOF=span.
- **T-0030 no digits in answer** (`test_answer_digits.py`): `answer` has no digit outside `{Sn}` slot tokens; `expires in 2027` is flagged and refused by the generator. Red-proof: REDPROOF=digits.
- **T-0031 no family-B text in train** (`test_family_leak.py`): no B word 4-gram, whole B fragment (≥ 20 chars) or B heading text in any train file; A/B templates share no 4-gram. Red-proof: REDPROOF=leak.
- **T-0032 unanswerable ≥ 15 %** (`test_qa.py`): per split; generator raises below 15 %. Red-proof: REDPROOF=unans.
- **T-0033 section ≤ 1,500 bytes** (`test_caps.py::test_section_over_1500_raises`, `caps_ok`). Red-proof: REDPROOF=cap.

Run: `cd gen && python -m pytest tests` (T-0027 alone: `python -m pytest tests/test_vault.py`); red-proof: `python tools/redproof.py`.

## App (app/, PR 2): test plan

Every guard is red-proofed by `python app/tools/redproof.py` (REDPROOF=<mutation>, test-side monkeypatch only); CI runs it.

- **T-0001 reconcile** (`test_t0001_reconcile.py`): F1 summed over the 180 systems equals the file total to the cent, and doses match. F2, F3 and F4 each sum to F1, on both the synthetic file and the fixture. Returns are 299 rows and −$1,285,193.13. The schema fails closed. The input sha256 equals gen's manifest record. Mutation: reconcile.
- **T-0002 ratio edge** (`test_t0002_ratio.py`): MenACWY = 0 gives "undefined" and below 50 doses gives "insufficient volume", never inf. File counts: 4 undefined, 102 ok, peer ratio 0.661. Mutation: ratio.
- **T-0003 switching** (`test_t0003_switching.py`): the planted Pfizer Pneumococcal 80%→30% at 400 doses per window flags; the noise system doesn't; the synthetic flag rate is below 50% (66/180). Mutation: switch.
- **T-0004 validator** (`test_t0004_validator.py`): "54%", `{F9.x}`, "Prevnar is safer", "offer a 5% discount" and "should charge" are all rejected, plus the T-0013 cases. All 180 rendered briefs are free of clinical and advice language. Mutation: validator.
- **T-0005 fallback** (`test_t0005_fallback.py`): LLM off, unreachable, the 20 s timeout and rejected-twice all give templated points (stub callable, no network). Mutation: fallback.
- **T-0006 one page** (`test_t0006_onepage.py`): 180 renders, each exactly 1 page, cross-checked with pdfinfo. Points truncate with an ellipsis. Mutation: onepage.
- **T-0007 custody: RETIRED** per D-0022 (fake data) and D-0034 (national file public-real). No test.
- **T-0008 benchmark label** (`test_t0008_label.py`): benchmark-derived facts carry "synthetic peers" or "national", and other facts carry "system". The PDF footer shows the live benchmark in both modes. Mutation: label.
- **T-0025 (app slice) national file never training or gen input** (`test_t0025_train_guard.py`): the national path or a copy of it is refused; paths outside `data/synthetic|train/` are refused; records without `synthetic: true` are refused; the gen/ scan is clean; a planted reference is flagged. Mutation: trainguard.
- **T-0035 name, D-0033 (name)** (`test_t0035_name.py`): checks the `set_page_config(page_title=…)` spy, the `st.title`, the first line of the PDF text, and the README. Mutation: name.
- **T-0036 contract Q&A** (`test_t0036_contracts.py`): TermSet answers equal the gen/out spans S1 text and anchor. Citations are from this system only and are verbatim. Unknown questions get D-0027 (refusal string). Mutation: isolation.
- **T-0037 benchmark modes** (`test_t0037_benchmark.py`): the default is synthetic; national reads the national file (ratio 0.54); a missing file falls back with a note; a bad mode or schema fails closed. Mutation: bench.
- **AppTest smoke** (`test_app.py`, `tools/smoke.py`): picker, brief, Q&A tab, download button and benchmark toggle. It also runs a live server health check.
- T-0035, T-0036 and T-0037 are confirmed as numbered (Trinity, PR 3 review). T-0034 is the spec's full-length fit.

## Review follow-ups (PR 3)
- **T-0038 expired marker (confirmed as numbered, Trinity PR 3 review)** (`app/tests/test_t0038_expired.py`): SYNCP000036's MSA (ended 2026-08-31) is flagged expired in the lookup, the Q&A citations and the PDF snapshot (pdftotext), and its PDF stays one page. SYNCP000025's live MSA carries no marker. Rule edges: the as-of date itself isn't expired, and only `expiration_date` counts (AS-0040 (expired rule)). The file count is exactly 21 of 180, and SYNCP000094/095/096 (ending on 2026-09-30) are live. Mutations: expired, expired_le (`<` changed to `<=`). GATE 2: the PDF check now expects `[EXPIRED]` on SYNCP000014 and `[TERM ENDED · auto-renews]` on SYNCP000036.
- **T-0039 auto-renew split (confirmed as numbered, Trinity GATE 2 review)** (`app/tests/test_t0039_autorenew.py`): field-based rule unit cases, including auto_renew True in a different section giving `[EXPIRED]` and clause wording not mattering (AS-0040 (expired rule)); a PRE-REGEN fixture on stub data: 21 expired = 9 auto-renew (007, 009, 018, 036, 062, 088, 099, 140, 150) + 12 none (014, 068, 083, 090, 101, 130, 135, 141, 146, 148, 149, 164), with SYNCP000094/095/096 live. This is not the count pin; GATE 2 pins counts after the regen. The label uses a non-breaking hyphen (U+2011) so the PDF wrapper never splits it; the unit test pins that. Mutations: noautorenew, nosamesection.
- **T-0040 Brief-tab marker (confirmed as numbered, Trinity GATE 2 review)** (`app/tests/test_t0040_brief_contracts.py`): AppTest. SYNCP000036's Brief tab has "Contracts on file" and `[TERM ENDED · auto-renews]`, not `[EXPIRED]`; SYNCP000025's has neither marker; SYNCP000014 shows `[EXPIRED]`. Mutations: briefmarker (hide the Brief-tab marker), noautorenew.
- **T-0041 auto_renew bool schema guard (Trinity GATE 2 review)** (`app/tests/test_t0041_autorenew_schema.py`): guards AS-0041 (schema_v1 keeps auto_renew boolean in term section). Every one of the 180 MSAs has an `auto_renew` TermSet field, it is a bool, and it cites the same section (doc and anchor) as `expiration_date`. Keyed on field names and sections only, so it applies unchanged to schema_v1. Mutation: schema_autorenew (drops `auto_renew` on SYNCP000001's MSA and makes it a string on SYNCP000002's; both tests go red).
- gen red-proof: `test_real_out.py::test_real_regeneration_identical` is now on the expected-red list for the nondet and famsplit mutations.

## v0.2-a client metrics (app/, PR 5): proposed, numbering per the v0.2 spec
- **T-0042 client formulas** (`app/tests/test_t0042_client_formulas.py`, fixture `app/tests/metrics_fixture.py`): hand-computed A1–A4, A10–A11 and R1–R3, R5–R7 at system, five pooled in-state peers and a national-shaped fixture file, with indices and labels. File pins: national R1 0.5483, R2 1.2570, R3 5.6960, R5 0.1928, R6 0.0802, babies 3,514,862.5 / 2,253,839.8 (share 0.641), HepB Ped 6,711,748; SYNCP000025 R1 = 150/240 against peers 952/1144 (n = 7). A1 state = 13,300 ÷ (13,300 + 65,500) and the peer median $13,100 (A1M). Mutations: kr_abcwy (drop MenABCWY from R1), kr_swap (swap numerator and denominator), a1_excl (also below).
- **T-0043 availability** (`app/tests/test_t0043_availability.py`): every client item has a registry entry at every level with a digit-free reason; the NOT AVAILABLE and DERIVED sets are pinned; across all 180 systems and the fixture a NOT AVAILABLE metric has no value fact and renders `not available: <reason>` with no digit, in the cell, the comparison-table rows and the A5–A9 strip; the state column is labelled "synthetic peers (state)". Mutation: invent (the gate lets national A8 through as the number 0).
- **T-0044 ratio guards** (`app/tests/test_t0044_ratio_guards.py`): AS-0044 (ratio rule) unit cases; fixture edges (COVID net −80 undefined, HPV net returns, adult flu 40 insufficient, too few in-state peers, private above total); real file: SYNCP000036 R3 undefined, 11 R3 undefined, 21 R5 undefined, 140/180 with a state comparison, 61 inconsistent babies; no ratio or index fact is inf or negative; A1 state share stays within 0..1 (unit cases including system 100 against peers 50, and all 140 systems). Mutations: ratio_neg (drop the ≤ 0 check), a1_excl (A1 state reverts to the system-excluded denominator, so 100 against 50 gives 2).
- **T-0053 validator widening** (`app/tests/test_t0053_validator_tokens.py`): `{F9.x}`..`{F14.x}` accepted when known; `{F0.x}`, `{F15.x}` and above rejected as malformed. Mutation: tok_wide (regex `F\d+`).
- T-0001..T-0041 are unchanged; T-0025 still passes (the national file stays benchmark-only).
