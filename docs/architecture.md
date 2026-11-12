# architecture

Populated by the first build PR.

## Generator (gen/, PR 1)

The generator turns one seed plus the synthetic sales CSV into a small, fully fictional contract corpus with ground-truth Q&A for the retrieval and answering work. Every artefact is fake under D-0022 (fake data); every document carries a SYNTHETIC banner and `synthetic: true`.

### Flow

1. **Systems.** `bia562gen/systems.py` reads one profile per health system from the synthetic CSV (system id, name, state, org type and trailing-12-month doses by vaccine class). Tests use a seeded 12-system fixture instead, so the suite needs no data file.
2. **Plan.** For each system the active spec's `plan(system, rng, family)` decides which documents exist (MSA, exhibits, amendments, notes, proposals) and draws the terms. Randomness comes from one RNG keyed on seed and system, so the same seed always gives the same bytes.
3. **Render.** The spec renders each document as numbered sections, and also emits a TermSet sidecar (`.terms.json`), proposal sidecars and the Q&A records for that system.
4. **Validate.** `generate.validate_bundle` checks the bundle before anything is written and fails closed (see "Guards").
5. **Write.** Documents (`.md`), sidecars, per-clause leaves and one `qa.jsonl` per split go under `out/{train,test}/`. `out/manifest.json` lists the sha256 of every file, and `out/manifest.sha256` hashes the manifest itself.

### The ContractSpec seam

`bia562gen/seam.py` defines the frozen record types and the `ContractSpec` protocol. The generator, leaf writer and checks import only from the seam, never from a spec module. A spec provides `spec_version`, `families`, `doc_types()`, `field_catalog()`, `plan(...)`, `render(...)`, `terms(...)`, `proposals(...)`, `qa(...)` and `template_text(family)`; the last three seam members were added under D-0028 (seam additions).

Stub v0 lives in `bia562gen/specs/schema_stub.py` with its templates in `templates_stub.py`. The owner's schema_v1 drops in as a new `bia562gen/specs/schema_v1.py` plus one `REGISTRY` line in `bia562gen/specs/__init__.py` (or `--spec module:Class`), with `config.json` naming it. No generator code changes. `tests/test_seam.py` proves this with a three-field toy spec that only the test suite knows about.

### Families and split

Two template families exist: A for training and B held out. A family covers both the document text and the question phrasing (D-0024, family scope), and A and B share no four-word phrase (D-0026, no shared 4-word phrase). A seeded shuffle holds out a quarter of the systems; train is family A on train systems only and test is family B on held-out systems only, with no cross cells (D-0025, family split).

### Q&A records

Each answer is a slot template plus verbatim spans, following D-0020 (answer format): the `answer` text carries `{S1}`, `{S2}` slot tokens and no digits, and `spans` maps each slot to text that appears verbatim in its anchor section, written `<doc_id>#<section>`. Slot tokens are exempt from the digit rule but labels like "Tier 2" are not (D-0023, slot tokens exempt from digit rule). At least 15 % of questions per split have no answer in the contracts, and their answer is exactly "not in the contracts" (D-0027, refusal string). The counterparty is always "Synthetic Supplier Co." and products are `PRD-syn-*` ids (D-0029, synthetic supplier and products); no manufacturer or product name from the CSV is ever written.

### Guards (fail closed)

- Document-id grammar and the SYNTHETIC stamp on every document and leaf.
- Section bodies at most 1,500 bytes; every leaf at most 15,360 bytes, with oversize sections split into linked sub-leaves.
- TermSet field names must exist in the spec's field catalog.
- Every span verbatim in its anchor section, and anchors stay inside the same system.
- No digits in answer text; at least 15 % unanswerable per split.
- No system in both splits; no family-B text in train.
- Vault contamination (T-0027): `bia562gen/vault_guard.py` rejects leaves whose path matches its denylist, leaf ids that match no project grammar, bodies carrying provenance markers, and non-`.py` files in a vendored code directory.

### Layout

```
gen/
  bia562gen/        generator package (seam, generate, leaves, caps, checks, vault_guard, specs/)
  tests/            pytest suite (T-0014, T-0017, T-0021, T-0022, T-0027 to T-0033)
  tools/            gen_contracts.py (CLI), redproof.py (proves each guard can go red)
  out/              accepted seed-562 run; tests re-check it
  config.json       active spec name
  requirements.txt  pinned test dependencies (the package itself is standard library only)
```

Regenerate with `cd gen && python tools/gen_contracts.py --seed 562 --out out/`. Without `--systems-csv` the tool reads `data/BIA_562_Synthetic_Sales_Data.csv` (moved there in PR 2; `test_real_out.py` reads the same path).

## App (app/, PR 2)

Little Blue for Vaccine Sales, D-0033 (name). Proposed repo slug: `little-blue-vaccine-sales`.

```
data/BIA_562_Synthetic_Sales_Data.csv --load.py (schema check, fail closed)--> clean.py (returns netted, null class -> Unclassified)
   --> facts.py F1..F8 (+ switching.py z-test, benchmark.py synthetic|national) --> FactSheet (fact_id, value, unit, period, n, source_label)
   --> templates.py (fact tokens only) --> validator.py --> narrative.py (LLM off; templated) --> render tokens
   --> charts.py (matplotlib Agg) --> render.py: ONE letter figure -> one-page PDF
gen/out (read-only) --> contracts.py: TermSet lookup with cited spans <doc_id>#<section>, filtered to one system
app.py (Streamlit): benchmark radio, system picker, Brief tab (tiles, 4 charts, points, flags, Download PDF), Contract Q&A tab
cli.py: batch PDFs (--system/--all, --benchmark, --factsheet)
```

- **Paths:** `brief/config.py`. `DATA_PATH`, `NATIONAL_PATH`, `GEN_OUT` and `BENCHMARK` are env-overridable. Defaults are `<repo>/data/<file>` (legacy fallback: `<repo>/<file>`).
- **Benchmark:** `synthetic` is the default and the fallback. `national` reads 'BIA 562 National System Data.csv', D-0034 (national file public-real). That file has no system or state columns, so it supplies only national dollars and the MenB:MenACWY ratio. Rank and in-state peers stay on synthetic peers and are labelled so. A missing national file falls back to synthetic, with a note in the sidebar and a "[fallback]" footer.
- **LLM:** off. `narrative.compose(fs, llm=None)` takes an in-process callable only so T-0005 can prove the fallback. There is no network client.
- **Guardrails:** `validator.py` rejects digits outside `{Fn.id}` tokens, unknown tokens, clinical-claim words, "should charge", and an advisory word plus a commercial term in one sentence. It applies D-0009 (denylist), and D-0023 (slot tokens exempt from digit rule) is applied to fact tokens. Real manufacturer and product names may appear, D-0035 (real names, fake grounding). Contracts and Q&A stay synthetic (gen/out).
- **T-0025 app slice:** `train_guard.py` holds the refusal the future training path must call, plus a scan of gen/ for any consumption of the national file.
