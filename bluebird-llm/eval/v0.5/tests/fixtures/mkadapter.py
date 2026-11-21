import torch, json, os, hashlib
from transformers import Qwen2Config, Qwen2ForCausalLM
from peft import LoraConfig, get_peft_model
torch.manual_seed(1234)
m = Qwen2ForCausalLM(Qwen2Config(vocab_size=151936, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1, max_position_embeddings=4096, tie_word_embeddings=True))
torch.manual_seed(7)
p = get_peft_model(m, LoraConfig(r=4, lora_alpha=8, target_modules="all-linear", task_type="CAUSAL_LM", init_lora_weights=False))
d = "adapter/final-adapter"; p.save_pretrained(d)
sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
open("adapter/ADAPTER.SHA256", "w").write("".join(f"{sha(os.path.join(d, f))}  final-adapter/{f}\n" for f in sorted(os.listdir(d)) if f != "README.md"))
print(open("adapter/ADAPTER.SHA256").read())
