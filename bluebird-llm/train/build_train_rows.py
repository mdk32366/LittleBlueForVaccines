# ORDER-bluebird-full-run@0.1 Appendix B1. Box only. GATE 2 TRAIN split only (family A); test/ is never opened.
# Deterministic. Token counts and token-id hashes use the pinned Qwen2.5-3B-Instruct tokenizer (rev aa8e7253...).
# @0.1: clauses in NUMERIC section order; documents in doc-id order; anchor clause stays in its natural position;
#       over-budget rows drop the clauses farthest from any required (anchor/span) clause first; required clauses never drop.
import json, glob, os, random, re, collections, sys, hashlib
from tokenizers import Tokenizer
from jinja2 import Environment
R = "/workspace/littleblue-v02g/repo/gen/out/train"; SEQ = 1536; OUT = os.environ.get("B1_OUT", "/workspace/littleblue-fullrun/train_rows.jsonl")
T = "/workspace/littleblue-fullrun/tok"; tk = Tokenizer.from_file(f"{T}/tokenizer.json")
tpl = Environment().from_string(json.load(open(f"{T}/tokenizer_config.json"))["chat_template"])
enc = lambda s: tk.encode(s, add_special_tokens=False).ids
SYS = "Answer from the contract text only. Return JSON {answer, spans}; no raw digits in answer."
REFUSAL = {"answer": "not in the contracts", "spans": {}}
def body(f):
    t = open(f).read(); return t.split("\n---\n", 1)[1].strip() if "\n---\n" in t else t
cl = {os.path.basename(f)[3:-3]: body(f) for f in glob.glob(f"{R}/leaves/CL-*.md")}
pl = {os.path.basename(f)[2:-3]: body(f) for f in glob.glob(f"{R}/leaves/P-*.md")}
def nat(sec): return tuple(int(p) for p in sec.split("."))                   # "11.1" -> (11, 1); all sections are numeric
doc_secs = collections.defaultdict(list)
for k in cl: d, s = k.rsplit("-", 1); doc_secs[d].append(s)
for d in doc_secs: doc_secs[d].sort(key=nat)
def prompt(user): return tpl.render(messages=[{"role": "system", "content": SYS}, {"role": "user", "content": user}], add_generation_prompt=True)
def user_of(q, texts): return f"Question: {q['question']}\n\nContract text:\n" + "\n\n".join(texts)
qa = [json.loads(l) for l in open(f"{R}/qa.jsonl")]
assert all(q["synthetic"] and q["family"] == "A" for q in qa)
random.seed(562); random.shuffle(qa)
st = collections.Counter(); pos = collections.Counter(); out = open(OUT, "w"); lens = []
for q in qa:
    doc = q["doc_id"]; req = set()                                            # units: (doc, sec) for clauses, (doc, None) for a whole P-leaf
    units = {(doc, s) for s in doc_secs.get(doc, [])}
    if q.get("source_anchor"):
        need = list(dict.fromkeys([q["source_anchor"]] + [v["anchor"] for v in q["spans"].values()]))
        for an in need:
            adoc, sec = an.split("#")
            if f"{adoc}-{sec}" in cl: u = (adoc, sec)
            elif adoc in pl: u = (adoc, None); st["anchor_proposal_leaf"] += 1
            else: sys.exit(f"UNRESOLVED anchor {q['qa_id']} {an}")
            req.add(u); units.add(u)
        if len(need) > 1: st["rows_multi_anchor"] += 1
        for v in q["spans"].values():
            adoc, sec = v["anchor"].split("#"); src = cl.get(f"{adoc}-{sec}") or pl.get(adoc); assert v["text"] in src, q["qa_id"]
        sa = q["source_anchor"].split("#"); src_unit = (sa[0], sa[1]) if f"{sa[0]}-{sa[1]}" in cl else (sa[0], None)
        target = {"answer": q["answer"], "spans": q["spans"]}
    else:
        target = REFUSAL; src_unit = None; st["unanswerable"] += 1
    order = sorted(units, key=lambda u: (u[0], nat(u[1]) if u[1] else ()))  # doc-id order, then numeric section order
    text = lambda u: cl[f"{u[0]}-{u[1]}"] if u[1] else pl[u[0]]
    ans = json.dumps(target); aids = enc(ans + "<|im_end|>"); keep = SEQ - len(aids)
    rpos = [i for i, u in enumerate(order) if u in req]
    # drop priority: farthest from the nearest required clause first (ties: later position first); no anchor -> drop from the tail
    dist = lambda i: min(abs(i - r) for r in rpos) if rpos else -(-i)
    cand = sorted((i for i in range(len(order)) if order[i] not in req), key=lambda i: (dist(i), i), reverse=True)
    kept = set(range(len(order))); dropped = 0
    ctok = {i: len(enc(text(order[i]) + "\n\n")) for i in kept}
    over = lambda: sum(ctok[i] for i in kept) + len(enc(prompt(user_of(q, [])))) - keep
    ci = iter(cand)
    while over() > 0:                                                         # estimate with per-clause counts, then verify exactly
        i = next(ci, None)
        if i is None: break
        kept.discard(i); dropped += 1
    while True:
        pids = enc(prompt(user_of(q, [text(order[i]) for i in sorted(kept)])))
        if len(pids) <= keep: break
        i = next(ci, None); assert i is not None, f"required clauses exceed budget {q['qa_id']}"
        kept.discard(i); dropped += 1
    assert all(order.index(u) in kept for u in req)                           # anchors and span clauses never drop
    st["rows_clauses_dropped" if dropped else "rows_whole_doc"] += 1; st["clauses_dropped_total"] += dropped
    seq = [order[i] for i in sorted(kept)]
    if src_unit is not None:
        p = seq.index(src_unit); n = len(seq)
        pos["first" if p == 0 else ("last" if p == n - 1 else "middle")] += 1
        if n == 1: pos["only_clause"] += 1
    ids = pids + aids; n = len(ids); assert n <= SEQ; lens.append(n)
    out.write(json.dumps({"system": SYS, "user": user_of(q, [text(u) for u in seq]), "assistant": ans, "qa_id": q["qa_id"],
                          "answerable": bool(q.get("source_anchor")), "tokens": n,
                          "ids_sha256": hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest()}) + "\n")
out.close(); lens.sort(); A = sum(pos[k] for k in ("first", "middle", "last"))
print(json.dumps({"rows": len(lens), **st, "tokens_sum": sum(lens), "tokens_mean": round(sum(lens) / len(lens), 1),
                  "p50": lens[len(lens) // 2], "p90": lens[int(.9 * len(lens))], "max": lens[-1], "min": lens[0],
                  "anchor_position": dict(pos), "anchor_first_pct": round(100 * pos["first"] / A, 2), "anchored_rows": A}))
