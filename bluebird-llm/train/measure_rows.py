# Box-only measurement for ORDER-bluebird-full-run@0.0. Train split only. Reads no test rows except ids/system ids for the disjointness check.
import json, glob, os, statistics as st, collections
from tokenizers import Tokenizer
G = "/workspace/littleblue-v02g/repo/gen/out"; R = f"{G}/train"; SEQ = 1536
tk = Tokenizer.from_file("/workspace/littleblue-fullrun/tok/tokenizer.json")
n = lambda s: len(tk.encode(s, add_special_tokens=False).ids)
leaf = {}
for f in glob.glob(f"{R}/leaves/CL-*.md"):
    t = open(f).read(); body = t.split("\n---\n", 1)[1].strip() if "\n---\n" in t else t
    leaf[os.path.basename(f)[3:-3]] = body
pleaf = {}
for f in glob.glob(f"{R}/leaves/P-*.md"):
    t = open(f).read(); body = t.split("\n---\n", 1)[1].strip() if "\n---\n" in t else t
    pleaf[os.path.basename(f)[2:-3]] = body
SYS = "Answer from the contract text only. Return JSON {answer, spans}; no raw digits in answer."
REF = json.dumps({"answer": "not in the contracts", "spans": {}})
qa = [json.loads(l) for l in open(f"{R}/qa.jsonl")]
te = [json.loads(l) for l in open(f"{G}/test/qa.jsonl")]
print("train", len(qa), "test", len(te))
print("qa_id overlap", len({q["qa_id"] for q in qa} & {q["qa_id"] for q in te}))
print("system overlap", len({q["system_id"] for q in qa} & {q["system_id"] for q in te}), "train systems", len({q["system_id"] for q in qa}), "test systems", len({q["system_id"] for q in te}))
print("doc overlap", len({q["doc_id"] for q in qa} & {q["doc_id"] for q in te}))
print("families train", collections.Counter(q["family"] for q in qa), "test", collections.Counter(q["family"] for q in te))
print("answer_type train", collections.Counter(q["answer_type"] for q in qa))
print("synthetic all", all(q["synthetic"] for q in qa))
pre_fix = lambda user: f"<|im_start|>system\n{SYS}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
stats = collections.Counter(); lens = []; anslen = []; ctxfull = []
for q in qa:
    doc = q["doc_id"]; keys = sorted(k for k in leaf if k.startswith(doc + "-"))
    if q.get("source_anchor"):
        adoc, anc = q["source_anchor"].split("#"); ak = f"{adoc}-{anc}"
        if ak in leaf: order = [ak] + [k for k in keys if k != ak]
        elif adoc in pleaf:
            leaf["P:" + adoc] = pleaf[adoc]; order = ["P:" + adoc] + keys; stats["anchor_in_proposal_leaf"] += 1
            if not all(v["text"] in pleaf[adoc] for v in q["spans"].values()): stats["proposal_span_not_verbatim"] += 1
        else: stats["anchor_missing_leaf"] += 1; continue
        ans = json.dumps({"answer": q["answer"], "spans": q["spans"]}) + "<|im_end|>"; ans = json.dumps({"answer": q["answer"], "spans": q["spans"]}) + "<|im_end|>"
        stats["anchored"] += 1
    else:
        order = keys; ans = REF + "<|im_end|>"; stats["unanswerable"] += 1
        if not keys: stats["unans_no_doc_leaves"] += 1
    a = n(ans); anslen.append(a); keep = SEQ - a
    full = n(pre_fix(f"Question: {q['question']}\n\nContract text:\n" + "\n\n".join(leaf[k] for k in order)))
    ctxfull.append(full)
    if full <= keep: stats["fits_whole_doc"] += 1; lens.append(full + a); continue
    stats["clauses_dropped"] += 1
    ctx = leaf[order[0]] if order else ""; first = n(pre_fix(f"Question: {q['question']}\n\nContract text:\n{ctx}"))
    if first > keep: stats["first_clause_cut"] += 1
    lens.append(SEQ)  # upper bound: filled to SEQ by whole clauses (<=SEQ)
print(dict(stats))
print("answer tokens mean/max", round(st.mean(anslen),1), max(anslen))
print("whole-doc prompt tokens p50/p90/max", st.median(ctxfull), sorted(ctxfull)[int(.9*len(ctxfull))], max(ctxfull))
print("row tokens (<=1536 upper bound) mean", round(st.mean(lens),1), "share at cap", round(sum(l==SEQ for l in lens)/len(lens),4))
