# Bluebird LLM v1.0 (`bluebird-v1.0-e2`)

**Built with Qwen.** Bluebird is a LoRA adapter for `Qwen/Qwen2.5-3B-Instruct`. The base model is under the Qwen RESEARCH LICENSE AGREEMENT, which allows non-commercial use only (research or evaluation). See [LICENSE-NOTES.md](LICENSE-NOTES.md).

## What Bluebird is
Bluebird is a QLoRA fine-tune of Qwen2.5-3B-Instruct. It answers questions about vaccine-supply contracts and returns JSON of the form `{answer, spans}`. The spans point to the contract text that supports the answer. It was built for Little Blue / BIA 562.

This folder holds the training code and data, the eval and scoring harness, the run evidence and scored results, and the final adapter weights. The adapter weights are stored in Git LFS. **The base model weights are not here.** Download them from Hugging Face (see below).

## Data: all synthetic
All training and eval rows are made up. There is no patient data and no real contract data. Matt Kelly ruled on 2026-11-20 (t576u): "There is ZERO patient data. It was all made up data." Row ids start with `SYN-`, and `train/build_train_rows.py` asserts `q["synthetic"]` on every row.

## Base model
- Hugging Face id: `Qwen/Qwen2.5-3B-Instruct` (https://huggingface.co/Qwen/Qwen2.5-3B-Instruct). Checked on its card on 2026-11-20. The card states `license: other`, `license_name: qwen-research`.
- Revision: the tokenizer used to build the training rows is pinned at rev `aa8e7253...` (`train/build_train_rows.py`, line 2). The download command in `results/records/HOWTO-bluebird-llm@0.1.md` §9 pins the full revision `aa8e72537993ba99e69dfaafa59ed015b17504d1`, and that is the HF `main` sha as of 2026-11-20. The laptop training logs were not available for this push, so this repo does not independently confirm which revision of the *weights* the laptop run loaded. `train/train.py` does check that every tokenized row's token count matches the rows file, which was built with the pinned tokenizer.

### `adapter/adapter_config.json` holds a local Windows path
`base_model_name_or_path` in `adapter/adapter_config.json` is `C:\Users\mdk32\models\Qwen2.5-3B-Instruct`. That's the laptop folder the run loaded the base from. **The file is left exactly as it was produced**, because its sha256 (`11e460712a1fc783799e0a3b336b2a94d8b566b86cfc16a51364dd7a3470511f`) is on the record in the run JSON and `adapter/ADAPTER.SHA256`. To use the adapter, point it at the HF id yourself. Either load the base explicitly and attach the adapter:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct", revision="aa8e72537993ba99e69dfaafa59ed015b17504d1")
tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct", revision="aa8e72537993ba99e69dfaafa59ed015b17504d1")
model = PeftModel.from_pretrained(base, "bluebird-llm/adapter")
```

or edit a *copy* of `adapter_config.json` to set `base_model_name_or_path` to `Qwen/Qwen2.5-3B-Instruct`.

## Adapter
- LoRA r=16, alpha 32, dropout 0.05. Seven target modules: `q_proj k_proj v_proj o_proj gate_proj up_proj down_proj`. PEFT 0.21.2.
- `adapter/adapter_model.safetensors`: 119,801,528 bytes, sha256 `3b4166836c840e4e1661e030aad42e0c0c00c31b01aede65be98520cf007112d`. Stored in Git LFS.
- `adapter/ADAPTER.SHA256`: the recorded shas. Its own sha256, `35589c33dcc605024b44f6cadecae002998ffff4ecb75a7c52d5432f2988251b`, is the value `score.py --expect_adapter_sha` uses.
- `adapter/PEFT-AUTOGEN-README.md`: the empty model card PEFT generates automatically, renamed.

## How to reproduce
### Environment (from `train/evidence/train-bluebird-v1.0-e2.json`)
torch 2.11.0+cu128, CUDA 12.8, bitsandbytes 0.50.2, transformers 5.22.2, peft 0.21.2. The run used a single 8 GB-class laptop GPU on Windows, and its peak allocation was 6,238,254,080 B.

### Training
**The exact training command line was not recorded in this pack.** The laptop logs that held it were not available for this push. The run JSON records these parameters: tag `bluebird-v1.0-e2`, epochs 2, accum 16, seq 1536, lr 0.0002, 6,273 rows (`rows_sha256` `b947c1be6468a0edb60ab09ece28909a664462178d079c38bc19fa62f7860106`), and 786 steps. Defaults are in `train/train.py`, including `--save_every 50`, `--keep_ckpts 2` and `--peak_limit 7.0e9`. A command consistent with those recorded parameters, **reconstructed rather than recorded**, would be:

```
python train/train.py --model <path or HF snapshot of Qwen/Qwen2.5-3B-Instruct> --rows train/train_rows.jsonl \
  --out_dir <out> --tag bluebird-v1.0-e2 --epochs 2 --seq 1536 --accum 16 --lr 2e-4
```

`train.py` checks `train_rows.jsonl` (and itself) against `train/TRAIN.SHA256` and the token counts against the rows, and it aborts on any mismatch. Step logs, stdout/stderr and `gpu.csv` are in `train/evidence/`. The pre-run fit probe (Qwen2.5-3B vs Phi-3.5-mini) is in `train/fit-probe/`.

### Eval (harness `eval/v0.5/`, 3,569 synthetic rows, `eval_rows.jsonl` sha256 `dd3fc66d50373f123ce4f76602658794a438f6250c0953e8fffa7c84934db899`)
`eval.py --adapter` expects a `final-adapter` directory with `ADAPTER.SHA256` in its parent (it checks `final-adapter/<file>` against that manifest). This repo stores the adapter flat in `adapter/`, so before running T, copy `adapter/adapter_config.json` and `adapter/adapter_model.safetensors` into `<work>/adapter/final-adapter/`, copy `adapter/ADAPTER.SHA256` into `<work>/adapter/`, and pass `--adapter <work>/adapter/final-adapter`.

`eval.py` refuses to run unless `--expect_manifest_sha` equals the sha256 of `RUN-INPUTS.SHA256` (RUN PIN `0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d`). Generic forms, using the flags defined in `eval/v0.5/eval.py`:

```
# T (fine-tuned)
python -B eval/v0.5/eval.py --model <Qwen2.5-3B-Instruct> --adapter <work>/adapter/final-adapter --rows eval/v0.5/eval_rows.jsonl \
  --expect_manifest_sha 0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d --out_dir out-T --tag bluebird-v1.0-e2 --pin_transformers 5.22.2
# S (same base, few-shot, no adapter); r03 ran S at --batch 4 (route A, results/r03/REDO-S-route-A.md)
python -B eval/v0.5/eval.py --model <Qwen2.5-3B-Instruct> --mode fewshot --fewshot eval/v0.5/fewshot.json --rows eval/v0.5/eval_rows.jsonl \
  --expect_manifest_sha 0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d --out_dir out-S-b4 --tag qwen25-3b-base-fs --batch 4 --pin_transformers 5.22.2
```

The actual laptop launch lines for the JSON-fix rerun are recorded verbatim in `eval/jsonfix-v0.0/evidence/ps-blocks-jf/` (for example `09-J6.ps1`: `--max_new_tokens 256 --constraint json-slot`, RUN PIN `c5db63e4a0194582245692c73ef7333297bf27dc46dd298ce55f98fa58903871`).

### Scoring
Flags, as the tests and `eval/v0.5/sim/stub_harness.py` call it: `score.py --rows <eval_rows.jsonl> --expect_score_manifest_sha 8c4b3042ba5abf0134b9d0075170ec55585e41092e60e51f411642b59b59bd1e --expect_run_manifest_sha 0769b8611cc9882f50fbd95ed81c4d0adbc35946ec7c6a187cb30a9802d8866d --expect_adapter_sha 35589c33dcc605024b44f6cadecae002998ffff4ecb75a7c52d5432f2988251b --pred T=<out-T/predictions-*.jsonl> --pred S=<out-S-b4/predictions-*.jsonl> --primary T --baseline S --out <dir>`.

`score.py` (sha256 `a4d7a3746e17549ba5e21965df3dcad916758faecaf2425dfaebdda99d424045`, which matches `eval/v0.5/SCORE-INPUTS.SHA256` and `EVAL-INPUTS.SHA256`) was not in the original source pack. It was added afterwards from the box eval stage `littleblue-eval-v0.5`, on Matt Kelly's ruling (card t581s2093), and its line was added to `SHA256SUMS`.

## Eval results (verbatim from the record)
From `results/r03/score/REPORT.md` (sha256 `eecf22aad959fb80df64c40a87a01abf7bcff31fba92c82c5033a4fc6dfed4e5`) and `results/r03/OWNER-OVERRIDE-T-PASS.md`:

- Scorer verdict for T: **DEGENERATE** (strict). The format gate failed, because 11 of 2090 test outputs were not strict-valid.
- **PASS by owner override, certified by Matt on card t391s1356, 5:02 AM PT 2026-11-16.**
- T: correct_all 0.7459 [0.7273, 0.7641]; valid JSON 0.9947; refusal F1 0.9268.
- Baseline S (the same base model, few-shot, no fine-tune): correct_all 0.0278, valid JSON 0.255.
- Paired T−S answer_value_match: +0.6873 [0.6651, 0.7084], discordant 1141 / 0, McNemar p ~ 0.
- No memorisation evidence (memorisation test did not fire: n 577, effect 0.0, p 1.0).

JSON-fix rerun (`results/jf00/REPORT-jf.md`, constrained json-slot decoding, max_new_tokens 256): G-F 2090/2090 PASS, accuracy unchanged at 1559/2090 = 0.7459, strict verdict **INCONCLUSIVE**. This is a reported result, not a re-certification. It measures the model **plus** the constrained decoder.

Read `REPORT.md` for every bar, the probe results and the conditions behind the false-alarm figure.

## Layout
- `adapter/`: the final LoRA adapter (safetensors in Git LFS) and its config and shas.
- `train/`: `train.py`, `build_train_rows.py`, `measure_rows.py`, `TRAIN.SHA256`, `train_rows.jsonl` (6,273 synthetic rows), `evidence/` (run JSON, step log, stdout/stderr, gpu.csv), and `fit-probe/`.
- `eval/v0.5/`: the pinned eval harness, rows, tests, and mutation and simulation evidence. `tests/fixtures/model/` holds only the Qwen tokenizer and generation config (no weights). `tests/fixtures/adapter/` holds a tiny, randomly initialised LoRA (19,848 B, r=4) that `tests/fixtures/mkadapter.py` built on a 2-layer random Qwen2 config. It is a test fixture, not derived from any Qwen weights.
- `eval/jsonfix-v0.0/`: the JSON-slot constrained-decoding fix harness. Its `eval_rows.jsonl` is byte-identical to v0.5's, so it is left out.
- `eval/route-a-evidence/v0.6`, `v0.7`: baseline-abort analysis tools and evidence.
- `results/r03/`: run r03 (T and S outputs, scoring, result note, owner override, route-A redo, JSON-fix plan). `results/jf00/`: the JSON-fix T rerun and its re-score. `results/records/`: BIA 562 class report v2, HOWTO, class-pack index.
- `SHA256SUMS`: sha256 of every other file in this folder (206 lines as packed, plus `eval/v0.5/score.py` added later; see Scoring). Run `sha256sum -c bluebird-llm/SHA256SUMS` from the repo root. README.md and LICENSE-NOTES.md were written after packing, so they are not listed.

## Git LFS manifest
| Path | Bytes | sha256 |
|---|---|---|
| `bluebird-llm/adapter/adapter_model.safetensors` | 119,801,528 | `3b4166836c840e4e1661e030aad42e0c0c00c31b01aede65be98520cf007112d` |

It is the only LFS file. Run `git lfs install` before cloning, or `git lfs pull` afterwards, to get the real weights instead of the pointer.

## License
The base model license is quoted, with its attribution requirement, in [LICENSE-NOTES.md](LICENSE-NOTES.md). The adapter is a derivative of Qwen2.5-3B-Instruct and is distributed under the base model's terms. **The license for the code in this folder is still to be decided (TBD by Matt Kelly). No code license is granted yet.**
