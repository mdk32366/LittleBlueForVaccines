# Bluebird v1.0 eval rows + memorisation probes @0.1. Box only, CPU, deterministic (seed 562), no model.
# @0.1 (review M7, I1, I2, L3, H2): rn also renames the supplier's brand stems (case-insensitive) and carries leak_terms; cf/ar carry a
# placebo value (another system's gold for the same question type, absent from the prompt) as the control for old-value evidence;
# every probe invariant is checked by probecheck.py BEFORE anything is written; fake names asserted absent from the corpus.
# Reads the GATE 2 TEST split (family B, 2,090 rows; never trained on) and builds prompts exactly as B1
# (build_train_rows.py @0.1) does for train: same system prompt, same user layout, doc-id + numeric section order,
# farthest-from-anchor clause drop. One difference: the prompt budget is SEQ - MAX_NEW (fixed), not SEQ - gold answer length,
# so truncation never depends on the gold answer.
# Probes (each built from test rows, each its own kind): cf counterfactual value, ar anchor removal, sh clause shuffle,
# rn supplier rename, pp question paraphrase outside both template families.
import json, glob, os, random, re, collections, sys, hashlib
from tokenizers import Tokenizer
from jinja2 import Environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evalcore import SYS, REFUSAL, PROMPT_BUDGET, messages, user_of, render, denylist_hit, digits_in_answer
import probecheck as pc
from probecheck import occurs, full_text
def must(problems, what):
    if problems: sys.exit(f"BUILD CHECK FAILED ({what}): {problems[:10]} ... {len(problems)} total")
G = os.environ.get("GEN_OUT", "/workspace/littleblue-v02g/repo/gen/out")
T = os.environ.get("TOK_DIR", "/workspace/littleblue-fullrun/tok")
TRAIN_ROWS = os.environ.get("TRAIN_ROWS", "/workspace/littleblue-fullrun/train_rows.jsonl")
OUT = os.environ.get("EVAL_OUT", os.path.dirname(os.path.abspath(__file__)))
N_PROBE = int(os.environ.get("N_PROBE", "300"))           # rows per probe kind (fewer if the eligible pool is smaller)
TEST_QA_SHA = "260fbce943b5e10373d47a73c78520c2743e7fd85d40dac9c1a8985a911c8f65"   # ORDER full-run §0
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
must(pc.check_sha_pin(f"{G}/test/qa.jsonl", TEST_QA_SHA), "test qa.jsonl sha256 != ORDER §0")
tk = Tokenizer.from_file(f"{T}/tokenizer.json")
tpl = Environment().from_string(json.load(open(f"{T}/tokenizer_config.json"))["chat_template"])
enc = lambda s: tk.encode(s, add_special_tokens=False).ids
def prompt_ids(msgs): return enc(tpl.render(messages=msgs, add_generation_prompt=True))
def body(f):
    t = open(f).read(); return t.split("\n---\n", 1)[1].strip() if "\n---\n" in t else t
R = f"{G}/test"
cl = {os.path.basename(f)[3:-3]: body(f) for f in glob.glob(f"{R}/leaves/CL-*.md")}
pl = {os.path.basename(f)[2:-3]: body(f) for f in glob.glob(f"{R}/leaves/P-*.md")}
def nat(sec): return tuple(int(p) for p in sec.split("."))
doc_secs = collections.defaultdict(list)
for k in cl: d, s = k.rsplit("-", 1); doc_secs[d].append(s)
for d in doc_secs: doc_secs[d].sort(key=nat)
supplier = {}                                              # system_id -> Supplier named in its MSA §1
for f in glob.glob(f"{R}/docs/*-MSA1.md"):
    m = re.search(r'^(\S[^\n]*?) \(hereafter "Supplier"\)', open(f).read(), re.M); assert m, f
    supplier[os.path.basename(f).split("-")[1]] = m.group(1)
