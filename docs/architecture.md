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
- **Expired marker:** `contracts.is_expired` flags a contract end date before `config.AS_OF_DATE` (2026-09-30); the PDF snapshot, Q&A citations and TermSet table show `[EXPIRED]` (AS-0040 (expired rule), T-0038 (expired marker)). `contracts.field_marker` swaps in `[TERM ENDED · auto-renews]` when the MSA's `auto_renew` field is True and cites the same section as `expiration_date` (field-based, no phrase matching; AS-0041 (schema_v1 keeps auto_renew boolean in term section)). The Brief tab lists the same "Contracts on file" lines via `report.brief_contract_lines` (T-0039, T-0040). The label's hyphen is U+2011 (non-breaking; DejaVu Sans renders it) so the PDF wrapper keeps it whole. T-0041 guards the `auto_renew` schema contract.
- **T-0025 app slice:** `train_guard.py` holds the refusal the future training path must call, plus a scan of gen/ for any consumption of the national file.

## v0.2-a client metrics (app/, PR 5)

The client's key system attributes (A1–A11) and important ratios (R1–R3, R5–R7; R4 held) at three levels: the system, its pooled synthetic in-state peers and the pooled national file. The public spec copy is `docs/spec-v0.2.md` (§3 is the data contract).

```
data/BIA_562_Synthetic_Sales_Data.csv --load + clean--> client_metrics.extend(fsets, df, nat)
data/BIA 562 National System Data.csv --benchmark.national_profile()--^   (benchmark only, D-0034 (national file public-real))
   benchmark.pooled(rows): one additive aggregation used for the system, the pooled peers and the national file
   availability.gate(key, compute): the only route to a computation; NOT AVAILABLE returns NotAvailable, never a number
   --> FactSheet gains F9 (A1–A4, highest-dollar shares), F10 (A5–A9), F11 (A10), F12 (A11), F13 (R1–R7)
   --> client_metrics.table_rows(fs) / attribute_strip(fs): display strings for the comparison table and A5–A9 strip
```

- **Levels and ids.** A value fact per level: system `<fid>`, state `<fid>_state`, national `<fid>_nat`; each has a status label `<fid>[_level]_st` (ok, undefined, insufficient volume, net returns, too few in-state peers, no national file, not available, inconsistent (private exceeds total)). Indices are `<fid>_idx_state` and `<fid>_idx_nat` (system ÷ comparator × 100). A1 state (`F9.share_state`) is a fraction 0..1 of the state total including the system, with the in-state peer median dollars (`F9.peer_median_dollars_state`, registry item A1M) beside it. Series facts (A2, A3, A4, A9, manufacturer shares) carry one row per item with the three levels and both indices.
- **Comparators.** State = the other systems with the same `BAC_CORP_PAR_ST_CD`, at least five (AS-0031 (in-state peers)), their components summed. National = the whole national file pooled (AS-0043 (comparators)). The national file has no system, state or outlet columns (F-0014), so A6–A9 national, a national system grouping and a real system universe are NOT AVAILABLE.
- **Registry.** `brief/availability.py` holds `REGISTRY["<item>.<level>"] = Entry(status, reason, columns)` for every client item at every level, with status OK, DERIVED (the reason is the caveat) or NOT AVAILABLE. Reasons are digit-free. `client_metrics.cell()` renders a NOT AVAILABLE metric as `not available: <reason>`.
- **Ratio rule.** `client_metrics.ratio_rule` applies AS-0044 (ratio rule). F6 (MenB:MenACWY, T-0002) and its PDF tile are unchanged; R1 is the v0.2 figure.
- **Unchanged.** F1–F8 (`facts.py`), the PDF (one page, T-0006), the Brief and Q&A tabs, gen/ and gen/out. The comparison table and strip are rendered by the next PR (v0.2-b); this PR adds the data layer and its display strings only.
- **Validator.** Fact tokens widen from F1–F8 to F1–F14 (`validator.TOKEN`); F0 and F15+ stay malformed (T-0053).

## v0.2-b brief and talking points (app/, PR 6-lite)

