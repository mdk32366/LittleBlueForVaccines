# ORDER-bluebird-full-run@0.1 Appendix B2. DRAFT, NOT EXECUTED ON GPU. Derived from fit.py (sha256 6386cb84...). Laptop GATE 1 venv only.
# Runs only under Matt's own GO card for the full run. @0.1 applies Kaylee's review (resume determinism + guards).
# Exit codes: 2 nan/inf loss, 3 peak_alloc > limit, 4 tokenizer mismatch (count or ids hash), 5 CUDA OOM, 6 sha mismatch vs TRAIN.SHA256,
#             7 resume config mismatch, 8 non-finite grad norm, 9 row longer than --seq.
import argparse, json, time, math, os, glob, hashlib, shutil, random, sys, torch, transformers, peft, bitsandbytes as bnb
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, set_peft_model_state_dict
from safetensors.torch import load_file
a = argparse.ArgumentParser()
for k in ("--model", "--rows", "--out_dir", "--tag"): a.add_argument(k, required=True)
a.add_argument("--epochs", type=int, required=True); a.add_argument("--seq", type=int, default=1536); a.add_argument("--accum", type=int, default=16)
a.add_argument("--lr", type=float, default=2e-4); a.add_argument("--save_every", type=int, default=50); a.add_argument("--keep_ckpts", type=int, default=2)
a.add_argument("--peak_limit", type=float, default=7.0e9); a.add_argument("--manifest", default=None, help="default: TRAIN.SHA256 next to --rows")
a = a.parse_args(); torch.manual_seed(562); random.seed(562)          # seed before LoRA init (fresh runs reproducible)
os.makedirs(a.out_dir, exist_ok=True); CK = os.path.join(a.out_dir, "ckpt"); AB = os.path.join(a.out_dir, "ABORT.json")
LOGP = os.path.join(a.out_dir, f"steps-{a.tag}.jsonl")
def sha(p):
    h = hashlib.sha256(); f = open(p, "rb")
    for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
def abort(code, why):
    json.dump({"tag": a.tag, "abort": why, "exit": code, "time": time.strftime("%Y-%m-%d %H:%M:%S")}, open(AB, "w")); print("ABORT", why, flush=True); sys.exit(code)
def save_adapter(d):                                                  # save, then canonicalise adapter_config.json (peft writes target_modules
    m.save_pretrained(d); cp = os.path.join(d, "adapter_config.json")  # from a set, so its order varies with PYTHONHASHSEED)
    c = json.load(open(cp))
    if isinstance(c.get("target_modules"), list): c["target_modules"] = sorted(c["target_modules"])
    json.dump(c, open(cp, "w"), indent=2, sort_keys=True)