qa = [json.loads(l) for l in open(f"{R}/qa.jsonl")]
assert len(qa) == 2090 and all(q["family"] == "B" and q["synthetic"] for q in qa)
train_q = [json.loads(l) for l in open(f"{G}/train/qa.jsonl")]
must(pc.check_system_disjoint({q["system_id"] for q in qa}, {q["system_id"] for q in train_q}), "system overlap train/test")
qa.sort(key=lambda q: q["qa_id"])
# review I2: fake supplier names, their distinctive tokens and the fake brand stems (rn probe) are absent from the whole corpus (train + test
# docs, leaves, qa; train_rows, which hold the few-shot exemplars; system prompt), case-insensitive. Checked in code, before anything is built.
FAKE = ["HALVERN BIOLOGICS", "ORRIN VACCINE CO", "TESSARA PHARMA"]
FAKE_STEMS = ["VORALIX", "QUENTARA", "MIRADEX", "SOLVANTRE", "BRELUXA", "CORVENTI", "DAXOPRA", "FENTAVIX", "GLORIVAX", "HALUNTRA", "JEXOMER", "KYLORAX",
              "LUMIRAX", "NEPHORA", "OSTRAVEX", "PALUNDRA", "RIZOMEX", "TAVORINE", "ULVANTRA", "WENDAXIL"]   # @0.2: 20 (GSK has 16 stems)
# @0.2 (review N4): brands of the real supplier that are NOT covered_product-* of any MSA (they appear only in market-share exhibit rows,
# e.g. "Countrywide Tdap / TENIVAC") were left un-renamed in 2 of 300 rn prompts. Supplier attribution from public product labelling
# (the reviewer's independent list, evidence-eval@0.1/rn_residual.py); key = substring of the corpus supplier_name. Only stems that occur
# as a whole token somewhere in the corpus are added (so the fake-stem pool stays small); asserted below: 0 rn rows keep any real stem.
PUBLIC_BRANDS = {
    "GSK": "AREXVY HAVRIX TWINRIX KINRIX INFANRIX ROTARIX MENVEO PENMENVY FLUARIX BEXSERO BOOSTRIX ENGERIX PEDIARIX PRIORIX SHINGRIX FLULAVAL CERVARIX HIBERIX",
    "PFIZER": "PREVNAR ABRYSVO COMIRNATY TRUMENBA NIMENRIX PENBRAYA TICOVAC VAXCHORA",
    "MERCK": "GARDASIL PNEUMOVAX PROQUAD RECOMBIVAX ROTATEQ VARIVAX VAXNEUVANCE CAPVAXIVE ENFLONSIA VAQTA PEDVAXHIB ZOSTAVAX ERVEBO",
    "SANOFI": "ADACEL BEYFORTUS FLUBLOK FLUZONE MENQUADFI PENTACEL QUADRACEL DAPTACEL IPOL IMOVAX TENIVAC YF-VAX TYPHIM MENACTRA",
    "SEQIRUS": "FLUAD FLUCELVAX AFLURIA AUDENZ"}
GENERIC = {"PHARM", "PHARMA", "COMPANY", "CO", "INC", "CORP", "TECH", "&", "VACCINE", "VACCINES", "COMP", "BIOLOGICS"}
corpus = [(f, open(f, encoding="utf-8").read()) for f in sorted(glob.glob(f"{G}/*/docs/*") + glob.glob(f"{G}/*/leaves/*") + glob.glob(f"{G}/*/qa.jsonl"))]
corpus += [(TRAIN_ROWS, open(TRAIN_ROWS, encoding="utf-8").read()), ("SYS", SYS)]
fake_terms = FAKE + [w for f in FAKE for w in f.split() if w not in GENERIC] + FAKE_STEMS
must(pc.check_absent(fake_terms, corpus), "fake names vs corpus")
def uid(u): return f"{u[0]}#{u[1]}" if u[1] else f"{u[0]}#*"
def utext(u): return cl[f"{u[0]}-{u[1]}"] if u[1] else pl[u[0]]
def qgroup(t): return t.split(".")[0] if t.split(".")[0] in ("metric", "cxs", "refuse") else t

