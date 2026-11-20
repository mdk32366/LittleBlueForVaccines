# Little Blue for Vaccine Sales

A BIA 562 class project, built as a proof of concept for demo purposes only. Little Blue helps a vaccine sales rep prepare for and record a visit to a health system. For each system it builds a one-page visual account brief, answers questions about that system's contracts and proposals with cited source text, and lets the rep log the visit. It is a Streamlit app with downloadable one-page PDF reports.

Every dataset in this repository is synthetic, apart from one public national summary file (see "Data" below). The project was also used to choose, fine-tune and evaluate a small local language model, **Bluebird LLM v1.0**. How that was done is described below. The model is **not** part of the app on `main`.

## What it does

- **Account brief.** Pick a health system and see its sales facts and charts, benchmarked against synthetic peers or the national file, plus must-cover talking points worked out from the computed numbers. Download the brief as a one-page PDF.
- **Contract Q&A.** Ask about a system's contracts and get an answer from that system's documents only. Each answer quotes the source text verbatim and cites it as `<doc_id>#<section>`. A question the contracts can't answer gets exactly "not in the contracts".
- **Visit record.** Log a visit: typed notes, or optional voice notes transcribed locally by the app. The app hints which talking points were raised and suggests an evidence quote and a follow-up for each one using fixed rules. The rep can change every suggestion. Saving stores the visit and a FAKE Salesforce-shaped payload record in the app's own SQLite database.
- **Integration (dry run).** Shows, as text only, the one Salesforce Composite request (allOrNone) that a real integration would send.

## What it does not do

- **No real data.** The contracts, proposals, Q&A and visit narratives are invented. Every generated document says "SYNTHETIC TRAINING DOCUMENT. NOT A REAL AGREEMENT. Terms are invented." and every Q&A row carries `terms_invented: true`.
- **No pricing advice, and no efficacy or safety claims.** The brief's text goes through a validator that rejects clinical-claim words and pricing advice (D-0009 (denylist)). The generated Q&A includes pricing and clinical questions, and their answer is the refusal string.
- **No Salesforce connection.** The app never connects to Salesforce and stores no Salesforce credentials. Nothing is sent (D-0037 (no real Salesforce), D-0045 (Salesforce dry run), D-0046 (one Composite request, allOrNone)).
- **No language model in the app on `main`.** The brief's narrative is templated (LLM off), and the visit suggestions are deterministic rules. Bluebird was trained and evaluated outside this repository. Its integration work is on a separate branch that has not been merged (see "Where we left off").
- **No model weights in this repository.** No base model, adapter, merged model or GGUF file is committed, and none will be.
- **Not for public or production use.** No patient data. Not reviewed for any real commercial use.

## Data

- `data/BIA_562_Synthetic_Sales_Data.csv`: the synthetic sales file the class provided. Every brief figure comes from it.
- `data/BIA 562 National System Data.csv`: a public national summary, treated as public and real (D-0034 (national file public-real)). It is used as a benchmark and, from GATE 2, as a generator input (D-0041 (national file is generator and training input)).
- `gen/out/`: the generated contract corpus (seed 562): 180 synthetic health systems, 623 documents and 8,363 Q&A rows. Real manufacturer and brand names appear because they are public information (D-0035 (real names, fake grounding), D-0043 (real names in generated data), D-0044 (real manufacturer as the contract party)). The contract terms themselves are always invented.

## Run it locally

Python 3.13 is what CI uses.

```bash
# App
cd app
pip install -r requirements.txt
streamlit run app.py

# Optional: voice notes (faster-whisper, small.en by default)
pip install -r requirements.txt -r requirements-voice.txt

# Batch PDF reports from the command line
python cli.py --system SYNCP000025 --out reports/
```

The app reads `../data/` and `../gen/out/`. Override them with `DATA_PATH`, `NATIONAL_PATH` and `GEN_OUT`. Visits go to `LB_VISITS_DB` (default `data/visits.db`, which git ignores).

