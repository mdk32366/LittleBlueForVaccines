# (Box suite @0.1: Kaylee's review shim evidence/39-shim_eval.py, adopted per ruling 7; additions marked @0.1.)
# CPU shim for eval.py's GPU branch: runs an UNMODIFIED copy of eval.py (sha printed) with a tiny random Qwen2 (fixed seed) and the pinned local tokenizer.
# Stand-ins: bitsandbytes module (fake), BitsAndBytesConfig ignored, device "cuda" -> cpu, torch.cuda.{is_available,mem_get_info,reset_peak_memory_stats,
# max_memory_allocated,max_memory_reserved,get_device_name}. The tiny model carries Qwen2.5-3B-Instruct's SHIPPED generation_config (sampling + rep 1.05).
# Env: SHIM_CUDA=0 (no CUDA), SHIM_FREE (bytes free), SHIM_PEAK, SHIM_PEAK_AT (batch index from which PEAK_HI is reported), SHIM_OOM_LOAD=1, SHIM_OOM_AT (batch),
#      SHIM_KILL_AT (hard kill after N batches), SHIM_STOP_AT (force <|im_end|> at generated step k), SHIM_SPECIAL=1 (force <|im_start|> at step 1),
#      SHIM_LOG (jsonl: merged generation config, logits processors, batch ids), SHIM_RAISE_AT (non-OOM RuntimeError at batch).
#      @0.1: SHIM_TAMPER_MERGED=1 (generate() merges repetition_penalty 1.05 + sampling, as an unpatched shipped config would),
#            SHIM_INTERRUPT_AT (KeyboardInterrupt at batch), SHIM_TF_VERSION (reported transformers.__version__).
import sys, os, types, hashlib, runpy, importlib, json, torch
script = sys.argv[1]; sys.argv = [script] + sys.argv[2:]
print("SHIM_EVAL script sha256", hashlib.sha256(open(script, "rb").read()).hexdigest(), flush=True)
E = lambda k, d="0": os.environ.get(k, d)
bnb = types.ModuleType("bitsandbytes"); bnb.__version__ = "shim"; sys.modules["bitsandbytes"] = bnb
import transformers
for modname in ["peft.import_utils", "peft.tuners.lora.model", "peft.tuners.lora.layer", "peft.utils.other", "peft.tuners.tuners_utils"]:
    mm = importlib.import_module(modname)
    for fn in ["is_bnb_available", "is_bnb_4bit_available"]:
        if hasattr(mm, fn): setattr(mm, fn, lambda: False)
from transformers import Qwen2Config, Qwen2ForCausalLM, GenerationConfig
transformers.BitsAndBytesConfig = lambda **k: ("shim-bnb", k)
LOG = E("SHIM_LOG", "")
def log(d):
    if LOG: open(LOG, "a").write(json.dumps(d) + "\n")
st = {"batch": 0}
def tiny(path, *a, **k):
    if E("SHIM_OOM_LOAD") == "1": raise torch.cuda.OutOfMemoryError("SHIM OOM during model load")
    with torch.random.fork_rng():
        torch.manual_seed(1234)
        m = Qwen2ForCausalLM(Qwen2Config(vocab_size=151936, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1,
                                         max_position_embeddings=4096, tie_word_embeddings=True, bos_token_id=151643, eos_token_id=151645))
    m.generation_config = GenerationConfig.from_pretrained(path)          # Qwen's shipped defaults
    log({"loaded_generation_config": m.generation_config.to_dict()})
    of = m.forward; gen = {"step": 0}
    def fwd(*x, **y):
        out = of(*x, **y)
        pk = y.get("past_key_values")
        is_prefill = y["input_ids"].shape[1] > 1 or gen.get("new", True)
        if y["input_ids"].shape[1] > 1: gen["step"] = 0
        else: gen["step"] += 1
        s = gen["step"]
        if E("SHIM_SPECIAL") == "1" and s == 0: out.logits[:, -1, :] = -1e9; out.logits[:, -1, 151644] = 1e9
        if int(E("SHIM_STOP_AT")) and s == int(E("SHIM_STOP_AT")): out.logits[:, -1, :] = -1e9; out.logits[:, -1, 151645] = 1e9
        return out
    m.forward = fwd
    og = m.generate
    return m
