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
- **T-0038 expired marker (confirmed as numbered, Trinity PR 3 review)** (`app/tests/test_t0038_expired.py`): SYNCP000036's MSA (ended 2026-08-31) is flagged expired in the lookup, the Q&A citations and the PDF snapshot (pdftotext), and its PDF stays one page. SYNCP000025's live MSA carries no marker. Rule edges: the as-of date itself isn't expired, and only `expiration_date` counts (AS-0040 (expired rule)). The file count is exactly 21 of 180, and SYNCP000094/095/096 (ending on 2026-09-30) are live. Mutations: expired, expired_le (`<` changed to `<=`).
- gen red-proof: `test_real_out.py::test_real_regeneration_identical` is now on the expected-red list for the nondet and famsplit mutations.