def build(q):
    doc = q["doc_id"]; req = set(); units = {(doc, s) for s in doc_secs.get(doc, [])}; src = None
    if q.get("source_anchor"):
        for an in dict.fromkeys([q["source_anchor"]] + [v["anchor"] for v in q["spans"].values()]):
            adoc, sec = an.split("#")
            u = (adoc, sec) if f"{adoc}-{sec}" in cl else ((adoc, None) if adoc in pl else None)
            assert u, f"unresolved {q['qa_id']} {an}"; req.add(u); units.add(u)
        sa = q["source_anchor"].split("#"); src = (sa[0], sa[1]) if f"{sa[0]}-{sa[1]}" in cl else (sa[0], None)
        gold = {"answer": q["answer"], "spans": q["spans"]}
        for v in q["spans"].values():
            assert v["text"] in utext((v["anchor"].split("#")[0], v["anchor"].split("#")[1]) if v["anchor"].replace("#", "-") in cl else (v["anchor"].split("#")[0], None)), q["qa_id"]
    else:
        gold = REFUSAL
    order = sorted(units, key=lambda u: (u[0], nat(u[1]) if u[1] else ()))
    rpos = [i for i, u in enumerate(order) if u in req]
    dist = lambda i: min(abs(i - r) for r in rpos) if rpos else i
    cand = iter(sorted((i for i in range(len(order)) if order[i] not in req), key=lambda i: (dist(i), i), reverse=True))
    kept = set(range(len(order))); dropped = 0
    while True:
        row = {"question": q["question"], "units": [{"id": uid(order[i]), "text": utext(order[i])} for i in sorted(kept)]}
        if len(prompt_ids(messages(row))) <= PROMPT_BUDGET: break
        i = next(cand, None); assert i is not None, f"required clauses exceed budget {q['qa_id']}"
        kept.discard(i); dropped += 1
    seq = [order[i] for i in sorted(kept)]; pos = None
    if src is not None:
        p = seq.index(src); pos = "only" if len(seq) == 1 else ("first" if p == 0 else ("last" if p == len(seq) - 1 else "middle"))
    return {"id": f"test:{q['qa_id']}", "kind": "test", "src": q["qa_id"], "qa_id": q["qa_id"], "system_id": q["system_id"],
            "question_type": q["question_type"], "qt_group": qgroup(q["question_type"]), "answer_type": q["answer_type"],
            "manufacturer": supplier[q["system_id"]], "truncated": dropped > 0, "clauses_dropped": dropped, "anchor_position": pos,
            "question": q["question"], "units": row["units"], "gold": gold, "expect_refusal": gold == REFUSAL,
            "gold_anchor_ids": sorted({uid(u) for u in req})}

test = [build(q) for q in qa]
by = {r["src"]: r for r in test}
# ---------------- probes ----------------
MONTHS = "January February March April May June July August September October November December".split()
NUM = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?![\d,]*\d)")
def fmt_like(old_int, old_dec, val):
    dec = len(old_dec) - 1 if old_dec else 0
    s = f"{val:,.{dec}f}" if "," in old_int else f"{val:.{dec}f}"
    return s
def counterfactual(text, atype, rng):
    if atype == "date":
        m = re.fullmatch(r"(\d{1,2}) (%s) (\d{4})" % "|".join(MONTHS), text) or re.fullmatch(r"(%s) (\d{1,2}), (\d{4})" % "|".join(MONTHS), text)
        if not m: return None
        day = int(m.group(1) if m.group(1).isdigit() else m.group(2)); new = rng.choice([d for d in range(2, 29) if d != day])
        return text.replace(str(day), str(new), 1)
    nums = list(NUM.finditer(text))
    if len(nums) != 1: return None
    m = nums[0]; old = float(m.group(1).replace(",", "") + (m.group(2) or ""))
    if old == 0: return None
    for _ in range(20):
        new = fmt_like(m.group(1), m.group(2), old * rng.choice([0.55, 0.7, 1.35, 1.6]))
        if float(new.replace(",", "")) not in (old, 0): return text[:m.start()] + new + text[m.end():]
    return None