### Tests

```bash
cd gen && pip install -r requirements.txt && python -m pytest tests && python tools/redproof.py
cd app && python -m pytest tests && python tools/redproof.py && python tools/smoke.py
```

Some app tests need `poppler-utils` (`pdfinfo`, `pdftotext`). The red-proof scripts break each guard on purpose and check that its test goes red. CI (`.github/workflows/ci.yml`) runs both suites, both red-proofs and a headless smoke test on every push and pull request.

To regenerate the corpus, run `cd gen && python tools/gen_contracts.py --seed 562 --out out/`.

## Repository layout

| Path | What it holds |
|---|---|
| `app/` | The Streamlit app (`app.py`), the `brief/` package, the command-line PDF tool, tests and red-proof |
| `gen/` | The synthetic contract and Q&A generator (`bia562gen/`), its tests, and the accepted `out/` run |
| `data/` | The synthetic sales file and the public national file |
| `docs/architecture.md` | How the generator and the app are built, version by version |
| `docs/decisions.md` | Decisions (D-) with the owner's wording where there is one |
| `docs/assumptions.md` | Assumptions (AS-) |
| `docs/testplan.md` | Test ids (T-) and the test file behind each one |
| `docs/findings.md` | Findings (F-), including the Bluebird run and evaluation |
| `docs/spec-v0.2.md` | The 13 Nov v0.2 draft spec, kept for history and now superseded |

The decision, assumption, finding and test ids in `docs/` are local to this repository. Program-level ids are labelled as such where they are cited (see `docs/decisions.md`).

## Project status

- **App versions on `main`:** the first version (brief, Contract Q&A, PDF), then v0.2-a to v0.2-g (client metrics, talking points, voice notes, visit store and payload record, Salesforce dry run, one Composite request, missed talking-point follow-up), then v0.2-h1 (rule-based evidence quote and follow-up), with follow-ups h1b and h1c. The last merge is PR #17, on 15 Nov 2026.
- **Demo deployment:** the last public demo ran commit `b430554d` (v0.2-g, before h1). h1, h1b and h1c were merged but never deployed. The demo was taken down on 20 Nov 2026, after the final class presentation was recorded.
- **Bluebird LLM v1.0:** trained and evaluated, as described below. It is not in the app on `main`.

## How Bluebird LLM v1.0 was built

Bluebird LLM v1.0 is a QLoRA fine-tune of a small open model. It answers questions about the synthetic contracts with verbatim, cited spans, in the same answer format as the generator's Q&A. The goal was a model that runs locally on a CPU, with no internet access, in its own container beside the app. The full records are in `docs/findings.md` (F-0042 to F-0045) and `docs/decisions.md` (program-level D-0070). The steps are below.

### 1. Requirements

- Run on a CPU in its own container, with no network access.
- Return machine-checkable JSON.
- Proposed latency targets for the planned customer-response use: 95th percentile at most 8 s per talking point and at most 60 s for a 7-point visit.
- Fine-tune on one 8 GB laptop GPU with QLoRA.
- The licence has to allow this use, and the result is named "Bluebird LLM v1.0".

### 2. Choosing the base model

Four public 3B to 8B instruct models were screened. Each licence was read from the upstream model card:

| Candidate | Licence | Outcome |
|---|---|---|
| Qwen/Qwen2.5-3B-Instruct (3.1B) | Qwen Research licence, non-commercial only | **Picked.** Usable only because the owner ruled that this class project is non-commercial (a proof of concept for demo purposes only) |
| microsoft/Phi-3.5-mini-instruct (3.8B) | MIT | **Documented fallback** |
| meta-llama/Llama-3.2-3B-Instruct (3.2B) | Llama 3.2 Community licence | **Dropped before benchmarking.** A distributed fine-tune must have a name starting with "Llama" and must show "Built with Llama", which conflicts with the product name. The base repository is also gated |
| Qwen/Qwen2.5-7B-Instruct (7.6B) | Apache-2.0 | Missed both CPU latency targets |

