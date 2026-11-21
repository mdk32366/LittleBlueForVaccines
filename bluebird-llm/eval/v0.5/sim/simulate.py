# False-alarm / power simulation for the @0.2 bars (same bars as @0.1), through score.py's OWN decision_counts() + decide() (not a re-implementation).
# Reader model = the review's honest reader (evidence/21): independent per-row accuracy p on every row and kind; a wrong answer is a refusal
# or a content-free span (never the old or placebo value); anchor-removal rows are refused with probability p. Per-row score dicts are
# precomputed once per output variant with score.py's score_row(), then mixed per replicate.
import json, os, random, sys, collections, multiprocessing as mp
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, H); sys.path.insert(0, os.path.join(H, "tests"))
import score, stubs
rows = {r["id"]: r for r in (json.loads(l) for l in open(os.path.join(H, "eval_rows.jsonl")))}
def pre(fn):
    out = {}
    for i, r in rows.items():
        d = score.score_row(r, fn(r)); d["_gold_ref"] = r["expect_refusal"]; out[i] = d
    return out
V = {"gold": pre(stubs.gold), "ref": pre(stubs.refuse), "fo": pre(stubs.format_only), "mem": pre(stubs.mem)}
IDS = sorted(rows)
# null for the memorisation test: wrong cf/ar answers that are a PLAUSIBLE value (another test system's gold for the same question type,
# frequency-weighted), i.e. prior-driven guessing. Up to 20 candidates per cf/ar row, scored once.
by_qt = collections.defaultdict(list)
for r in rows.values():
    if r["kind"] == "test" and not r["expect_refusal"]: by_qt[r["question_type"]].append(r)
HAL = {}
for i, r in rows.items():
    if r["kind"] not in ("cf", "ar"): continue
    c = [x for x in by_qt[r["question_type"]] if x["system_id"] != r["system_id"] and (r["kind"] == "ar" or len(x["gold"]["spans"]) == 1)]
    random.Random("hal" + i).shuffle(c); out = []
    for x in c[:20]:
        if r["kind"] == "cf":
            g = json.loads(json.dumps(r["gold"])); k = next(iter(g["spans"])); g["spans"][k]["text"] = next(iter(x["gold"]["spans"].values()))["text"]
        else: g = x["gold"]
        d = score.score_row(r, json.dumps(g)); d["_gold_ref"] = r["expect_refusal"]; out.append(d)
    HAL[i] = out
def reader(p_of, mem_frac=0.0, hal=0.0):
    def one(seed):
        rng = random.Random(seed); D = {}
        for i in IDS:
            r = rows[i]
            if mem_frac and r["kind"] in ("cf", "ar") and rng.random() < mem_frac: D[i] = V["mem"][i]; continue
            if rng.random() < p_of(r): D[i] = V["gold"][i]
            elif hal and HAL.get(i) and rng.random() < hal: D[i] = rng.choice(HAL[i])
            elif r["expect_refusal"]: D[i] = V["fo"][i]
            else: D[i] = V["ref"][i] if rng.random() < 0.5 else V["fo"][i]
        dec = score.decide(score.decision_counts(rows, D))
        return dec["verdict"], [b["id"] for b in dec["bars"] if b["status"] != "PASS" and b["id"] != "G-G"]
    return one
SCEN = {}
for p in (0.45, 0.70, 0.80, 0.83, 0.85, 0.88, 0.90, 0.92, 0.95, 0.97, 0.99): SCEN[f"honest p={p:.2f}"] = (p, None, 0.0)
SCEN["power: shuffle-sensitive (0.95, sh 0.85)"] = (0.95, ("sh", 0.85), 0.0)
SCEN["power: shuffle-sensitive (0.95, sh 0.88)"] = (0.95, ("sh", 0.88), 0.0)
SCEN["power: paraphrase-fragile (0.95, pp 0.85)"] = (0.95, ("pp", 0.85), 0.0)
for f in (0.02, 0.05, 0.10): SCEN[f"power: memorises {int(f*100)}% of cf/ar (else honest 0.92)"] = (0.92, None, f)
SCEN["null: plausible-value guesser (honest 0.70; every wrong cf/ar answer is another system's value)"] = (0.70, None, 0.0, 1.0)
SCEN["null: plausible-value guesser (honest 0.92; every wrong cf/ar answer is another system's value)"] = (0.92, None, 0.0, 1.0)
def run(args):
    name, k = args; p, alt, mf, *h = SCEN[name]
    pof = (lambda r: alt[1] if r["kind"] == alt[0] else p) if alt else (lambda r: p)
    return name, reader(pof, mf, h[0] if h else 0.0)(f"{name}-{k}")
if __name__ == "__main__":
    R = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    OUTP = sys.argv[2] if len(sys.argv) > 2 else os.path.join(H, "sim", "SIM-RESULTS")
    jobs = [(n, k) for n in SCEN for k in range(R)]
    with mp.get_context("fork").Pool(int(os.environ.get("LBE_SIM_JOBS", "4"))) as pool: res = pool.map(run, jobs, chunksize=50)
    agg = collections.defaultdict(lambda: {"n": 0, "v": collections.Counter(), "bars": collections.Counter()})
    for name, (v, fb) in res:
        a = agg[name]; a["n"] += 1; a["v"][v] += 1; a["bars"].update(fb)
    OLD = {0.90: 0.792, 0.92: 0.330, 0.95: 0.077, 0.97: 0.024, 0.99: 0.000}     # review evidence/21 (@0.0 point-estimate bars, 4,000 sims)
    L = ["| scenario | reps | P(not READS) | READS | INCONCLUSIVE | MEMORISES | DEGENERATE | top failing bars (rate) | @0.0 P(not READS) |", "|---|---|---|---|---|---|---|---|---|"]
    out = {}
    for name in SCEN:
        a = agg[name]; n = a["n"]; fr = lambda k: a["v"][k] / n
        top = ", ".join(f"{b} {c / n:.3f}" for b, c in a["bars"].most_common(3))
        p = SCEN[name][0]; old = OLD.get(p) if name.startswith("honest") else None
        L.append(f"| {name} | {n} | {1 - fr('READS'):.3f} | {fr('READS'):.3f} | {fr('INCONCLUSIVE'):.3f} | {fr('MEMORISES'):.3f} | {fr('DEGENERATE'):.3f} | {top} | {'' if old is None else old} |")
        out[name] = {"reps": n, "verdicts": dict(a["v"]), "bar_fail_counts": dict(a["bars"])}
    txt = "\n".join(L); print(txt)
    json.dump(out, open(OUTP + ".json", "w"), indent=1, sort_keys=True)
    open(OUTP + ".md", "w").write(f"# @0.2 bar simulation ({R} replicates per scenario; score.decide with default PARAMS)\n\n{txt}\n")