def probe(base, kind, n, **kw):
    r = json.loads(json.dumps(base)); r.update(kind=kind, id=f"{kind}:{base['src']}:{n}", **kw); return r
probes = collections.defaultdict(list); elig = collections.Counter()
rng0 = lambda k: random.Random(f"562-{k}")
answerable = [r for r in test if not r["expect_refusal"]]
# (a) counterfactual: single-span numeric/date rows; old value once in its anchor clause, nowhere else in the prompt
pool = []
for r in answerable:
    sp = list(r["gold"]["spans"].values())
    if len(sp) != 1 or r["answer_type"] not in ("date", "int", "pct", "num"): continue
    old = sp[0]["text"]; aid = sp[0]["anchor"]
    ai = [i for i, u in enumerate(r["units"]) if u["id"] == aid or (u["id"].endswith("#*") and u["id"][:-2] == aid.split("#")[0])]
    if len(ai) != 1 or occurs(r["units"][ai[0]]["text"], old) != 1 or occurs(full_text(r), old) != 1: continue
    pool.append((r, ai[0], old))
elig["cf"] = len(pool); rng = rng0("cf")
for r, i, old in rng.sample(pool, min(N_PROBE, len(pool))):
    new = counterfactual(old, r["answer_type"], rng)
    if new is None or occurs(full_text(r), new): continue
    p = probe(r, "cf", 0, old_value=old, new_value=new)
    p["units"][i]["text"] = re.sub(r"(?<![\w.,])" + re.escape(old) + r"(?![\w]|[.,]\d)", lambda _: new, p["units"][i]["text"], count=1)
    k = next(iter(p["gold"]["spans"])); p["gold"]["spans"][k]["text"] = new
    assert occurs(full_text(p), new) == 1 and occurs(full_text(p), old) == 0
    probes["cf"].append(p)
# (b) anchor removal: drop every anchor/span unit; the gold span text must then appear nowhere in the prompt -> must refuse
pool = []
for r in answerable:
    keep = [u for u in r["units"] if u["id"] not in r["gold_anchor_ids"]]
    if not keep: continue
    txt = r["question"] + "\n" + "\n".join(u["text"] for u in keep)
    if any(occurs(txt, v["text"]) for v in r["gold"]["spans"].values()): continue
    pool.append((r, keep))
elig["ar"] = len(pool); rng = rng0("ar")
for r, keep in rng.sample(pool, min(N_PROBE, len(pool))):
    p = probe(r, "ar", 0, removed=r["gold_anchor_ids"], old_value=[v["text"] for v in r["gold"]["spans"].values()])
    p["units"] = keep; p["gold"] = REFUSAL; p["expect_refusal"] = True; p["anchor_position"] = None; probes["ar"].append(p)
# placebo control for old-value evidence (@0.1, H2): another system's gold for the same question type, frequency-weighted,
# absent from the probe prompt; may equal the old value (then the pair is concordant). Own per-row rng: probe selection unchanged.
by_qt = collections.defaultdict(list)
for x in answerable: by_qt[x["question_type"]].append(x)
def placebo(p, single):
    cands = [x for x in by_qt[p["question_type"]] if x["system_id"] != p["system_id"] and (len(x["gold"]["spans"]) == 1 or not single)]
    random.Random(f"562-placebo-{p['id']}").shuffle(cands); ft = full_text(p)
    for x in cands:
        v = [y["text"] for y in x["gold"]["spans"].values()]
        if not any(occurs(ft, t) for t in v): return v[0] if single else v
    return None
