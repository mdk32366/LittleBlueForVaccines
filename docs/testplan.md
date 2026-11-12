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
