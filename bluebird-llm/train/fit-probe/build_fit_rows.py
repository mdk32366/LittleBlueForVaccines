import json, glob, os, random, re
R = "/workspace/littleblue-v02g/repo/gen/out/train"; random.seed(562)
leaf = {}
for f in glob.glob(f"{R}/leaves/CL-*.md"):
    t = open(f).read(); body = t.split("\n---\n", 1)[1].strip() if "\n---\n" in t else t
    leaf[os.path.basename(f)[3:-3]] = body          # id like SYN-SYNCP000001-EXH1-1
qa = [json.loads(l) for l in open(f"{R}/qa.jsonl")]; assert all(q["synthetic"] for q in qa)
random.shuffle(qa); out = open("/workspace/littleblue-fit/fit_rows_src.jsonl", "w"); n = 0
SYS = "Answer from the contract text only. Return JSON {answer, spans}; no raw digits in answer."
for q in qa:
    if not q.get("source_anchor"): continue   # unanswerable rows have no anchor
    doc = q["doc_id"]; anc = q["source_anchor"].split("#")[1]; own = leaf.get(f"{doc}-{anc}")
    if not own: continue
    rest = [v for k, v in sorted(leaf.items()) if k.startswith(doc + "-") and k != f"{doc}-{anc}"]
    ctx = own; i = 0
    while len(ctx) < 9000 and i < len(rest): ctx += "\n\n" + rest[i]; i += 1
    if len(ctx) < 9000: continue
    out.write(json.dumps({"system": SYS, "user": f"Question: {q['question']}\n\nContract text:\n{ctx}",
                          "assistant": json.dumps({"answer": q["answer"], "spans": q["spans"]}), "qa_id": q["qa_id"]}) + "\n"); n += 1
    if n == 320: break
assert n == 320, n
