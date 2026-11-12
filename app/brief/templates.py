"""templates.py: templated talking points, written only in fact tokens (no digits). Framing per PROPOSAL.md:
where we're strong, where we're exposed, white space, questions to ask. Conditions read facts; text never carries numbers."""


def points(fs) -> list:
    f = fs.facts
    out = [
        "Size: purchases of {F1.dollars} across {F1.doses} doses rank this system {F1.rank} of {F1.n_systems} synthetic peers and equal {F1.bench_share} of benchmark dollars.",
        "Mix: {F2.top_class} leads at {F2.top_class_share} of dollars; the main facility type is {F3.top_facility} at {F3.top_facility_share}.",
        "Manufacturers: Pfizer holds {F4.pfizer_share} of dollars ({F4.pfizer_dollars}); the largest manufacturer is {F4.top_mfr}.",
    ]
    if fs.v("F5.status") == "flagged":
        out.append("Share move: {F5.top_mfr} in {F5.top_class} moved from {F5.top_from} to {F5.top_to} of class doses between the two windows.")
    else:
        out.append("Switching: no material switching between the two windows.")
    st = fs.v("F6.status")
    if st == "ok":
        s = "White space: the MenB to MenACWY dose ratio is {F6.ratio}, an index of {F6.index_vs_bench} against the benchmark"
        s += (", and {F6.index_vs_state} against in-state peers." if "F6.index_vs_state" in f
              else "; in-state comparison: {F6.state_status}.")
        out.append(s)
    elif st == "undefined":
        out.append("White space: the MenB to MenACWY ratio is undefined because this system has no MenACWY doses; MenB doses total {F6.menb_doses}.")
    else:
        out.append("White space: MenB and MenACWY volume is too low to state a ratio ({F6.status}).")
    if "F7.growth_pct" in f:
        out.append("Trend: trailing twelve-month dollars moved {F7.growth_pct} against the prior twelve months; {F7.top_grower} grew most and {F7.top_decliner} fell most.")
    q = "{F5.top_class}" if "F5.top_class" in f else "{F2.top_class}"
    out.append(f"Question to ask: what is driving purchasing in {q}, and which programs are planned for next season?")
    out.append("Returns netted out of totals: {F8.returns_dollars} across {F8.returns_rows} return rows.")
    return out
