# Bluebird v1.0 eval @0.1: probe-row invariants (review M7, M8, I1, I2, L3). Stdlib only.
# build_eval_rows.py runs these before it writes anything; the box suite runs them on the shipped eval_rows.jsonl and on broken copies.
import hashlib, json, re
from evalcore import REFUSAL, PROMPT_BUDGET, leak_hits

def occurs(hay, needle):
    return len(re.findall(r"(?<![\w.,])" + re.escape(needle) + r"(?![\w]|[.,]\d)", hay))
def full_text(r): return r["question"] + "\n" + "\n".join(u["text"] for u in r["units"])
def grams(s, n=4):
    w = re.sub(r"[^a-z0-9 ]", " ", s.lower()).split(); return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}
def nq(s): return re.sub(r"\s+", " ", s).strip().lower()

def check_sha_pin(path, want):
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return [] if got == want else [("sha_pin", f"{path} {got} != {want}")]
def check_system_disjoint(test_systems, train_systems):
    both = sorted(set(test_systems) & set(train_systems))
    return [("system_overlap", s) for s in both]
def check_absent(terms, texts):
    """Every term (case-insensitive, word-bounded) must be absent from every text (I2: fake names vs the train corpus)."""
    out = []
    pats = [(t, re.compile(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", re.I)) for t in terms]
    for name, txt in texts:
        for t, p in pats:
            if p.search(txt): out.append(("fake_term_in_corpus", f"{t} in {name}"))
    return out
def check_paraphrase_templates(pp_templates, known):
    out = []
    for t, v in pp_templates.items():
        for s in v:
            g = grams(s.replace("{n}", "1").replace("{cls}", "Influenza").replace("{year}", "2025"))
            if g & known: out.append(("pp_template_4gram", s))
    return out

def check_rows(rows, known_grams=None):
    """Returns a list of (code, row id). Empty = every probe invariant holds."""
    P = []; seen = set(); test = {}
    for r in rows:
        if r["id"] in seen: P.append(("dup_id", r["id"]))
        seen.add(r["id"])
        if r["kind"] == "test": test[r["src"]] = r
    for r in rows:
        i = r["id"]; k = r["kind"]; ft = full_text(r)
        if r.get("prompt_tokens", 0) > PROMPT_BUDGET: P.append(("over_budget", i))          # L3: every row, probes included
        if k == "test": continue
        s = test.get(r["src"])
        if s is None: P.append(("no_src", i)); continue
        if k == "cf":
            sp = list(r["gold"]["spans"].values())
            if len(sp) != 1 or sp[0]["text"] != r["new_value"]: P.append(("cf_gold_not_new", i))
            if occurs(ft, r["new_value"]) != 1: P.append(("cf_new_not_once", i))
            if occurs(ft, r["old_value"]) != 0: P.append(("cf_old_present", i))
            if r.get("placebo_value") is not None and occurs(ft, r["placebo_value"]): P.append(("cf_placebo_present", i))
        elif k == "ar":
            if not r["expect_refusal"] or r["gold"] != REFUSAL: P.append(("ar_gold_not_refusal", i))
            if set(r["removed"]) & {u["id"] for u in r["units"]}: P.append(("ar_unit_kept", i))
            if any(occurs(ft, v) for v in r["old_value"]): P.append(("ar_old_present", i))
            if any(occurs(ft, v) for v in (r.get("placebo_value") or [])): P.append(("ar_placebo_present", i))
        elif k == "sh":
            a, b = [u["id"] for u in r["units"]], [u["id"] for u in s["units"]]
            if sorted(a) != sorted(b): P.append(("sh_units_changed", i))
            if any(x in b and a.index(x) == b.index(x) for x in r["gold_anchor_ids"]): P.append(("sh_anchor_not_moved", i))
        elif k == "rn":
            if leak_hits(ft + "\n" + json.dumps(r["gold"]), r["leak_terms"]): P.append(("rn_real_name_present", i))
            if r["renamed_from"] not in r["leak_terms"]: P.append(("rn_leak_terms_incomplete", i))
            if r["renamed_to"].lower() not in ft.lower(): P.append(("rn_fake_absent", i))
        elif k == "pp":
            if nq(r["question"]) == nq(s["question"]): P.append(("pp_not_paraphrased", i))
            if grams(r["question"]) & grams(s["question"]): P.append(("pp_4gram_with_original", i))
            if known_grams is not None and grams(r["question"]) & known_grams: P.append(("pp_4gram_with_corpus", i))
            if [u["id"] for u in r["units"]] != [u["id"] for u in s["units"]]: P.append(("pp_units_changed", i))
        else:
            P.append(("unknown_kind", i))
    return P