for p in probes["cf"]: p["placebo_value"] = placebo(p, True)
for p in probes["ar"]: p["placebo_value"] = placebo(p, False)
# (c) clause shuffle: >= 3 units, seeded permutation that moves the anchor unit
pool = [r for r in answerable if len(r["units"]) >= 3]; elig["sh"] = len(pool); rng = rng0("sh")
for r in rng.sample(pool, min(N_PROBE, len(pool))):
    ids0 = [u["id"] for u in r["units"]]
    for _ in range(50):
        perm = rng.sample(range(len(ids0)), len(ids0))
        if all(ids0.index(a) != perm.index(ids0.index(a)) for a in r["gold_anchor_ids"] if a in ids0): break
    else: continue
    p = probe(r, "sh", 0, perm=perm); p["units"] = [r["units"][j] for j in perm]; p["anchor_position"] = None; probes["sh"].append(p)
# (d) supplier rename to a fictitious name (checked absent from the whole corpus); question, clauses and gold spans
# @0.1 (M7): brand stems identify the real supplier (a renamed GSK row still listed BEXSERO, BOOSTRIX). Catalog = covered_product-* of every
# MSA terms file (train + test) grouped by supplier_name; stem = first token of the brand ("BOOSTRIX TDAP" -> BOOSTRIX; class words kept).
catalog = collections.defaultdict(set)
for f in glob.glob(f"{G}/*/docs/*-MSA1.terms.json"):
    fl = json.load(open(f))["fields"]; sn = [v["value"] for k, v in fl.items() if k == "supplier_name"]
    if sn: catalog[sn[0]].update(v["value"].split()[0] for k, v in fl.items() if k.startswith("covered_product"))
corpus_tokens = set()
for f in glob.glob(f"{G}/*/docs/*"):
    try: corpus_tokens.update(re.findall(r"[A-Za-z0-9-]+", open(f, errors="ignore").read().upper()))
    except IsADirectoryError: pass
for sname in list(catalog):
    for key, lst in PUBLIC_BRANDS.items():
        if key in sname.upper(): catalog[sname].update(t for t in lst.split() if t in corpus_tokens)
def wsub(t, old, new): return re.sub(r"(?<![A-Za-z0-9-])" + re.escape(old) + r"(?![A-Za-z0-9-])", new, t, flags=re.I)
pool = [r for r in test if r["manufacturer"] in full_text(r)]; elig["rn"] = len(pool); rng = rng0("rn")
for r in rng.sample(pool, min(N_PROBE, len(pool))):
    fake = rng.choice(FAKE); old = r["manufacturer"]
    stems = sorted(catalog[old]); fk = FAKE_STEMS[:]; random.Random(f"562-rn-brand-{r['src']}").shuffle(fk); bmap = dict(zip(stems, fk))
    assert len(stems) <= len(FAKE_STEMS), old
    toks = [w for w in old.split() if w not in GENERIC]; ftok = [w for w in fake.split() if w not in GENERIC][0]
    subs = [(old, fake)] + [(b, bmap[b]) for b in sorted(stems, key=len, reverse=True)] + [(w, ftok) for w in toks]
    p = probe(r, "rn", 0, renamed_from=old, renamed_to=fake, renamed_brands=bmap, leak_terms=sorted({old, *toks, *stems}))
    def ren(t):
        for o, n in subs: t = wsub(t, o, n)
        return t
    p["question"] = ren(p["question"])
    for u in p["units"]: u["text"] = ren(u["text"])
    for v in p["gold"]["spans"].values(): v["text"] = ren(v["text"])
    p["brand_hits_replaced"] = sum(len(re.findall(r"(?<![A-Za-z0-9-])" + re.escape(b) + r"(?![A-Za-z0-9-])", full_text(r), re.I)) for b in stems)
    full_p = p["question"] + "\n" + "\n".join(u["text"] for u in p["units"]) + "\n" + json.dumps(p["gold"])
    resid = [b for b in stems if re.search(r"(?<![A-Za-z0-9-])" + re.escape(b) + r"(?![A-Za-z0-9-])", full_p, re.I)]
    assert not resid, (p["id"], resid)                     # @0.2 (N4): no real brand stem of the renamed supplier survives
    probes["rn"].append(p)