Two lessons came out of this. Licences can differ within one model family: Qwen2.5-3B and Qwen2.5-7B carry different ones. Naming clauses matter as much as commercial-use clauses.

**CPU serving benchmark (measured).**
- **Setup:** llama.cpp `llama-server` (CPU only, Q4_K_M GGUF files) on a 16-thread laptop-class CPU, in throwaway containers with no network, a read-only root filesystem and a memory cap. A guard watched the running app's health throughout and never had to fire.
- **Workload:** 27 talking points from 5 synthetic visit narratives, decoded with temperature 0 and a JSON-schema grammar.
- **Results:** in the one-call-per-point mode, Qwen2.5-3B returned 100 % valid JSON at every thread count, with a 95th-percentile time per point of 4.73 s at 8 threads and 5.29 s at 4 threads. Phi-3.5-mini went over 8 s at 4 threads. Qwen2.5-7B went over both targets at 8 threads.
- **Lesson:** batching several points into one call was fragile even with a grammar (duplicated or missing keys, and token-cap truncation).

**GPU fit test (measured; T-0034).**
- **Question:** does QLoRA at the full 1,536-token row length fit an 8 GB laptop GPU?
- **Method:** 20 optimizer steps × gradient accumulation 16, using 320 training-split rows, each cut to exactly 1,536 tokens. 4-bit NF4 with double quantization, bf16 compute, LoRA r 16, α 32, dropout 0.05 on all linear layers, gradient checkpointing, paged 8-bit AdamW, learning rate 2e-4.
- **Pass rule:** peak allocated GPU memory at most 7.0×10⁹ bytes, all steps complete, and no NaN loss.

| Base | Peak allocated | Result |
|---|---|---|
| Qwen2.5-3B-Instruct | 6,237,824,000 B (5.81 GiB) | PASS |
| Phi-3.5-mini-instruct | 4,109,368,832 B (3.83 GiB) | PASS |

A falling loss over 20 steps only shows that the loop trains. It is not a quality result.

**Pick.** The owner picked Qwen2.5-3B-Instruct as the base on 14 Nov 2026, with Phi-3.5-mini-instruct as the fallback. It is recorded as program-level decision D-0070 (Bluebird LLM v1.0 base is Qwen2.5-3B-Instruct).

### 3. Training data: synthetic contracts and Q&A

The training data is this repository's own generator output (`gen/`, seed 562), and nothing else:

- **Systems and families.** 180 synthetic health systems. A seeded shuffle holds out a quarter of them. Training uses template family A on the 135 training systems (468 documents, 6,273 Q&A rows). The held-out test uses family B on the 45 other systems (155 documents, 2,090 Q&A rows). The two families share no four-word phrase, so the test checks reading rather than recall of templates (D-0024 (family scope), D-0025 (family split), D-0026 (no shared 4-word phrase)).
- **Documents.** Each system gets an invented MSA, amendments, proposals and a purchasing-profile exhibit. The exhibit states the system's figures from the synthetic sales file, its in-state peer figures and pooled national figures. Each contract names a real manufacturer as the party, because brand and manufacturer names are public (D-0043, D-0044). Every term is invented, and every document carries the SYNTHETIC banner.
- **Answers.** Each answer is digit-free prose with `{S1}`, `{S2}` slots, plus spans that must appear verbatim in their anchor clause (LB D-0023 (slot tokens exempt from digit rule)). About 20.5 % of the rows can't be answered from the contracts by design (1,287 training rows). Those rows keep the target `"not in the contracts"`, so the model learns to refuse (D-0027 (refusal string)).
- **Row building.** Each training row holds the question's document plus every anchor clause, in natural numeric clause order. A row over 1,536 tokens drops whole clauses, starting with the ones farthest from the anchor. An anchor or span clause is never dropped. Each row records its token count and a hash of its token ids, and the trainer refuses to start if its own tokenizer disagrees.
- **Guards.** The repository's training guard (`app/brief/train_guard.py`) refuses visit records and databases as training input (T-0051), and accepts the national file only by its recorded sha256 (T-0066).

