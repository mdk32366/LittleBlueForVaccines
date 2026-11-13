# Little Blue for Vaccine Sales: v0.2 spec (architect draft @0.0, 2026-11-13)

Public copy: the deploy section and server internals are omitted. Person names are replaced by roles ("the client" is the source of the asks; "the owner" is the project owner).

Repo: mdk32366/LittleBlueForVaccines (PUBLIC). Base: main `a11b2f3e` plus unmerged `gate2-regen` head `9acaca82` (AS-0041, T-0039..T-0041). Numbering below continues from that branch. Highest numbers today: **D-0035 (real names, fake grounding), AS-0041, T-0041, F-0013** (docs/decisions.md:34, gate2-regen docs/assumptions.md, docs/testplan.md, docs/findings.md:18).
Scope source: the owner's GO for v0.2, 11:42 AM PT 11/13, logged as D-0036 (v0.2 scope), accepted (docs/decisions.md). Only the owner's own words count as approval.
Evidence for this spec: a read-only metrics probe script and its output, an STT bench script and its notes, and the fixture WAV, kept with the build evidence (not in the repository). The probe's national values are pinned by T-0042.

## 0. Goal, does / doesn't

**Goal.** A rep picks a health system and gets (1) a pre-visit brief comparing that system with the national file and with its in-state peers, (2) the talking points they must cover, built only from computed numbers, (3) visit notes captured by voice (typed fallback), and (4) a Salesforce-shaped visit payload "sent" to a local SQLite store that can be looked up later by rep + visit date + company.

**Does:**
- The client's 11/13 attributes and ratios, each with an availability status, and the computable ones shown three ways: system / in-state peers / national.
- Purchasing change within a class, at both manufacturer and brand (PROD_NM) level, using same-season windows (closes AS-0039).
- Offline speech-to-text: faster-whisper on CPU, with a typed fallback.
- A Task-shaped JSON payload, a JSON Schema check, a SQLite upsert, a lookup view and a simulated send log.

**Doesn't:**
- Make any network call to Salesforce. There's no Salesforce library and no credentials.
- Give pricing advice, or make efficacy or safety claims (D-0009 (denylist) and D-0035 (real names, fake grounding) guardrails unchanged).
- Invent any field: a metric the data can't support shows NOT AVAILABLE with a reason.
- Use the national file as training or gen input (D-0034 (national file public-real), T-0025). Visit notes and the visits DB never become training or gen input either (new T-0051).
- Change gen/, gen/out or the QLoRA data. v0.2 is app-only and does not touch GATE 2.
- Change the PDF (still one page, T-0006). v0.2 additions are UI and payload only.
- Let private vault notes enter the project (T-0027 unchanged).

## 1. Data facts that drive the design (verified 2026-11-13 on main a11b2f3e)

| File | Rows | Columns |
|---|---|---|
| `data/BIA 562 National System Data.csv` (real/public, D-0034 (national file public-real)) | 45,462 | 12: `MTH_ID, PROD_NM, MFR_NM, VAC_PROD_CLAS_NM, VAC_PROD_SUBCLAS_NM, VAC_AGE_GRP_NM, VAC_FRZ_IND, SEASON_DESC, BAC_CHNL_SPEC_DESC, BAC_CORP_PAR_ORG_TYP_DESC, DOSES, DOLLARS` (also app/brief/benchmark.py:19-20) |
| `data/BIA_562_Synthetic_Sales_Data.csv` (synthetic, D-0022 (fake data); the client: "created by co-pilot") | 25,000 | 24: the same 12 plus `BAC_IMS_ORG_ID, DDD_OTLT_NBR, DDD_SUBCAT, DDD_OUTLET_NAME/ADDRESS/CITY/STATE, BAC_CORP_PAR_IMS_ORG_ID, BAC_CORP_PAR_NM, BAC_OWN_SUBS_IMS_ORG_ID, BAC_OWN_SUBS_NM, BAC_CORP_PAR_ST_CD` (app/brief/load.py:8-13) |

- **Both files cover the same 24 months, 202410 to 202609.**
- **The national file has no system ID, no state and no outlet columns.** Its only organisation column is `BAC_CORP_PAR_ORG_TYP_DESC`, with values {Corporate Owner, IDN}. Totals: $29.42B and 258.8M doses. So "national" can only ever mean the pooled national file. There's no national per-system distribution and no national state slice. This restates F-0010 and AS-0034.
- **State comparison exists only through synthetic in-state peers** (same `BAC_CORP_PAR_ST_CD`, excluding the system, at least 5 peers; AS-0031, facts.py:13 and :154).
  - 140 of 180 systems qualify: TX 33, OH 30, CA 22, UT 12, MN 11, PA 9, FL 8, LA 8, ID 7 systems.
  - The other 40 show "too few in-state peers". For example, SYNCP000036 (IL) has 4 peers.