# (e) paraphrase outside both template families (family C, written here; 4-gram overlap with every train+test question asserted 0)
PP = {"effective_date": ["On which calendar day did this master contract first take force?", "Give the opening day of the master contract's term."],
      "expiration_date": ["Give the final calendar day of the master contract's term.", "Which calendar day closes out the master contract's term?"],
      "renewal_notice_days": ["Before term close, how many days earlier must a party say it will not continue?", "Count of days of warning required to stop the term from continuing?"],
      "auto_renew": ["Will the master contract carry on by itself once its term closes?", "Once the term closes, does the deal continue with nobody acting?"],
      "termination_notice_days": ["Once a quit notice is delivered, how many days pass before the exit counts?", "Days between delivering a quit notice and the exit counting?"],
      "termination_for_convenience": ["May either side quit the master contract with no cause stated?", "Can one side leave the deal without stating any cause?"],
      "share_floor_pct": ["Smallest slice of class volume reserved for the vendor under the master contract?", "What least fraction of class purchases goes to the vendor?"],
      "exclusivity_class": ["Name the vaccine class in which the vendor enjoys favoured status.", "For what vaccine class is the vendor favoured?"],
      "admin_fee_pct": ["What rate does the vendor hand back to cover group running costs?", "Rate the vendor returns for group upkeep?"],
      "amended_share_floor": ["Following the later change document, what least slice goes to the vendor?", "Once changed later on, what least fraction goes to the vendor?"],
      "amendment_exclusivity": ["Identify the later change document that altered favoured status.", "Which later paper altered the vendor's favoured status?"],
      "tier_min_doses": ["Per-year dose count that opens rebate level {n}?", "Dose count needed per year to unlock level {n}?"],
      "tier_rebate_pct": ["What rebate rate comes with level {n}?", "Level {n} carries what rebate rate?"],
      "commitment_doses_per_year": ["What yearly {cls} dose minimum has the account signed up for?", "Yearly {cls} doses the account has signed up to buy?"],
      "proposal_get": ["For its {year} approach, what was the vendor after?", "What did the vendor want back in {year}?"],
      "proposal_give": ["What did the vendor hand over in its {year} pitch?", "In {year}, what did the vendor hand over?"],
      "proposal_outcome": ["Final status of the vendor's {year} approach?", "Where did the vendor's {year} pitch land?"]}
grams = pc.grams
known = set().union(*(grams(q["question"]) for q in train_q + qa))
known_q = {q["question"].strip().lower() for q in train_q + qa}
must(pc.check_paraphrase_templates(PP, known), "paraphrase template shares a 4-gram with a corpus question")
def slots(r):
    q = r["question"]; d = {}
    if "{n}" in "".join(PP[r["question_type"]]):
        m = re.search(r"\b(?:Band|Tier|band|tier) (\d+)", q); d["n"] = m and m.group(1)
    if "{cls}" in "".join(PP[r["question_type"]]):
        m = re.search(r"How many (.+?) doses", q); d["cls"] = m and m.group(1)
    if "{year}" in "".join(PP[r["question_type"]]):
        m = re.search(r"\b(20\d\d)\b", q); d["year"] = m and m.group(1)
    return d if all(d.values()) else None
pool = [r for r in test if r["question_type"] in PP and slots(r) is not None]; elig["pp"] = len(pool); rng = rng0("pp")
for r in rng.sample(pool, min(N_PROBE, len(pool))):
    s = rng.choice(PP[r["question_type"]]).format(**slots(r))
    assert s.strip().lower() not in known_q
    probes["pp"].append(probe(r, "pp", 0, question=s, original_question=r["question"]))