### 4. The QLoRA training run (measured)

| Setting | Value |
|---|---|
| Base | Qwen2.5-3B-Instruct, pinned revision |
| Method | QLoRA: 4-bit NF4, double quantization, bf16 compute, SDPA attention |
| LoRA | r 16, α 32, dropout 0.05, all linear layers |
| Loss | Completion-only (prompt tokens masked) |
| Rows | 6,273 training rows, at most 1,536 tokens each, no packing |
| Schedule | 2 epochs, gradient accumulation 16, so 786 optimizer steps (393 per epoch); learning rate 2e-4, cosine, no warm-up; seed 562 |
| Optimizer | Paged 8-bit AdamW, gradient checkpointing |
| Peak GPU memory allocated | 6,238,254,080 B, under the 7.0×10⁹-byte abort guard |
| Software | torch 2.11.0+cu128, bitsandbytes 0.50.2, transformers 5.22.2, peft 0.21.2 |
| Hardware | One 8 GB laptop GPU |
| Finished | 4:57 AM PT, 15 Nov 2026, after about 7.7 h of step time |

**Guards.** The run aborts on:
- peak memory over the limit;
- a NaN or infinite loss or gradient;
- CUDA out-of-memory;
- a tokenizer mismatch;
- a data or script file that doesn't match its sha256 manifest;
- a resume with changed settings.

It checkpoints every 50 steps. Each guard was tripped once on purpose, on a tiny CPU stand-in model, before the real run.

**Output.** Only the LoRA adapter is saved. It is kept outside this repository. For reference, the sha256 fingerprint of the adapter weights file is `3b416683…112d`.

### 5. Evaluation

- **Held-out set.** The 2,090 family-B test rows, plus 1,479 probe rows built from them, for 3,569 rows in total. The probes are:
  - counterfactual value swaps;
  - anchor removal, where the answer should become a refusal;
  - clause shuffles;
  - supplier and brand renames;
  - paraphrases.
- **What was compared.** The tuned model (T) against the same base model, untuned and given few-shot examples (S). Both used the same harness with greedy decoding, and the results went through a pinned scorer.
- **Bars.** The pass bars were set before any results came in. They included:
  - a format gate: every test output must be strictly valid JSON;
  - an accuracy floor: the lower bound of the Wilson 95 % interval at least 0.8149, for a stated true accuracy of 0.85;
  - probe bars;
  - a memorisation test.

Results on the 2,090 synthetic test rows (scorer report of 16 Nov 2026):

| Metric | Tuned (T) | Untuned base, few-shot (S) |
|---|---|---|
| Strict correct (all test rows) | **0.7459** [0.7273, 0.7641] (1,559 / 2,090) | 0.0278 [0.0206, 0.0349] |
| Valid answer JSON | 0.9947 (2,079 / 2,090) | 0.255 |
| Refusal F1 | 0.9268 | 0.2358 |
| Paired answer-value gain, T − S | +0.6873 [0.6651, 0.7084]; 1,141 rows right only for T, 0 right only for S | |

- **Probes.** The counterfactual and rename probes passed: the model followed the changed value and leaked no real name after renames. The anchor-removal, clause-shuffle and paraphrase probes failed their bars. A probe failure counts as evidence only if probe rows are as hard as their source rows, and that was not established.
- **Memorisation.** The memorisation test did not fire.
- **Scorer verdict.** Under the strict rules, T is **DEGENERATE**, because 11 test outputs failed the format gate and the accuracy floor was missed.
- **Owner ruling.** The owner judged T a **PASS by owner override** on 16 Nov 2026. The reasoning was that the 0.85 floor had been set too high before any results existed, that the result far exceeded what the untuned model could do, and that the JSON errors were fixable. The scorer verdict is kept on the record next to the override.
- **JSON-format follow-up.** The T run was repeated with a larger output cap and schema-constrained decoding. All 2,090 outputs were then valid, and accuracy was unchanged at 0.7459 (strict verdict INCONCLUSIVE). This is reported as a measurement of the model plus the constrained decoder, not as a re-certification.