def manifest(d):                                                       # adapter files except README.md (peft writes a non-deterministic card)
    return {f: sha(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f != "README.md"}
# 1. rows file must match TRAIN.SHA256 (and so must this script if it is listed there)
mp = a.manifest or os.path.join(os.path.dirname(os.path.abspath(a.rows)), "TRAIN.SHA256")
want = {ln.split()[1].lstrip("*"): ln.split()[0] for ln in open(mp) if ln.strip()}
rows_sha = sha(a.rows)
if want.get(os.path.basename(a.rows)) != rows_sha: abort(6, f"rows sha256 {rows_sha} != manifest {want.get(os.path.basename(a.rows))}")
me = os.path.basename(os.path.abspath(sys.argv[0]))
if me in want and want[me] != sha(os.path.abspath(sys.argv[0])): abort(6, f"{me} sha256 != manifest")
# 2. tokenize; laptop ids must equal the box builder's ids (count and sha256 of the id list)
tok = AutoTokenizer.from_pretrained(a.model)
rows = [json.loads(l) for l in open(a.rows, encoding="utf-8")]
data = []
for r in rows:
    pre = tok.apply_chat_template([{"role": "system", "content": r["system"]}, {"role": "user", "content": r["user"]}],
                                  tokenize=True, add_generation_prompt=True, return_dict=False)
    ans = tok(r["assistant"] + tok.eos_token, add_special_tokens=False)["input_ids"]
    ids = pre + ans
    if len(ids) != r["tokens"]: abort(4, f"tokenizer_mismatch count {r['qa_id']} {len(ids)}!={r['tokens']}")
    if hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest() != r["ids_sha256"]: abort(4, f"tokenizer_mismatch ids {r['qa_id']}")
    if len(ids) > a.seq: abort(9, f"row_too_long {r['qa_id']} {len(ids)} > {a.seq}")
    data.append((ids, [-100] * len(pre) + ans))          # completion-only loss
N = len(data); spe = math.ceil(N / a.accum); total = spe * a.epochs
CFG = {"epochs": a.epochs, "accum": a.accum, "seq": a.seq, "lr": a.lr, "rows_sha256": rows_sha, "rows": N}
try:
    q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    m = AutoModelForCausalLM.from_pretrained(a.model, quantization_config=q, attn_implementation="sdpa", dtype=torch.bfloat16, device_map={"": 0})
    m = prepare_model_for_kbit_training(m, use_gradient_checkpointing=True)
    m = get_peft_model(m, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear", task_type="CAUSAL_LM"))
    params = [p for p in m.parameters() if p.requires_grad]
    opt = bnb.optim.PagedAdamW8bit(params, lr=a.lr)
    sched = transformers.get_cosine_schedule_with_warmup(opt, 0, total)
    done = 0; peak_prev = 0
    good = sorted(d for d in glob.glob(os.path.join(CK, "step-*")) if os.path.exists(os.path.join(d, "COMPLETE")))
    if good:                                               # resume from the last complete checkpoint
        d = good[-1]; st = torch.load(os.path.join(d, "state.pt"), weights_only=False)
        if st.get("cfg") != CFG: abort(7, f"resume config mismatch: checkpoint {st.get('cfg')} vs now {CFG}")
        if json.load(open(os.path.join(d, "COMPLETE"))) != manifest(os.path.join(d, "adapter")): abort(6, f"checkpoint {d} adapter hash != COMPLETE")
        set_peft_model_state_dict(m, load_file(os.path.join(d, "adapter", "adapter_model.safetensors")))
        opt.load_state_dict(st["opt"]); sched.load_state_dict(st["sched"]); done = st["step"]; peak_prev = st.get("peak_alloc", 0)
        random.setstate(st["py_rng"]); torch.set_rng_state(st["torch_rng"])
        if st.get("cuda_rng") is not None and torch.cuda.is_available(): torch.cuda.set_rng_state_all(st["cuda_rng"])
        if os.path.exists(LOGP):                           # truncate the step log to the checkpoint step
            keep = [l for l in open(LOGP) if l.strip() and json.loads(l)["step"] <= done]; open(LOGP, "w").writelines(keep)
        if os.path.exists(AB): os.replace(AB, os.path.join(a.out_dir, f"ABORT-cleared-{time.strftime('%Y%m%d-%H%M%S')}.json"))
        print("RESUME", d, done, flush=True)
    elif os.path.exists(LOGP) or os.path.exists(AB): abort(7, "out_dir has a step log or ABORT.json but no complete checkpoint; use a fresh out_dir")
    order = lambda ep: random.Random(562 + ep).sample(range(N), N)    # fixed per-epoch order, so resume replays exactly
    log = open(LOGP, "a"); torch.cuda.reset_peak_memory_stats(); m.train()
    for step in range(done, total):
        ep, k = divmod(step, spe); idx = order(ep)[k * a.accum:(k + 1) * a.accum]; t0 = time.time(); tot = 0.0; ntok = 0
        for i in idx:
            ids, lab = data[i]
            loss = m(input_ids=torch.tensor([ids], device="cuda"), labels=torch.tensor([lab], device="cuda")).loss / len(idx)
            loss.backward(); tot += loss.item(); ntok += len(ids)
        if math.isnan(tot) or math.isinf(tot): abort(2, f"nan_loss step {step + 1}")
        gn = torch.linalg.vector_norm(torch.stack([p.grad.detach().float().norm() for p in params if p.grad is not None])).item()
        if not math.isfinite(gn): abort(8, f"grad_norm {gn} step {step + 1}")
        lr_applied = opt.param_groups[0]["lr"]                            # the lr this step's update uses
        opt.step(); sched.step(); opt.zero_grad(set_to_none=True); torch.cuda.synchronize()
        pk = peak_prev = max(torch.cuda.max_memory_allocated(), peak_prev);   # running max, carried across resume
        rs = torch.cuda.max_memory_reserved()
        free, tot_dev = torch.cuda.mem_get_info(); dev_used = tot_dev - free   # device-level (incl. paged optimizer, other processes)
        rec = {"step": step + 1, "epoch": ep + 1, "loss": tot, "grad_norm": gn, "sec": round(time.time() - t0, 2), "tokens": ntok, "lr": lr_applied,
               "peak_alloc": pk, "peak_reserved": rs, "device_used": dev_used}
        log.write(json.dumps(rec) + "\n"); log.flush(); print(rec, flush=True)
        if pk > a.peak_limit: abort(3, f"peak_alloc {pk} > {a.peak_limit} at step {step + 1}")
        if (step + 1) % a.save_every == 0 or step + 1 == total:
            d = os.path.join(CK, f"step-{step + 1:06d}"); save_adapter(os.path.join(d, "adapter"))
            torch.save({"opt": opt.state_dict(), "sched": sched.state_dict(), "step": step + 1, "cfg": CFG, "peak_alloc": pk, "py_rng": random.getstate(),
                        "torch_rng": torch.get_rng_state(), "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None}, os.path.join(d, "state.pt"))
            open(os.path.join(d, "COMPLETE"), "w").write(json.dumps(manifest(os.path.join(d, "adapter"))))
            for old in sorted(glob.glob(os.path.join(CK, "step-*")))[:-a.keep_ckpts]: shutil.rmtree(old)   # keep the last N
    fin = os.path.join(a.out_dir, "final-adapter"); save_adapter(fin)
except torch.cuda.OutOfMemoryError as e:
    abort(5, f"cuda_oom {str(e)[:200]}")
S = manifest(fin)
open(os.path.join(a.out_dir, "ADAPTER.SHA256"), "w").write("".join(f"{v}  final-adapter/{k}\n" for k, v in S.items()))
json.dump({"tag": a.tag, "model": a.model, **CFG, "steps": total, "peak_alloc_bytes": max(torch.cuda.max_memory_allocated(), peak_prev),
           "peak_reserved_bytes": torch.cuda.max_memory_reserved(), "adapter_sha256": S,
           "versions": {"torch": torch.__version__, "cuda": torch.version.cuda, "bitsandbytes": bnb.__version__, "transformers": transformers.__version__, "peft": peft.__version__}},
          open(os.path.join(a.out_dir, f"train-{a.tag}.json"), "w"), indent=1)
print("TRAIN_DONE", a.tag, total, flush=True)
# No merge, no GGUF, no upload here. Merge + GGUF + Q4_K_M is a separate step with its own GO (Order §e).