# ---------------- tokens, ids hashes, few-shot ----------------
tr = [json.loads(l) for l in open(TRAIN_ROWS)]
ans1 = min((x for x in tr if x["answerable"] and len(json.loads(x["assistant"])["spans"]) == 1), key=lambda x: (x["tokens"], x["qa_id"]))
ref1 = min((x for x in tr if not x["answerable"]), key=lambda x: (x["tokens"], x["qa_id"]))
fewshot = [{"qa_id": x["qa_id"], "user": x["user"], "assistant": x["assistant"]} for x in (ans1, ref1)]
rows = test + [p for k in ("cf", "ar", "sh", "rn", "pp") for p in probes[k]]
over = 0
for r in rows:
    ids = prompt_ids(messages(r)); fs = prompt_ids(messages(r, fewshot))
    r["prompt_tokens"] = len(ids); r["ids_sha256"] = hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest()
    r["fs_prompt_tokens"] = len(fs); r["fs_ids_sha256"] = hashlib.sha256(",".join(map(str, fs)).encode()).hexdigest()
    over += len(ids) > PROMPT_BUDGET
assert over == 0, f"{over} rows over the prompt budget"                    # review L3: probes included
must(pc.check_rows(rows, known), "probe rows")                                  # review M8/I1: instantiated rows, every kind
with open(f"{OUT}/eval_rows.jsonl", "w") as f:
    for r in rows: f.write(json.dumps(r, sort_keys=True) + "\n")
json.dump(fewshot, open(f"{OUT}/fewshot.json", "w"), indent=1, sort_keys=True)
gold_ans = [r["gold"] for r in test if not r["expect_refusal"]]
pt = sorted(r["prompt_tokens"] for r in rows)
stats = {"rows": len(rows), "by_kind": dict(collections.Counter(r["kind"] for r in rows)), "eligible_pool": dict(elig),
         "test_unanswerable": sum(r["expect_refusal"] for r in test), "test_truncated": sum(r["truncated"] for r in test),
         "test_anchor_position": dict(collections.Counter(r["anchor_position"] for r in test if r["anchor_position"])),
         "manufacturer_rows": dict(collections.Counter(r["manufacturer"] for r in test)),
         "prompt_tokens_min_p50_p90_max_mean": [pt[0], pt[len(pt) // 2], pt[int(.9 * len(pt))], pt[-1], round(sum(pt) / len(pt), 1)],
         "fs_prompt_tokens_mean": round(sum(r["fs_prompt_tokens"] for r in rows) / len(rows), 1), "over_budget_rows": over,
         "rn_brand_hits_replaced": sum(p["brand_hits_replaced"] for p in probes["rn"]),
         "rn_rows_with_brand": sum(p["brand_hits_replaced"] > 0 for p in probes["rn"]),
         "rn_gold_with_renamed_term": sum(any(n.lower() in json.dumps(p["gold"]).lower() for n in [p["renamed_to"], *p["renamed_brands"].values()]) for p in probes["rn"]),
         "placebo_rows": {k: sum(p.get("placebo_value") is not None for p in probes[k]) for k in ("cf", "ar")},
         "corpus_files_checked_for_fake_names": len(corpus),
         "gold_digits_in_answer": sum(digits_in_answer(g) for g in gold_ans), "gold_denylist_hits": sum(denylist_hit(g) for g in gold_ans),
         "fewshot_qa_ids": [x["qa_id"] for x in fewshot], "prompt_budget": PROMPT_BUDGET, "n_probe": N_PROBE, "seed": 562,
         "test_qa_sha256": TEST_QA_SHA, "train_rows_sha256": sha(TRAIN_ROWS),
         "tokenizer_sha256": {"tokenizer.json": sha(f"{T}/tokenizer.json"), "tokenizer_config.json": sha(f"{T}/tokenizer_config.json")},
         "eval_rows_sha256": sha(f"{OUT}/eval_rows.jsonl"), "fewshot_sha256": sha(f"{OUT}/fewshot.json")}
json.dump(stats, open(f"{OUT}/BUILD.json", "w"), indent=1, sort_keys=True); print(json.dumps(stats))