All of these numbers measure reading synthetic contracts. They say nothing about any real contract, product or clinical matter.

### 6. Serving on a CPU and the proof of concept

- **CPU check.** The adapter was merged into the base and converted to a Q4_K_M GGUF (about 1.9 GB) for llama.cpp. It was then checked on 200 test rows on CPU only.
  - On a laptop: 152 / 200 right, against 157 / 200 for the GPU model on the same rows; 199 / 200 valid JSON.
  - On the app server, as a sidecar with a 6 GB memory cap and no network: 151 / 200 right at 4 CPUs and 153 / 200 at 8 CPUs; 199 / 200 valid.
  - On the same server, for a short customer-response prompt: 95th-percentile time per point of 4.06 s at 4 CPUs and 3.56 s at 8 CPUs, and 25.49 s and 22.90 s per 7-point visit, with a memory peak of about 1.6 GB.
  - The owner accepted this check as a pass.
- **Lesson.** llama-server's default host prompt cache can break a capped container. Set it explicitly.
- **Proof of concept.** A proof-of-concept integration ran briefly beside the demo app, on its own port, with the live app untouched. It was behind a feature flag (`LB_BLUEBIRD`, off by default) and had two features:
  - Bluebird suggests the customer-response label (Positive, Neutral, Negative or Objection) for each raised talking point. The label is marked as a model suggestion, the rep can override it, and a failed call fills nothing, so it is never saved as a default.
  - Bluebird answers Contract Q&A. On 200 held-out questions it got 132 right (66 %).
- **Not measured.** Bluebird was trained on contract Q&A, not on classifying customer responses, so its accuracy for that use is unmeasured and none is claimed.

### 7. What is held and not done

- **Not merged.** The integration code is on a separate `bluebird-integration` branch, not on `main`. Review found three fixes needed before it can merge:
  - Bluebird's Q&A answers must pass the app's clinical-claim check;
  - a text-matching helper needs word boundaries;
  - one decisions entry needs rewording.
- **Not in production.** The proof of concept was taken down with the demo on 20 Nov 2026.
- **Not published.** No weights, adapter, GGUF, training rows or evaluation harness are in this repository. The training and evaluation code and evidence stay outside the public repository. Only the adapter fingerprint is published.
- **Never built.** A labelled customer-response dataset, and an evaluation of the response-label task.
- **Open evaluation follow-ups.** Whether to re-certify after the JSON-format fix, and the clean-up of the training machine's working files. Both were held for a later decision.

## Where we left off

As of 20 Nov 2026:

- **`main`** is `63344d41` (PR #17, v0.2-h1c, merged 15 Nov 2026). CI is the authority for the test suites.
- **Demo:** retired on 20 Nov 2026 after the final presentation was recorded. The last deployed build was `b430554d` (v0.2-g). Anything newer was never deployed.
- **Bluebird LLM v1.0:** trained (F-0042) and evaluated (F-0043, F-0044), with a CPU serving check (F-0045). Accepted by owner override. Not in the app on `main`.
- **Open items for anyone picking this up:**
  1. Review and merge the `bluebird-integration` branch once its three fixes land (see section 7 above).
  2. Decide whether the JSON-format rerun should replace the original T result on the record.
  3. Close or rewrite issue #4, an early v0.2 checklist whose work has all shipped.
  4. D-0038 (no raw audio kept) is still worded only as an assumption, AS-0059 (raw audio is not kept). The app already behaves that way.
  5. Some client data questions are still open, such as the HepB Ped figure behind R4 (AS-0053 (R4 interim definition)).
- **Rules that still apply:** no weights or private evidence in this repository, no pricing advice, no efficacy or safety claims, and synthetic data only.