- **Example values:**
  - Classes: Coronavirus, DTaP, HPV, Hepatitis, Hib, Influenza, MMR, Meningococcal, Other, Pneumococcal, RSV, Rotavirus, Shingles, Tdap, Travel, Varicella.
  - Subclasses used: `MenB`, `MenACWY`, `MenABCWY`, `HPV9`, `COVID Vaccine`, `HepB`, `RZV`, `RSV Vaccine`, `RSV Monoclonal Antibody`, `Tdap`, `Varicella`, `DTaP`.
  - Age group (`VAC_AGE_GRP_NM`): Adult / Ped / Mixed. This is a **product** label, not a patient age.
  - Specialty (`BAC_CHNL_SPEC_DESC`): 19 values nationally, 14 in the synthetic file, including "Women's Health" and "Pediatric Medicine".
  - Products: BOOSTRIX TDAP, ABRYSVO, AREXVY, MRESVIA (national only), SHINGRIX, GARDASIL 9, VARIVAX, PENBRAYA, PENMENVY.
  - Manufacturers: PFIZER, GSK PHARM, MERCK & COMPANY, SANOFI, SEQIRUS, MODERNA INC, among others.
- **Synthetic-data artefacts** (they matter for honest talking points):
  - HepB Ped is 0 doses in every synthetic system. Synthetic HepB is all Adult; nationally HepB Ped is 6,711,748 doses.
  - All 80 subsidiary IDs appear under more than one parent. 20,000 of 25,000 rows have a blank subsidiary.
  - 2,395 of 2,400 outlets appear under more than one specialty.
  - 62 of 180 systems give "private babies > total babies".
  - Women's Health has a median of 2 rows per system, and 23 systems have none.
  - Net doses can be negative after returns (SYNCP000036 COVID Vaccine is −80).

## 2. Component architecture

```mermaid
flowchart LR
  SYN[data/BIA_562_Synthetic_Sales_Data.csv] --> LOAD[load.py + clean.py]
  NAT[data/BIA 562 National System Data.csv\nbenchmark only, D-0034] --> BM[benchmark.py\n+ national_profile()]
  LOAD --> FACTS[facts.py F1..F8 unchanged]
  LOAD --> CM[client_metrics.py NEW: F9..F14\nsystem / state peers / national]
  BM --> CM
  CM --> AVAIL[availability.py NEW\nOK / DERIVABLE / NOT AVAILABLE]
  FACTS --> TP[talking.py NEW\nmust-cover selection]
  CM --> TP
  TP --> VAL[validator.py\ntoken regex widened to F1..F14]
  MIC[st.audio_input WAV 16 kHz] --> STT[stt.py NEW\nTranscriber seam: faster-whisper | stub | none]
  TYPED[st.text_area] --> NOTES[notes]
  STT --> NOTES
  NOTES --> PAY[payload.py NEW\nTask-shaped JSON + JSON Schema]
  TP --> PAY
  CM --> PAY
  PAY --> STORE[visits.py NEW\nSQLite visits + send_log]
  STORE --> LOOK[Lookup tab]
  GEN[gen/out read-only] --> CON[contracts.py unchanged]
```

- **New modules** all go under `app/brief/`, so the existing deploy image picks them up without changes. They are `client_metrics.py`, `availability.py`, `talking.py`, `stt.py`, `payload.py`, `visits.py`, `deploy_smoke.py`, `schemas/visit_payload.schema.json` and `fixtures/visit_note_fixture_16k.wav`.
- **facts.py, F1..F8 and T-0001..T-0008 stay as they are.** The new facts live in `client_metrics.py` and get merged into the FactSheet under new IDs, so no existing pin moves.
- **validator.py:10** today only accepts `F[1-8]` tokens. It widens to `F(?:[1-9]|1[0-4])`, with a redproof mutation that checks a `{F15.x}` token is still rejected.

## 3. Data contract per metric

Notation:
- **sys** = the system's rows (`BAC_CORP_PAR_IMS_ORG_ID`).
- **state** = pooled synthetic in-state peers (AS-0031).
- **nat** = the whole national file.
- **Index** = sys ÷ comparator × 100 (AS-0032 style).
- **Availability** is one of: OK (column exists), DERIVABLE (needs a stated mapping or heuristic), NOT AVAILABLE (no column; never invented).
- National reference values come from the metrics probe output (pinned in T-0042).

### 3.1 The client's "Key System attributes" (11/13 email, quoted)

