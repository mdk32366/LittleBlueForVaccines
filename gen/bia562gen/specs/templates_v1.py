"""schema_v1 template families (A = train, B = held-out; disjoint text, T-0031 / D-0026).

Built from the stub-v0 families (templates_stub.FAMILIES) with these changes only:
- the literal "Synthetic Supplier Co." becomes a {party} slot (D-0044 (real manufacturer as the contract party)); the
  defined term "the Supplier" stays, so the clauses otherwise read as before;
- MSA §1 also states the source facts (sites, subsidiaries, member type) and the invented covered specialty; the
  AMD and the proposal name the same party;
- three kept stub questions are reworded (A effective_date, A proposal_outcome, B termination_notice_days) because
  they match the app validator's CLINICAL pattern ("effective", "outcome"), which no answerable question may match
  (spec §6 item 4, T-0068). See docs/findings.md F-0027.
- new keys for EXH1 (exh_*), the metric reads (metric.*), contract x sales (cxs.*) and the refusals (refuse.*).
Item labels (A1..R7) are the client's own item names and live outside the families (schema_v1.ITEM_LABELS)."""
import copy

from .templates_stub import FAMILIES as STUB

FAMILIES = copy.deepcopy(STUB)
A, B = FAMILIES["A"], FAMILIES["B"]

# ---- kept stub text, party slot (D-0044) ----
A["clauses"]["parties"] = ('This Master Supply Agreement (the "Agreement") is made between {name} (the "Customer", '
                           'account {sid}) and {party} (the "Supplier"). The Agreement covers these products: {products}. '
                           'Participating sites: {sites}. Participating subsidiaries: {subs}. Member organisation type: '
                           '{otype}. Covered specialty: {cspec}.')
B["clauses"]["parties"] = ('{party} (hereafter "Supplier") and {name} (hereafter "Customer", account {sid}) enter into '
                           'this master arrangement. Products within its reach: {products}. Outlets taking part number '
                           '{sites}; owned units taking part number {subs}. The Customer is registered as {otype}. '
                           'Specialty in scope: {cspec}.')
A["clauses"]["amd_purpose"] = "This amendment, {amd_id}, between the Customer and {party}, modifies {msa_id} with effect from {date}."
B["clauses"]["amd_purpose"] = "Starting {date}, instrument {amd_id} agreed with {party} revises {msa_id}."
A["clauses"]["p_summary"] = "This proposal, {pid}, was presented by {party} (the Supplier) to {name} on {date}."
B["clauses"]["p_summary"] = "Prepared on {date}, pitch {pid} was put before {name} on behalf of {party}."

# ---- CLINICAL-pattern rewording of kept stub questions (F-0027) ----
A["questions"]["effective_date"] = ["When does the master agreement take effect?", "What is the start date of the MSA?",
                                    "On what date did the supply agreement begin?",
                                    "From which date is the master agreement in force?"]
B["questions"]["termination_notice_days"] = ["How long until an early ending takes effect?", "Early ending: how many days after notice?",
                                             "What delay applies to ending the arrangement early?",
                                             "How quickly does an early exit take hold?"]
A["questions"]["proposal_outcome"] = ["What was the result of the {year} proposal?",
                                      "How did the Customer respond to the {year} proposal?",
                                      "What is the status of the {year} proposal?", "Was the {year} proposal accepted?"]

