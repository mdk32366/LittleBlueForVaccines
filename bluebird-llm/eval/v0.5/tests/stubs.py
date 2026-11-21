# Adversarial / honest prediction stubs for the @0.1 verdict tests and simulation. Ported from the @0.0 review (scratch/adv/mkstubs.py, mk2.py)
# and extended. Each stub maps a row to a raw output string. Never imported by eval.py/score.py.
import json, random, re, collections, itertools
REF = json.dumps({"answer": "not in the contracts", "spans": {}})
def gold(r): return json.dumps(r["gold"])
def format_only(r): return json.dumps({"answer": "Value: {S1}.", "spans": {"S1": {"anchor": r["units"][0]["id"], "text": "see clause"}}})
def nums_in(r): return re.findall(r"\d[\d,]*(?:\.\d+)?(?: per cent|%)?", "\n".join(u["text"] for u in r["units"]))
num = lambda r: r["answer_type"] in ("date", "int", "pct", "num") and len(r["gold"]["spans"]) == 1
def mem(r):            # pure memoriser: knows every original answer, never reads
    if r["kind"] == "cf": g = json.loads(gold(r)); [v.__setitem__("text", r["old_value"]) for v in g["spans"].values()]; return json.dumps(g)
    if r["kind"] == "ar": return json.dumps({"answer": "Value: {S1}.", "spans": {"S1": {"anchor": r["removed"][0], "text": r["old_value"][0]}}})
    return gold(r)
def copy_anchor(r):
    if r["expect_refusal"] and r["kind"] != "ar": return REF
    ids = r.get("gold_anchor_ids") or []
    u = [x for x in r["units"] if x["id"] in ids] or r["units"][:1]
    return json.dumps({"answer": "{S1}", "spans": {"S1": {"anchor": u[0]["id"].replace("#*", "#1"), "text": u[0]["text"]}}})
def refuse(r): return REF
def length_gamer(r):
    sp = dict(r["gold"]["spans"]) if r["gold"]["spans"] else {}
    for n in nums_in(r)[:12]: sp[f"S{len(sp) + 1}"] = {"anchor": r["units"][0]["id"], "text": n}
    if not sp: return REF
    return json.dumps({"answer": " ".join("{%s}" % k for k in sp), "spans": sp})
def numeric_only(r):
    if random.Random(r["id"]).random() < 0.10: return '{"answer": "trunc'
    if r["kind"] in ("cf", "ar"): return gold(r)
    if r["expect_refusal"]: return REF
    if num(r): return gold(r)
    return format_only(r)
def numeric_only_clean(r):
    if r["kind"] in ("cf", "ar") or r["expect_refusal"] or num(r): return gold(r)
    return format_only(r)
def gold_but_invalid_nonnum(r):
    if r["kind"] == "test" and not num(r) and random.Random(r["id"]).random() < 0.08: return '{"answer": "x'
    return gold(r)
def honest(p, seed=""):
    """Honest reader, independent per-row accuracy p; wrong answers are never the old/placebo value (refusal or content-free)."""
    def f(r):
        rng = random.Random("h%s%s%s" % (p, seed, r["id"]))
        if rng.random() < p: return gold(r)
        if r["expect_refusal"]: return format_only(r)
        return REF if rng.random() < 0.5 else format_only(r)
    return f
def make_prior_guesser(rows):
    """Never reads: answers every row with the most common gold value of its question type (template prior)."""
    mode = {}
    for qt, xs in itertools.groupby(sorted((r for r in rows if r["kind"] == "test"), key=lambda r: r["question_type"]), key=lambda r: r["question_type"]):
        c = collections.Counter(gold(r) for r in xs); mode[qt] = json.loads(c.most_common(1)[0][0])
    def f(r):
        g = mode.get(r["question_type"])
        return REF if g is None else json.dumps(g)
    return f
def leaker(r):         # perfect reader that names the real supplier on renamed rows
    if r["kind"] == "rn":
        g = json.loads(gold(r)); g["answer"] = g["answer"] + " (" + r["renamed_from"].title() + ")" if g["spans"] else g["answer"]; return json.dumps(g)
    return gold(r)
def shuffle_sensitive(r):  # 0.95 reader that drops to ~0.75 when clauses are shuffled
    p = 0.75 if r["kind"] == "sh" else 0.95
    return honest(p, "ss")(r)
def partial_memoriser(frac):  # honest 0.92 reader that returns the old value on `frac` of cf/ar rows
    def f(r):
        if r["kind"] in ("cf", "ar") and random.Random("pm%s" % r["id"]).random() < frac: return mem(r)
        return honest(0.92, "pm")(r)
    return f
EXPECT = {"gold": "READS", "honest92": "READS", "honest45": "INCONCLUSIVE", "mem": "MEMORISES", "copy_anchor": "DEGENERATE", "refuse": "DEGENERATE",
          "length_gamer": "DEGENERATE", "format_only": "DEGENERATE", "numeric_only": "DEGENERATE", "numeric_only_clean": "INCONCLUSIVE",
          "gold_but_invalid_nonnum": "DEGENERATE", "prior_guesser": "DEGENERATE|INCONCLUSIVE", "leaker": "INCONCLUSIVE",
          "shuffle_sensitive": "INCONCLUSIVE", "partial_memoriser_30": "MEMORISES"}
def all_stubs(rows):
    return {"gold": gold, "honest92": honest(0.92), "honest45": honest(0.45), "mem": mem, "copy_anchor": copy_anchor, "refuse": refuse,
            "length_gamer": length_gamer, "format_only": format_only, "numeric_only": numeric_only, "numeric_only_clean": numeric_only_clean,
            "gold_but_invalid_nonnum": gold_but_invalid_nonnum, "prior_guesser": make_prior_guesser(rows), "leaker": leaker,
            "shuffle_sensitive": shuffle_sensitive, "partial_memoriser_30": partial_memoriser(0.30)}