transformers.AutoModelForCausalLM.from_pretrained = staticmethod(tiny)
# capture the MERGED generation config + the logits processors generate() actually builds
from transformers.generation import utils as gu
_prep = gu.GenerationMixin._prepare_generation_config
def prep(self, *a, **k):
    r = _prep(self, *a, **k); gc = r[0] if isinstance(r, tuple) else r
    if E("SHIM_TAMPER_MERGED") == "1": gc.repetition_penalty = 1.05; gc.do_sample = True; gc.temperature = 0.7; gc.top_p = 0.8; gc.top_k = 20
    log({"merged": {x: getattr(gc, x, None) for x in ("do_sample", "num_beams", "temperature", "top_p", "top_k", "repetition_penalty", "max_new_tokens", "eos_token_id", "pad_token_id")}})
    return r
gu.GenerationMixin._prepare_generation_config = prep
_glp = gu.GenerationMixin._get_logits_processor
def glp(self, *a, **k):
    r = _glp(self, *a, **k); log({"logits_processors": [type(p).__name__ for p in r]}); return r
gu.GenerationMixin._get_logits_processor = glp
_gen = gu.GenerationMixin.generate
def generate(self, *a, **k):
    st["batch"] += 1; b = st["batch"]
    if int(E("SHIM_KILL_AT")) and b == int(E("SHIM_KILL_AT")) + 1: print("SHIM hard kill (os._exit 137) before batch", b, flush=True); os._exit(137)
    if int(E("SHIM_OOM_AT")) and b == int(E("SHIM_OOM_AT")): raise torch.cuda.OutOfMemoryError("SHIM OOM at batch %d" % b)
    if int(E("SHIM_RAISE_AT")) and b == int(E("SHIM_RAISE_AT")): raise RuntimeError("SHIM non-OOM CUDA error at batch %d" % b)
    if int(E("SHIM_INTERRUPT_AT")) and b == int(E("SHIM_INTERRUPT_AT")): raise KeyboardInterrupt()
    ids = k["input_ids"]; log({"batch": b, "shape": list(ids.shape), "pad_left": int((k["attention_mask"] == 0).sum())})
    return _gen(self, *a, **k)
gu.GenerationMixin.generate = generate
_tensor = torch.tensor
def tensor(*a, **k):
    if k.get("device") == "cuda": k["device"] = "cpu"
    return _tensor(*a, **k)
torch.tensor = tensor
torch.cuda.is_available = lambda: E("SHIM_CUDA", "1") == "1"
torch.cuda.mem_get_info = lambda *a, **k: (int(float(E("SHIM_FREE", "7.5e9"))), int(8e9))
torch.cuda.reset_peak_memory_stats = lambda *a, **k: None
torch.cuda.max_memory_allocated = lambda *a, **k: int(float(E("SHIM_PEAK_HI", "9e9"))) if int(E("SHIM_PEAK_AT")) and st["batch"] >= int(E("SHIM_PEAK_AT")) else int(float(E("SHIM_PEAK", "1000")))
torch.cuda.max_memory_reserved = lambda *a, **k: int(float(E("SHIM_PEAK", "1000")))
torch.cuda.get_device_name = lambda *a, **k: "SHIM-CPU"
import peft
_pf = peft.PeftModel.from_pretrained.__func__
def pf(cls, *a, **k):
    old = torch.cuda.is_available; torch.cuda.is_available = lambda: False
    try: return _pf(cls, *a, **k)
    finally: torch.cuda.is_available = old
peft.PeftModel.from_pretrained = classmethod(pf)
if E("SHIM_TF_VERSION", ""): sys.modules["transformers"].__version__ = E("SHIM_TF_VERSION")  # set last, on the module eval.py will import (the lazy module is re-registered during the imports above); @0.1 ruling 8: pretend an unverified transformers (e.g. the laptop's 5.22.2)
runpy.run_path(script, run_name="__main__")