| # | The client's words | Fact id | Formula / source columns | sys | state (synthetic peers) | national | Notes |
|---|---|---|---|---|---|---|---|
| A1 | "Total System Vaccines Dollars" | F1.dollars (exists) + F9.share_state, F9.share_nat | Σ`DOLLARS`; state share = sys ÷ (sys + pooled in-state peers), bounded 0 to 1, with the in-state peer median dollars shown for scale (AS-0043 (comparators), amended); national share = sys ÷ national | OK | OK | OK (share of national $; the current F1.bench_share in national mode) | No national per-system distribution, so "how big vs national" is a share, not a rank |
| A2 | "% Vaccines Dollars by Class" | F9.cls_pct | Σ$ by `VAC_PROD_CLAS_NM` ÷ Σ$ | OK | OK | OK | Show the top 5 + Other, each with an index vs state and vs national |
| A3 | "% Vaccines Dollars by Specialty" | F9.spec_pct | Σ$ by `BAC_CHNL_SPEC_DESC` ÷ Σ$ (AS-0028) | OK | OK | OK | National has 5 specialties the synthetic file lacks (Dialysis, Long Term Care, Non-Retail Walk-In, Retail, Retail Walk-In) |
| A4 | "% Vaccines Doses by Class and Specialty" | F9.cls_spec_dose_pct | Σ`DOSES` by (class, specialty) ÷ Σdoses | OK | OK | OK | Sparse. The UI shows the top 10 cells; the full grid goes in an expander |
| A5 | "Corporate_Parent_Type" | F10.parent_type | `BAC_CORP_PAR_ORG_TYP_DESC` (one value per system, verified) | OK | n/a (label) | DERIVABLE: national $ split by the same type, for a type-peer mix | The client's field name doesn't exist; this mapping is AS-0042 |
| A6 | "Corporate_Parent_State" | F10.parent_state | `BAC_CORP_PAR_ST_CD` (one value per system) | OK | n/a | **NOT AVAILABLE**: the national file has no state column | |
| A7 | "# of Subsidiary" | F10.n_subs | nunique non-blank `BAC_OWN_SUBS_IMS_ORG_ID` | DERIVABLE, flagged "synthetic artefact" (14–35 per system; IDs shared across parents) | DERIVABLE (peer median) | **NOT AVAILABLE** | |
| A8 | "# of DDD_Number" | F10.n_ddd | nunique `DDD_OTLT_NBR` (outlets never cross parents) | OK (13–14 per system) | OK (peer median) | **NOT AVAILABLE** | The client's name maps to DDD_OTLT_NBR (AS-0042) |
| A9 | "# of DDD_Number by Specialty" | F10.n_ddd_by_spec | nunique `DDD_OTLT_NBR` with ≥1 row in that specialty | DERIVABLE with caveat: specialty is per row, not per outlet, so the counts add up to more than A8 | DERIVABLE | **NOT AVAILABLE** | |
| A10 | "Public vs. Private — Total babies = Doses (Class='Varicella')/2; Private babies = Doses (Class='DTaP')/5" | F11.babies_total, F11.babies_private, F11.babies_public, F11.private_share | total = Σdoses class Varicella ÷ 2; private = Σdoses class DTaP ÷ 5; public = total − private; share = private ÷ total | DERIVABLE (the client's heuristic, labelled "estimate"). When private > total, the status is "inconsistent (private exceeds total)" and no public number is shown (62/180 systems) | DERIVABLE | DERIVABLE (nat total 3,514,862.5; private 2,253,839.8; share 0.641) | "Public = total − private" is the architect's reading; confirm with the client (Q-K5) |
| A11 | "Pediatric vs. Adult" | F12.ped_share, F12.adult_share, F12.mixed_share | Σdoses by `VAC_AGE_GRP_NM` ÷ Σdoses | DERIVABLE: a product label, not patient age; Mixed is about 63–65% of doses | DERIVABLE | DERIVABLE (nat Ped 0.155, Adult 0.193, Mixed 0.653) | The client's "Age_Group" maps to VAC_AGE_GRP_NM (AS-0042) |

### 3.2 The client's "Important Ratios — compare vs national and state ratios" (quoted)

Each ratio follows AS-0044:
- Shown as a value when the denominator is at least 50 net doses and the numerator is at least 0.
- Denominator ≤ 0 gives "undefined".
- Denominator under 50 gives "insufficient volume".
- A negative numerator gives "net returns".
- Never inf, never negative.

| # | The client's words | Fact id | Formula | sys/state | national (value) | Availability / caveat |
|---|---|---|---|---|---|---|
| R1 | "Doses (SubClass in MenB + MenABCWY) / Doses (SubClass in Men ACWY + MenABCWY)" | F13.r1 | subclass ∈ {MenB, MenABCWY} ÷ subclass ∈ {MenACWY, MenABCWY} | OK | 0.5483 | OK. **Differs from F6** (MenB/MenACWY only, nat 0.541, F-0010). F6 stays for T-0002 and the PDF; R1 is the v0.2 brief figure |
| R2 | "Doses (Class = 'HPV') / Doses (SubClass in Men ACWY + MenABCWY)" | F13.r2 | class HPV ÷ {MenACWY, MenABCWY} | OK | 1.2570 | OK |
| R3 | "Doses (Class = 'Influenza') / Doses (SubClass = 'COVID Vaccine')" | F13.r3 | class Influenza ÷ subclass COVID Vaccine (antivirals excluded by subclass) | OK | 5.6960 | OK. 11 synthetic systems have a COVID denominator ≤ 0 (for example SYNCP000036 at −80), which gives "undefined" |
| R4 | "Hep B Ped 'high'" … "excessive Hep B ped usage which indicates using ped dose for adults. Doses (SubClass = 'HepB' and Age_Group = 'Ped') /" | F13.r4 (held) | numerator: subclass HepB and VAC_AGE_GRP_NM Ped | **numerator 0 in all 180 synthetic systems** | numerator 6,711,748 (46.9% of national HepB doses) | **NOT AVAILABLE as a ratio: the client's denominator is cut off in the email.** Synthetic data also can't show it. Ship only "HepB Ped share of HepB doses", labelled as the architect's placeholder, and only if the owner or the client accept it (Q-K1) |
| R5 | "Doses (Class = 'Shingles') / Doses (Class = 'Influenza' and Age_Group = 'Adult')" | F13.r5 | class Shingles ÷ (class Influenza and VAC_AGE_GRP_NM Adult) | DERIVABLE (Age_Group maps to the product age label) | 0.1928 | 21 synthetic systems have no adult-labelled flu, giving "undefined" |
| R6 | "Doses (SubClass = 'RSV Vaccine') / Doses (Class= 'Influenza' and Age_Group = 'Adult') *** Ideal this would be Older Adult RSV" | F13.r6 | subclass RSV Vaccine ÷ adult flu | DERIVABLE as written | 0.0802 | **Older-adult RSV: NOT AVAILABLE.** There's no patient-age column, and ABRYSVO is sold for both maternal and older-adult use. One proxy is AREXVY+MRESVIA only (nat 0.0199), but it drops older-adult Abrysvo, so it's offered rather than assumed (Q-K2). 145/180 synthetic systems have under 50 RSV doses, so expect many small ratios |
| R7 | "specifically looking at OBGYN offices and comparing Boostrix, Flu and RSV doses during the season" | F13.r7_* | within specialty "Women's Health": doses of PROD_NM BOOSTRIX TDAP, class Influenza and subclass RSV Vaccine in the season window (AS-0046); shown as 3 shares of their sum | DERIVABLE (OBGYN maps to Women's Health; season is a month window) | DERIVED (same OBGYN and season mapping; matches the registry) | Synthetic data is sparse (median 2 Women's Health rows per system; 23 systems have none), so expect "insufficient volume". SEASON_DESC only fills flu/COVID(/RSV) rows and is inconsistent in the synthetic file, so it isn't used (Q-K3) |

**Update (client email 2026-11-13, PR 6-lite).** The client's 11/13 items supersede parts of this table; the rows above keep the original text for the record:
- **R4** becomes the client's interim definition: Doses(SubClass = 'HepB' and Age_Group = 'Ped') ÷ Doses(Class = 'DTaP'), DERIVED at every level under AS-0044 (AS-0053). Synthetic HepB Ped is 0, so the synthetic value is a computed 0 (179 systems; 1 insufficient volume); national 0.5956.
- **R6** uses the full RSV Vaccine subclass (every product); the older-adult proxy is dropped (AS-0054). National 0.0802.
- **OBGYN** (Women's Health, Oct–Mar season months, the R7 window 202510–202603) gains two ratios: Doses(Class = 'Influenza') ÷ Doses(SubClass = 'Tdap') and Doses(SubClass = 'RSV Vaccine') ÷ Doses(SubClass = 'Tdap') (AS-0055). National 0.3452 and 0.2629.
- **Babies:** private (DTaP ÷ 5) over total (Varicella ÷ 2), shown against state peers and national (AS-0056). National 0.641.

### 3.3 Other client items (11/11 and 11/13)

| Item | Fact id | Formula | Availability |
|---|---|---|---|
| "Produce them grouped by BAC_CORP_PAR_IMS_ORG_ID" | (system key) | `SID` (facts.py:14) | OK synthetic; **NOT AVAILABLE national** (no ID) |
| "Highest Dollars / VAC_PROD_CLAS_NM", "/ BAC_CHNL_SPEC_DESC", "/ MFR_NM" | F2/F3/F4 (exist) + national share per item in F9 | Σ$ ranked | OK, both files |
| "Changes in purchasing over time (switch from one brand/manufacturer to another inside the same Class)" | F14.mfr_moves, F14.brand_moves | the z-test in switching.py, run on (class, MFR_NM) and (class, PROD_NM); **windows are same-season**: W1' 202410–202503 vs W2' 202510–202603 (AS-0046, closes AS-0039); national share move for the same class and windows shown alongside | OK, both files |
| "Changes in purchasing over time inside the same Class" | F14.class_trend | class $ and doses by month, sys vs national share-of-class index | OK |
| "feed it the entire universe of systems" | — | all 180 synthetic systems are already loaded (F-0008) | **Real system universe: NOT AVAILABLE.** The national file is aggregate only (Q-K4) |

### 3.4 Availability registry (`availability.py`)
- A single dict `{metric_id: (status, reason, columns)}` that the UI, the payload and the tests all read.
- A NOT AVAILABLE metric renders the literal text `not available: <reason>` and never a number, and it isn't eligible as a talking point.
- Summary: **NOT AVAILABLE** = national state (A6), national subsidiaries / DDD / DDD-by-specialty (A7–A9), national system grouping and a real system universe, R4 as a ratio (denominator missing; synthetic numerator always 0), and older-adult-only RSV (R6 ideal). **DERIVABLE with a caveat** = A5 national type mix, A7, A9, A10, A11, R5, R6, R7.

## 4. Brief and talking-point rules

**Brief tab, v0.2.** Keep the existing tiles, 4 charts, "Contracts on file" and F5 flags. Add a "System vs state peers vs national" table: one row per A1–A4, A10–A11 and R1–R7, with columns `metric | system | state peers (n) | national | index vs state | index vs national | status`. Values come from fact tokens through `fmt_fact`. A NOT AVAILABLE row shows its reason. Below that sits a compact attribute strip for A5–A9. The state column is labelled "synthetic peers (state)" and the national column "national (D-0034)".

**Talking points tab, NEW.** Generated by `talking.py`, from templates only (no LLM in v0.2; the LLM wire-in stays at 11/18–20 behind the same validator, AS-0035).
1. **Fixed slots (always shown):** size vs state and national (A1); top class (F2) with its national index; current switching status (F14 or F5).
2. **Must-cover slots (AS-0045):**
   - Candidates are R1–R3, R5–R7 and the A2 top-5 classes with status ok, where |index − 100| ≥ 25 against national or state.
   - Rank them by |ln(index/100)|, then by metric id.
   - Take the top 3. Each point names the system value, the comparator value and the n.
   - If nothing qualifies, show "No ratio differs from state peers or national by a quarter or more."
3. **Question slot:** "Ask what is driving purchasing in {class}…" (existing pattern, templates.py:29-30).
4. **Guardrails** (all already enforced by validator.py:10-16, now also run over talking points):
   - No digits outside fact tokens.
   - No unknown tokens.
   - No clinical words.
   - No "should charge".
   - No advisory word together with a commercial term.
   - **Plus:** a token whose availability is NOT AVAILABLE is rejected (new check), and a talking point can't cite a fact whose status isn't ok.
5. **Rendering:** each point gets a checkbox ("covered"). The checked set goes into the payload.

## 5. Voice notes (STT)

| Item | Design |
|---|---|
| Widget | `st.audio_input("Record visit notes", sample_rate=16000)`. Present in Streamlit 1.67.0 (verified signature; returns an `UploadedFile` WAV). AppTest has `AudioInput`. The typed `st.text_area` is always shown, and the transcript pre-fills it so the rep can edit before saving |
| Engine | `faster-whisper==1.2.1` (ctranslate2 4.9.0). CPU, `compute_type="int8"`, `cpu_threads=2`, `beam_size=1`, `language="en"` |
| Model | **base.en** (141 MB download). small.en (464 MB) is opt-in via `LB_STT_MODEL`; tiny.en (75 MB) is the low-resource fallback |
| Decode | **Don't hand faster-whisper a file path.** On the dev machine, PyAV 19.0.2 fails (`open() got an unexpected keyword argument 'metadata_errors'`) and `av<15` has no cp313 wheel (F-0018). Decode the WAV with stdlib `wave` + numpy to float32 and pass the array |
| Offline | The model sits in a local dir (`LB_STT_MODEL_DIR`) with `HF_HUB_OFFLINE=1` at runtime. Laptop: download once, with a GO. Server: baked into the image (deploy plan) |
| Measured cost (dev machine, 8 vCPU, 2 threads, clean TTS speech) | tiny.en 0.24–0.28 s per ~8 s clip (RTF 0.03–0.04, RSS 271–330 MB); **base.en 0.47–0.54 s (RTF 0.07, RSS ~360 MB)**; small.en 1.26 s (RTF 0.17, RSS 807 MB). All were word-correct on the fixture. **The laptop and the server are not measured.** Real rep audio will be worse |
| Fallback | `stt.get_transcriber()` returns `FasterWhisper`, `Stub` (tests) or `None`. With None (package or model missing, or `LB_STT=off`), the audio widget is hidden, a caption says "voice unavailable: <reason>", and typed notes still work. Any exception during transcription falls back to typed input with a note (same pattern as narrative.compose) |
| Privacy | **Raw audio is never written to disk or the DB (D-0038 (no raw audio kept)).** Only the edited transcript is kept, and `notes_source` records voice / typed / voice+edited |
| Dependencies | `app/requirements-voice.txt` (faster-whisper, ctranslate2, tokenizers, onnxruntime, av, huggingface-hub, pinned). CI's base `app/requirements.txt` is unchanged; the real-model test is marked `stt` and runs on the dev machine and in the deploy smoke |
| Fixture | `app/brief/fixtures/visit_note_fixture_16k.wav`: 8.27 s, 16 kHz mono, sha256 `25c20546…3f82`. Generated with piper voice en_US-ljspeech-medium (LJSpeech is public domain). Text: "Visit note for the demo. I met the clinic manager today. We talked about flu season, shingles, and the follow up meeting next week." |

## 6. Salesforce-ready payload (simulated)

- **Shape:** an sObject Collections request body with one standard `Task` (`TaskSubtype` "Call"). The account is matched by a proposed external-ID field.
- Fields ending in `__c` are proposed custom fields. **None of this is validated against a real org** (AS-0049).
- The schema is checked with `jsonschema` (already pinned, app/requirements.txt).

```json
{
  "allOrNone": true,
  "records": [{
    "attributes": {"type": "Task"},
    "Subject": "Visit: Sunrise Care Partners 025 (SYNCP000025)",
    "ActivityDate": "2026-11-18",
    "Status": "Completed",
    "Priority": "Normal",
    "TaskSubtype": "Call",
    "Type": "Visit",
    "What": {"attributes": {"type": "Account"}, "LB_System_Id__c": "SYNCP000025"},
    "Description": "<rep notes, edited transcript>",
    "LB_Visit_Key__c": "demo rep|2026-11-18|SYNCP000025",
    "LB_Rep_Name__c": "Demo Rep",
    "LB_Notes_Source__c": "voice+edited",
    "LB_Talking_Points__c": ["Size: …", "R1 MenB+MenABCWY to MenACWY+MenABCWY is 0.63 against 0.83 for state peers and 0.55 nationally."],
    "LB_Points_Covered__c": [true, false],
    "LB_Metrics__c": {"F13.r1": {"system": 0.625, "state": 0.832, "national": 0.5483, "status": "ok", "n_state_peers": 7}},
    "LB_FactSheet_Id__c": "FS-SYNCP000025-202609",
    "LB_Benchmark__c": "national (D-0034) + synthetic peers (state)",
    "LB_App_Sha__c": "<git sha>",
    "LB_Schema_Version__c": "lb-visit-0.2",
    "LB_Synthetic__c": true
  }]
}
```

- The SYNCP000025 values shown were computed today: FL, IDN, 7 in-state peers; R1 system 150/240, state 952/1144, national 0.5483.
- **Required fields:** Subject, ActivityDate (ISO date), Status, TaskSubtype, What.LB_System_Id__c (`^SYNCP\d{6}$`), Description, LB_Visit_Key__c, LB_Rep_Name__c, LB_Schema_Version__c, LB_Synthetic__c (const true).
- **Constraints:** `additionalProperties: false` on the record. LB_Metrics__c holds only aggregate values (no raw national rows).
- **"Send"** = validate the payload, write it to SQLite, and append to `send_log` with status `simulated`. No socket is opened.

## 7. SQLite store

Path: `LB_VISITS_DB`, default `<repo>/app/var/visits.sqlite`; `app/var/` goes into .gitignore (AS-0050). Stdlib `sqlite3`, no new dependency. `PRAGMA user_version = 1`, `journal_mode=WAL`, `foreign_keys=ON`.

```sql
CREATE TABLE visits (
  visit_key      TEXT PRIMARY KEY,                -- rep_name_norm|visit_date|system_id
  rep_name       TEXT NOT NULL,
  rep_name_norm  TEXT NOT NULL,                   -- casefold, trim, collapse spaces (AS-0048)
  visit_date     TEXT NOT NULL CHECK (visit_date GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]'),
  system_id      TEXT NOT NULL CHECK (system_id GLOB 'SYNCP[0-9][0-9][0-9][0-9][0-9][0-9]'),
  system_name    TEXT NOT NULL,
  notes_text     TEXT NOT NULL,
  notes_source   TEXT NOT NULL CHECK (notes_source IN ('voice','typed','voice+edited')),
  payload_json   TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  app_sha        TEXT,
  revision       INTEGER NOT NULL DEFAULT 1,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  synthetic      INTEGER NOT NULL DEFAULT 1 CHECK (synthetic = 1),
  UNIQUE (rep_name_norm, visit_date, system_id)
);
CREATE TABLE send_log (
  id INTEGER PRIMARY KEY, visit_key TEXT NOT NULL REFERENCES visits(visit_key),
  sent_at TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('simulated')), payload_sha256 TEXT NOT NULL
);
CREATE INDEX visits_by_date ON visits (visit_date, system_id);
```

- **Saving to an existing key** is refused unless "Replace existing visit" is ticked. A replace bumps `revision`, sets `updated_at` and logs the send.
- **Lookup:** filters for rep (normalised prefix), date (exact or range) and company (system id or name substring), giving a result table. Picking a row shows the notes, the covered points, the metric snapshot and the payload JSON, plus a download.
- **Parameterised SQL only.**

## 8. UI changes (app.py; tabs today at app.py:38)

- **Sidebar:** benchmark radio and system picker (unchanged), plus **Rep name** and **Visit date** (default today), which feed the visit tabs.
- **Tabs:** `Brief` (+ comparison table) | `Talking points` (NEW) | `Visit notes` (NEW: audio + text) | `Send to Salesforce (simulated)` (NEW: payload preview, validate, save) | `Visit lookup` (NEW) | `Contract Q&A` (unchanged).
- **Banner on the visit tabs:** "Demo: synthetic data. Notes are stored locally; nothing is sent to Salesforce. Do not enter patient information."
- **If Q-M1 option (a) is chosen**, the three visit tabs sit behind a passcode.

## 9. Log entries (proposed; numbering continues after gate2-regen)

**Decisions (the owner's words only; verbatim quotes required before logging):**
- **D-0036 (v0.2 scope):** brief, must-cover talking points from computed numbers, voice notes, and a Salesforce-shaped payload with a simulated send to SQLite, looked up by rep + date + company. Source: the owner's GO, 11:42 AM PT 11/13. **Accepted** (verbatim in docs/decisions.md).
- **D-0037 (no real Salesforce):** no Salesforce network calls, library or credentials.
- **D-0038 (no raw audio kept):** only the edited transcript is stored.
- **D-0039 (v0.2 deploy GO):** **Accepted** 11:49 PT 11/13 (verbatim in docs/decisions.md). Little Blue only; each merge and deploy still needs the Architect's approval.
- **D-0040 (public visit exposure):** the owner's choice from Q-M1.

**Assumptions:**
- **AS-0042 (client field mapping):** Specialty = BAC_CHNL_SPEC_DESC; Corporate_Parent_Type = BAC_CORP_PAR_ORG_TYP_DESC; Corporate_Parent_State = BAC_CORP_PAR_ST_CD; DDD_Number = DDD_OTLT_NBR; Subsidiary = BAC_OWN_SUBS_IMS_ORG_ID; Age_Group = VAC_AGE_GRP_NM (product label); OBGYN = "Women's Health".
- **AS-0043 (comparators):** national = the whole national file pooled; state = synthetic in-state peers (AS-0031). The national file has no state.
- **AS-0044 (ratio rule):** denominator ≥ 50 net doses, numerator ≥ 0. Statuses are undefined / insufficient volume / net returns. Index = sys ÷ comparator × 100.
- **AS-0045 (must-cover selection):** |index − 100| ≥ 25, ranked by |ln(index/100)|, top 3, with 3 fixed slots and 1 question.
- **AS-0046 (season windows):** flu season = Oct–Mar. Same-season windows for F14 are 202410–202503 vs 202510–202603 (closes AS-0039). The R7 season = Oct–Mar months in the latest full season, 202510–202603.
- **AS-0047 (STT):** faster-whisper base.en int8 on CPU, 2 threads, stdlib WAV decode, offline model dir.
- **AS-0048 (visit key):** `casefold(trim(collapse_ws(rep)))|YYYY-MM-DD|SYNCP…`.
- **AS-0049 (payload shape):** sObject Collections plus a Task, with proposed `LB_*__c` fields; not validated against an org.
- **AS-0050 (DB path):** `LB_VISITS_DB`; local default app/var (gitignored); the server path is in the deploy plan (not in this repository).
- **AS-0051 (PDF unchanged):** the v0.2 additions stay out of the one-page PDF (T-0006).
- **AS-0052 (deploy deltas):** the Little Blue-only server config changes, in the deploy plan (not in this repository).

**Findings:**
- **F-0014:** the national file has no system, state or outlet columns (restates F-0010), so national comparisons are pooled only.
- **F-0015:** synthetic HepB Ped is 0 in all 180 systems; national HepB Ped is 6,711,748 doses.
- **F-0016:** subsidiary IDs cross parents (80/80); 2,395/2,400 outlets cross specialties.
- **F-0017:** the client's babies heuristic gives private > total in 62/180 synthetic systems.
- **F-0018:** PyAV 19.0.2 path decode fails in faster-whisper 1.2.1; the stdlib WAV decode works.
- **F-0019:** STT bench numbers as in §5.
- **F-0020:** the live demo blocks microphone access and voice upload today; the change is in the deploy plan (not in this repository).
- **F-0021:** state comparison is available for 140/180 systems.

## 10. Deploy

The deploy plan for v0.2 (in-place upgrade of the public demo at https://little-blue.tailea9f4f.ts.net, its rollback and its smoke) is covered by D-0039 (v0.2 deploy GO), accepted; each deploy still needs the Architect's approval. It is kept outside this public repository because it describes server internals. Nothing in PR 5 to PR 8 changes the server.

## 11. Tests (each must be able to fail) and redproof mutations

| T | What | Mutation(s) that must turn it red |
|---|---|---|
| T-0042 client formulas | Hand-computed fixture cases for A1–A4, A10–A11 and R1–R3, R5–R7. File pins: national R1 0.5483, R2 1.2570, R3 5.6960, R5 0.1928, R6 0.0802; SYNCP000025 R1 = 150/240, state peers 952/1144 (n = 7) | `kr_abcwy` (drop MenABCWY from R1), `kr_swap` (swap numerator and denominator) |
| T-0043 availability | Every client item has a registry entry. A NOT AVAILABLE item renders "not available" and no digit. A6, A7–A9 national, R4 and older-adult RSV are NOT AVAILABLE. The state column is labelled synthetic peers | `invent` (registry returns 0 for a national A8) |
| T-0044 ratio guards | Denominator ≤ 0 gives undefined; < 50 gives insufficient; numerator < 0 gives net returns; never inf or negative. SYNCP000036 R3 is undefined; 140/180 have a state comparison | `ratio_neg` (drop the ≤ 0 check) |
| T-0045 talking points | Every point passes the validator; must-cover selection is deterministic and follows AS-0045; tokens resolve only to status-ok facts; no clinical or advice language across all 180 systems | `tp_digit` (a literal number in a template), `tp_select` (threshold 25 → 0), `tp_na` (allow a NOT AVAILABLE token) |
| T-0046 STT | The stub transcriber feeds the text area; transcriber None or an exception falls back to typed with a note; WAV decode via `wave` gives float32 at 16 kHz; **no audio bytes on disk or in the DB** (scan tmp + DB). `@stt` (dev machine and deploy smoke only): the fixture gives ≥ 3/4 keywords | `stt_nofallback`, `stt_persist` (write the WAV to app/var) |
| T-0047 payload | Validates against the JSON Schema; required fields; `LB_Synthetic__c` true; key = AS-0048; no raw national rows (Metrics values are aggregates only) | `payload_drop` (remove ActivityDate), `payload_extra` (add an unlisted field) |
| T-0048 visit store | Save then lookup by (rep, date, company) round-trips with the payload sha256 equal; rep normalisation; duplicate refused without replace; replace bumps revision; parameterised SQL (an injection string is stored literally) | `store_key` (drop the date from the key), `store_overwrite` (silent replace) |
| T-0049 no Salesforce network | `socket.socket.connect` is patched to raise during the send flow; there's no `simple_salesforce` or `salesforce.com` in app/ | `net` (the send calls `urllib.request.urlopen`) |
| T-0050 visit gate (if Q-M1 = a) | Unset passcode: visit tabs disabled. Wrong passcode: denied. Right passcode: open. Uses compare_digest | `gate_open` (unset means open) |
| T-0051 visits never training or gen input | `refuse_training_input` refuses `*.sqlite` and `app/var/`; the gen/ scan flags a planted visits reference; `.gitignore` covers app/var and `git ls-files` has no *.sqlite | `trainguard_visits` |
| T-0052 UI tabs (AppTest) | 6 tabs in order; Talking points shows checkboxes; Visit lookup finds a seeded visit; Brief shows the comparison table with "not available" rows | `tabs` (drop the lookup tab) |
| T-0053 validator widening | `{F14.x}` accepted; `{F15.x}` and `{F0.x}` rejected | `tok_wide` (regex `F\d+`) |
| T-0054 F14 same-season switching | Windows are 202410–202503 vs 202510–202603; a planted brand switch inside a class flags; an Influenza season effect no longer flags in the fixture | `season_mismatch` (W2 back to 202604–202609) |

Existing T-0001..T-0041 must stay green, unchanged. The redproof runner (`app/tools/redproof.py`) gains the mutations listed above.

## 12. Open questions

**Owner (real decisions):**
- **Q-M1 (TOP):** public visit read/write on the public URL: (a) a shared passcode on the visit tabs, (b) per-session saves with a read-only seeded lookup, or (c) a synthetic-only banner. **Recommend (a) plus the banner.**
- **Q-M2:** answered: D-0039 (v0.2 deploy GO), accepted (deploy plan kept outside this repository).
- **Q-M3 (CLOSED, Architect ruling 11/13):** the national column is always shown, because the client's ask compares with national AND with state (recorded under AS-0042 (client field mapping)). Original question: should the v0.2 comparison table always show the national column when the file is present? D-0034 (national file public-real) keeps "synthetic peers" as the default for the BENCHMARK toggle. **Recommend yes**: the table is a benchmark, not training, and the toggle keeps governing F1/F6.
- **Q-M4:** STT model base.en (recommended) or small.en; English only?
- **Q-M5:** notes policy on a demo: "no patient information, no real HCP names" banner only, or also a simple pattern block (dates of birth, phone numbers)?
- **Q-M6:** may the deploy persistence smoke leave one smoke row in the server DB?
- **Q-M7:** should the deploy files move into the public repo (no secrets) for reproducibility, or stay outside it as today?
- T-0034 still needs the owner's own yes (unchanged by v0.2).

**Client (routed via the owner):**
- **Q-K1:** the HepB Ped "high" denominator is cut off in the 11/13 email. What is it? Note that the synthetic data has 0 HepB Ped doses.
- **Q-K2:** older-adult RSV. Accept AREXVY+MRESVIA as a proxy (it excludes Abrysvo), or keep the RSV Vaccine subclass as written?
- **Q-K3:** OBGYN = "Women's Health"? And is the season Oct–Mar?
- **Q-K4:** is there a real system-level or state-level file? Without one, "universe of systems" and "vs state" are synthetic-only.
- **Q-K5:** is public babies = total − private? And what should be shown when private > total?