# ---- EXH1 "Purchasing profile schedule" ----
A["headings"].update({
    "exh_1": "Basis of this Schedule", "exh_2": "Total Dollars and Relative Size", "exh_3": "Dollars by Class",
    "exh_4": "Dollars by Specialty", "exh_5": "Doses by Class and Specialty", "exh_6": "Organisation and Sites",
    "exh_7": "Babies Estimate and Age Mix", "exh_8": "Highest Dollars by Manufacturer and Brand",
    "exh_9": "Important Ratios", "exh_10": "Women's Health Season Ratios", "exh_11": "National Pooled Figures",
    "exh_12": "Indices against State and National", "exh_13": "Brand Shares across Seasons",
    "exh_cont": "{h}, continued",
})
B["headings"].update({
    "exh_1": "Scope Note", "exh_2": "Spend Scale", "exh_3": "Spend Mix per Vaccine Group",
    "exh_4": "Spend Mix per Care Setting", "exh_5": "Dose Grid: Group x Setting", "exh_6": "Footprint",
    "exh_7": "Infant Heuristic; Label Mix", "exh_8": "Leading Makers and Products",
    "exh_9": "Key Proportions", "exh_10": "OB-GYN Window Proportions", "exh_11": "Countrywide Aggregate",
    "exh_12": "Relative Standing", "exh_13": "Product Mix Drift",
    "exh_cont": "{h} (more)",
})
A["clauses"].update({
    "exh_1": ("This schedule forms part of the contract file for {name} (account {sid}). Figures for the Customer and "
              "its in-state peers come from the synthetic sales file over {full}; figures marked national are pooled "
              "totals from the public national file over the same months. The Women's Health ratios use the season "
              "{season}. Brand shares across seasons compare {sw1} with {sw2}. Dollars are whole, shares are shown to "
              "one decimal place and ratios to two."),
    "exh_line": "- {label}: {value}",
    "exh_line3": "- {label}: {value} (in-state peers {state}; national {nat})",
    "exh_line2s": "- {label}: {value} (in-state peers {state})",
    "exh_line2n": "- {label}: {value} (national {nat})",
    "exh_peers": "- In-state peers counted: {value}",
    "exh_switch": "- {cls}, largest brand gain: {value}",
    "exh_switch_brand": "- {cls}, {brand}: earlier season {w1}, later season {w2}",
    "exh_switch_nat": "- {cls}, largest national brand gain: {value}",
    "exh_switch_brand_nat": "- National {cls}, {brand}: earlier season {w1}, later season {w2}",
    "exh_party": "- {party} share of {cls} doses: earlier season {w1}, later season {w2}",
    "exh_idx": "- {label}: index vs in-state peers {state}; index vs national {nat}",
})
B["clauses"].update({
    "exh_1": ("Exhibit to the arrangement file of {name} [{sid}]. Account and same-state comparator numbers derive from "
              "the invented sales extract, months {full}; countrywide numbers are aggregates of the public "
              "nationwide extract for those months. OB-GYN proportions cover {season} only. Product mix drift "
              "sets {sw1} against {sw2}. Spend is rounded to the dollar; mix to a tenth of a point; proportions to "
              "hundredths."),
    "exh_line": "* {label} = {value}",
    "exh_line3": "* {label} = {value} | same-state pool {state} | countrywide {nat}",
    "exh_line2s": "* {label} = {value} | same-state pool {state}",
    "exh_line2n": "* {label} = {value} | countrywide {nat}",
    "exh_peers": "* Comparator accounts in the same state = {value}",
    "exh_switch": "* {cls} biggest product gainer = {value}",
    "exh_switch_brand": "* {cls} / {brand} = first window {w1} | second window {w2}",
    "exh_switch_nat": "* {cls} biggest countrywide gainer = {value}",
    "exh_switch_brand_nat": "* Countrywide {cls} / {brand} = first window {w1} | second window {w2}",
    "exh_party": "* {party} portion of {cls} doses = first window {w1} | second window {w2}",
    "exh_idx": "* {label} = relative to same-state pool {state} | relative to countrywide {nat}",
})

