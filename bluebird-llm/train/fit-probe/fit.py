import argparse, json, time, math, torch, transformers, peft, bitsandbytes as bnb, trl
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
a = argparse.ArgumentParser()
for k in ("--model", "--tag", "--rows", "--out"): a.add_argument(k)
a.add_argument("--seq", type=int, default=1536); a.add_argument("--steps", type=int, default=20); a.add_argument("--accum", type=int, default=16)
a = a.parse_args(); torch.manual_seed(562)
tok = AutoTokenizer.from_pretrained(a.model)
rows = [json.loads(l) for l in open(a.rows, encoding="utf-8")][: a.steps * a.accum]
data = []
for r in rows:
    ans = tok(r["assistant"] + (tok.eos_token or ""), add_special_tokens=False)["input_ids"]
    pre = tok.apply_chat_template([{"role": "system", "content": r["system"]}, {"role": "user", "content": r["user"]}],
                                  tokenize=True, add_generation_prompt=True, return_dict=False)
    keep = a.seq - len(ans); assert keep > 256 and len(pre) >= keep, (len(pre), keep)
    ids = pre[:keep] + ans                       # context truncated, answer kept: exactly seq tokens
    assert len(ids) == a.seq; data.append(ids)
q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
m = AutoModelForCausalLM.from_pretrained(a.model, quantization_config=q, attn_implementation="sdpa", dtype=torch.bfloat16, device_map={"": 0})
base_alloc = torch.cuda.memory_allocated()
m = prepare_model_for_kbit_training(m, use_gradient_checkpointing=True)
m = get_peft_model(m, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear", task_type="CAUSAL_LM"))
opt = bnb.optim.PagedAdamW8bit([p for p in m.parameters() if p.requires_grad], lr=2e-4)
sched = transformers.get_cosine_schedule_with_warmup(opt, 0, a.steps)
torch.cuda.reset_peak_memory_stats(); m.train(); log = []; i = 0; nan = False
for step in range(a.steps):
    t0 = time.time(); tot = 0.0
    for _ in range(a.accum):
        x = torch.tensor([data[i]], device="cuda"); i += 1
        loss = m(input_ids=x, labels=x).loss / a.accum; loss.backward(); tot += loss.item()
    opt.step(); sched.step(); opt.zero_grad(set_to_none=True); torch.cuda.synchronize()
    nan |= math.isnan(tot); log.append({"step": step + 1, "loss": tot, "sec": round(time.time() - t0, 2)}); print(log[-1], flush=True)
pa, pr = torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved()
res = {"tag": a.tag, "model": a.model, "seq": a.seq, "steps": a.steps, "accum": a.accum, "rows": len(data),
       "rows_len_min": min(map(len, data)), "rows_len_max": max(map(len, data)), "base_alloc_bytes": base_alloc,
       "peak_alloc_bytes": pa, "peak_reserved_bytes": pr, "peak_alloc_GB": pa / 1e9, "peak_alloc_GiB": pa / 2**30,
       "nan_loss": nan, "log": log, "pass_1e9": pa <= 7.0e9 and not nan and len(log) == a.steps,
       "ambiguity_band": 7.0e9 < pa <= 7.0 * 2**30,
       "versions": {"torch": torch.__version__, "cuda": torch.version.cuda, "cap": torch.cuda.get_device_capability(),
                    "gpu": torch.cuda.get_device_name(0), "bitsandbytes": bnb.__version__, "transformers": transformers.__version__,
                    "peft": peft.__version__, "trl": trl.__version__}}
json.dump(res, open(a.out, "w"), indent=1); print("FIT", a.tag, "PASS" if res["pass_1e9"] else "FAIL", pa)
# No save_pretrained / no checkpoint: nothing here can become Bluebird.