- **Tabs** come from `config.TABS`: Brief, Talking points, Contract Q&A (T-0052, partial).
- **Brief tab** adds "System vs state peers vs national" (`client_metrics.table_rows`) and the A5–A9 strip (`attribute_strip`); a NOT AVAILABLE cell reads "not available: <reason>". The app computes `client_metrics.compute_all` with the national file whenever it is present, so the national column always shows (Q-M3 closed).
- **Talking points tab** (`brief/talking.py`): templates plus fact tokens only, no LLM. `build(fs)` gives three fixed points, up to three must-cover points (AS-0045 (must-cover selection)) and one question. Each is checked by the validator and by `allowed()` (no status labels, no NOT AVAILABLE items, only status-ok facts) and shown with a "covered" checkbox.
- **Payload seam.** `talking.payload_points(system_id, fsets=None)` returns `PayloadPoint(key, text, metric_value, bench_state, bench_national)` items. This is a local frozen dataclass whose field names and order map 1:1 to the payload dataclass in `brief/payload.py` (the visit-record payload, a separate PR); talking.py does not import payload.py. Values are numbers or None, never a number for a NOT AVAILABLE or not-ok fact. T-0045 `test_payload_fields` pins the fields (mutation payload_fields).
- **Client email 2026-11-13 items:** R4 (the client's interim definition), R6 (full RSV Vaccine subclass), the two OBGYN Tdap ratios (F13.r7_flu_tdap, F13.r7_rsv_tdap) and the babies ratio; registry updated (AS-0053..AS-0056).
- **Unchanged:** the PDF, the narrative points, F14 (PR 6b), gen/ and gen/out.
## v0.2-d visit store + FAKE Salesforce payload record (app/, PR 8)

```
Visit record tab (brief/visit_tab.py): rep, visit date, company (= the health system picker), start, duration, typed notes
   talking points: talking.payload_points(system_id, fsets) (v0.2-b; same points as the Talking points tab),
                   falling back to payload.points_from_client_rows(client_metrics.table_rows) if the provider fails
   payload.mentioned_hint(point, notes) pre-fills "Addressed"; the rep confirms every outcome
   --> visits.save_visit(): payload.build_payload() -> payload.validate() (schemas/visit_payload.schema.json)
       -> SQLite visits (upsert by key) + sf_payloads (append version n+1, sha256)      [nothing is sent]
   --> visits.lookup(rep, date, system_id): exact key only -> latest version + payload JSON + Download visit (.json)
   --> Load visit file: visits.parse_visit_file() (file schema + payload schema + payload rebuilt from the visit fields)
```

- **Modules.** `brief/payload.py` (the pure builder, the TalkingPoint seam, the keyword hint and schema validation), `brief/visits.py` (stdlib sqlite3 store, parameterised SQL, `backup` CLI), `brief/visit_tab.py` (Streamlit tab), and `brief/schemas/visit_payload.schema.json` with `visit_file.schema.json`. app.py gains one tab, "Visit record", in one block.
- **Payload.** sObject Tree bodies per root type: Event plus nested Talking_Point_Outcome__c children, and Task per follow-up (AS-0049 (sf payload field names)). It is marked FAKE-SYNTHETIC and stored as a record, never sent (AS-0057 (sf payload is a database record, not a send), D-0037 (no real Salesforce)).
- **Store.** `visits` holds one row per key (AS-0048 (visit key, exact lookup)). `sf_payloads` holds id, visit_key, version, created_at, schema_version, payload_json and sha256; it is append-only, with triggers. The path is `LB_VISITS_DB` (AS-0050 (visits DB path)). The store is open with no passcode, so there is no enumeration (AS-0058 (open visit store, no passcode)).
- **Seams.** app.py passes `talking.payload_points` (bound to the app's FactSheets) as `points_provider`. It returns frozen PayloadPoint items (key, text, metric_value, bench_state, bench_national), and payload.py duck-types them without importing talking.py. "Visit record" is the last entry of `config.TABS`. v0.2-c pre-fills `st.session_state["vr_notes"]` with the edited transcript before the notes widget renders.
- **Unchanged.** The PDF (T-0006), the Brief and Q&A tabs, F1–F14, gen/ and gen/out. Visit records are never training input (T-0051).

## v0.2-c voice notes (app/, PR 7)
```
Visit record tab: st.audio_input("Record visit notes", sample_rate=16000)    [hidden when no transcriber]
   --> bytes in memory --> stt.decode_wav() (stdlib wave + numpy, float32, 16 kHz) --> transcriber.transcribe(array)
   --> st.session_state["vr_notes"] (appended to typed text) --> the rep edits --> Save visit (as typed notes)
```

- **Module.** `brief/stt.py`: `get_transcriber()` returns FasterWhisper, Stub or None with a reason, and `transcribe_bytes()` falls back to typed notes on any error. visit_tab.py caches the transcriber per STT config with `st.cache_resource` and shows a spinner while it runs (AS-0047 (STT engine and model)).
- **Config.** `LB_STT` (faster-whisper, stub, off), `LB_STT_MODEL` (small.en default, base.en swap), `LB_STT_MODEL_DIR`. The optional packages are in `app/requirements-voice.txt`; without them the app runs typed-only.
- **Privacy.** The recording is never written anywhere (AS-0059 (raw audio is not kept)); the payload and store are unchanged.
- **Unchanged.** The payload schema, the visit store, the other tabs and the PDF.