# ---- metric reads (one EXH1 span), contract x sales (two spans), refusals (exactly the refusal string) ----
A["questions"].update({
    "metric.system": ["What does the purchasing schedule give for {label}?", "Per the schedule, what is {label} for this system?",
                      "What figure does the exhibit state for {label}?", "Which value is listed for {label} in the schedule?"],
    "metric.state": ["What is the in-state peer figure for {label}?", "Among in-state peers, what is {label}?",
                     "What does the schedule give for in-state peers on {label}?", "For the state peer group, what is {label}?"],
    "metric.national": ["What is the pooled national figure for {label}?", "Nationally, what is {label}?",
                        "What national value does the schedule give for {label}?", "Across the national file, what is {label}?"],
    "metric.idx_nat": ["How does {label} compare nationally?", "What is the index vs national for {label}?",
                       "Against the national figure, where does {label} stand?", "What national index does the schedule give for {label}?"],
    "cxs.band": ["Which rebate tier has this system reached on trailing twelve month {cls} doses?",
                 "On recent {cls} volume, which tier does the system reach?",
                 "Given trailing twelve month {cls} doses, what tier is reached?",
                 "What is the highest tier the system's recent {cls} doses reach?"],
    "cxs.commit": ["Is the {cls} volume commitment met on trailing twelve month doses?",
                   "Do recent {cls} doses meet the yearly commitment?",
                   "Has the system met its {cls} commitment over the trailing twelve months?",
                   "Does trailing twelve month {cls} volume reach the commitment?"],
    "cxs.floor": ["Does {party} hold the share floor in the later season?",
                  "Is the {cls} share floor met by {party} in the later season?",
                  "In the later season, is {party} at or above its {cls} share floor?",
                  "Does the later season {cls} share of {party} reach the floor?"],
    "cxs.switch": ["Which brand gained the most {cls} share between seasons?", "Between seasons, which {cls} brand gained the most?",
                   "Which {cls} brand moved up the most from the earlier season to the later one?",
                   "Who led the {cls} brand share gains between seasons?"],
    "refuse.pricing": ["What price should we offer {party} for {cls}?", "Which rebate should we propose to {party} next year?",
                       "How low should our {cls} pricing go?", "What discount should we push for with {party}?"],
    "refuse.clinical": ["Is {b1} safer than {b2}?", "Which works better, {b1} or {b2}?",
                        "Does {b1} have fewer side effects than {b2}?", "Is {b1} more effective than {b2}?"],
    "refuse.real_data": ["What are this system's real purchase figures?", "How many doses did {name} actually buy last year?",
                         "What does the real sales history show for this system?", "Which real invoices back these numbers?"],
})
A["answers"].update({
    "metric.system": "The schedule gives {S1}.", "metric.state": "Among in-state peers it is {S1}.",
    "metric.national": "The pooled national figure is {S1}.", "metric.idx_nat": "Index vs national: {S1}.",
    "cxs.band_yes": "The highest tier reached starts at {S1} doses; trailing twelve month doses are {S2}.",
    "cxs.band_no": "No tier is reached: the first tier starts at {S1} doses and trailing twelve month doses are {S2}.",
    "cxs.commit_true": "Yes; trailing twelve month doses of {S2} meet the commitment of {S1}.",
    "cxs.commit_false": "No; trailing twelve month doses of {S2} fall short of the commitment of {S1}.",
    "cxs.floor_true": "Yes; the later season share of {S2} meets the floor of {S1}.",
    "cxs.floor_false": "No; the later season share of {S2} is below the floor of {S1}.",
    "cxs.floor_none": "The later season share cannot be measured ({S2}); the floor is {S1}.",
    "cxs.switch": "For the class in {S2}, the schedule lists the largest gain as {S1}.",
})
B["questions"].update({
    "metric.system": ["Profile exhibit: {label} for this account?", "How is {label} recorded for the account?",
                      "Account figure for {label}, please?", "Looking at the profile, {label} is what?"],
    "metric.state": ["Same-state comparator pool: {label}?", "How do same-state comparators read on {label}?",
                     "Comparator accounts in the state, {label}?", "What is the same-state pool's {label}?"],
    "metric.national": ["Countrywide aggregate for {label}?", "Nationwide reading of {label}?",
                        "What does the countrywide extract give for {label}?", "Across the nation, {label} comes to what?"],
    "metric.idx_nat": ["Relative to countrywide, {label}?", "Nationwide relative standing on {label}?",
                       "Where does the account sit against the nation on {label}?", "Countrywide relative reading for {label}?"],
    "cxs.band": ["Latest-year {cls} volume puts the account in which band?", "Band attained on recent {cls} doses?",
                 "Recent {cls} doses unlock which band?", "Top band unlocked by the account's latest-year {cls} volume?"],
    "cxs.commit": ["Minimum take for {cls}: satisfied by latest-year doses?", "Latest-year {cls} doses versus the minimum take: satisfied?",
                   "Has the account cleared its {cls} minimum take over the latest year?", "Minimum take cleared for {cls}?"],
    "cxs.floor": ["Second-window {cls} portion for {party}: at the minimum or better?", "Preferred-position minimum honoured by {party} in the second window?",
                  "Second window, {cls}: does {party} clear its minimum portion?", "Is the minimum portion for {party} cleared in the second window?"],
    "cxs.switch": ["Biggest {cls} product gainer across windows?", "Across windows, which {cls} product climbed furthest?",
                   "{cls}: top gaining product from first to second window?", "Which product led {cls} drift across windows?"],
    "refuse.pricing": ["Ideal price point to put to {party} for {cls}?", "Best discount level to request from {party}?",
                       "Where ought {cls} pricing land in the next round?", "Rebate figure to aim for in talks with {party}?"],
    "refuse.clinical": ["{b1} versus {b2}: which is the safer pick?", "Clinically, does {b1} beat {b2}?",
                        "Efficacy edge between {b1} and {b2}?", "Which carries less risk for patients, {b1} or {b2}?"],
    "refuse.real_data": ["Actual, non-synthetic dollars for the account?", "Genuine sales history behind the account, please?",
                         "Real-world dose counts for {name}?", "True invoice totals for the account?"],
})
B["answers"].update({
    "metric.system": "Exhibit figure: {S1}.", "metric.state": "Same-state comparator figure: {S1}.",
    "metric.national": "Countrywide figure: {S1}.", "metric.idx_nat": "Nationwide relative reading — {S1}.",
    "cxs.band_yes": "Band attained: the one opening at {S1} doses (latest-year volume {S2}).",
    "cxs.band_no": "None attained; the opening band needs {S1} doses against latest-year volume {S2}.",
    "cxs.commit_true": "Satisfied: latest-year volume {S2} versus minimum take {S1}.",
    "cxs.commit_false": "Not satisfied: latest-year volume {S2} versus minimum take {S1}.",
    "cxs.floor_true": "Cleared: second-window portion {S2} against minimum {S1}.",
    "cxs.floor_false": "Not cleared: second-window portion {S2} against minimum {S1}.",
    "cxs.floor_none": "Unmeasurable second-window portion ({S2}); minimum {S1}.",
    "cxs.switch": "Group {S2}: top gainer recorded as {S1}.",
})
