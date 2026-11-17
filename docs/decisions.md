# decisions

Populated by the first build PR.

## Generator (gen/, PR 1)

Project-local decisions for gen/ (BIA 562), numbered by Trinity 2026-11-12. These numbers are local to this repository and are not the program-level decision log; where a number collides with a program-level decision (for example D-0027), the entry below governs only this project.

- **D-0023 (slot tokens exempt from digit rule):** slot tokens are exempt from the digit rule. "Tier 2" in answer prose stays rejected; carry the label in a span. (AS-0018, F-0005)
- **D-0024 (family scope):** a family covers both the doc text and the question phrasing.
- **D-0025 (family split):** train is A-only and test is B-only, with no cross cells. (AS-0016)
- **D-0026 (no shared 4-word phrase):** A and B share no 4-word phrase. (T-0031, F-0006)
- **D-0027 (refusal string):** the refusal string is exactly "not in the contracts".
- **D-0028 (seam additions):** the seam gains plan(system, rng, family), families and template_text. (AS-0023)
- **D-0029 (synthetic supplier and products):** the supplier is "Synthetic Supplier Co." and products are PRD-syn-*. (AS-0014, AS-0015)

## Gap rulings (Trinity 2026-11-12)
- **G-04:** the spans dict is canonical; the single `span` is dropped. (AS-0019, resolved)
- **G-06:** the ontology spec governs; there is no `proposed_to` edge. (AS-0020)
- **G-07:** a 25% hold-out is OK. (AS-0016)
- **G-13:** one qa.jsonl per split is OK. (AS-0025)
- **G-15:** the anchor grammar is digits and dots (`\d+(\.\d+)*[a-z]?`).
- **G-18:** T-0028..T-0033 are confirmed (docs/testplan.md).
- **G-09 / G-10:** accepted as built (V2 via project-grammar rule; V4 tested on a temp `src/brief/leafstore/`).
- **G-11 / G-16 / G-17:** out of scope for this order.

## App (app/, PR 2)

Project-local decisions for app/ (BIA 562), logged from Matt's rulings via Trinity, 2026-11-12. Like the generator entries above, these numbers are local to this repository and are not the program-level decision log.

- **D-0032 (Streamlit reports):** Streamlit is the UI. Pick a health system, see the brief with its charts, ask about the contracts with cited spans, and download a one-page PDF report (matplotlib).
- **D-0033 (name):** Matt, 12:19 PT: "Call the project, and the system, 'Little Blue for Vaccine Sales'". The exact string goes in the page title, the page header, the PDF header and the README. Proposed repo slug: little-blue-vaccine-sales.
- **D-0034 (national file public-real):** Matt, 12:25 PT: "Treat it as public and real". This amends D-0022 (fake data) for that file only. BENCHMARK=national may read it; synthetic peers stays the default and the fallback. It is never training input (T-0025 kept).
- **D-0035 (real names, fake grounding):** Matt, 12:31 PT: "Use them.  They are public companies with public data.  What is fake is the grounding data.  Go". Real manufacturer and product names may appear in the UI, charts and PDFs. Contracts, proposals and Q&A (gen/out) stay synthetic. The guardrails are unchanged: no pricing advice, no efficacy or safety claims, system isolation.
- Applied, not new: D-0004 (single-figure PDF), D-0009 (denylist), D-0022 (fake data), D-0023 (slot tokens exempt from digit rule; applied to fact tokens), D-0027 (refusal string).

## Review rulings (Trinity, PR 3)
- gen/out documents still carry the stamp "(D-0022)" as a bare number. It stays for now: `STAMP` in `gen/bia562gen/generate.py` gets fixed in the GATE 2 regeneration on Sat 11/14, which also changes the manifest. PR 3 does not touch gen/out or the manifest.
- Assumptions AS-0028 to AS-0038 accepted (deferrals in assumptions.md); AS-0039 open follow-up; T-0035 to T-0037 confirmed; F-0008 to F-0013 accepted.
- AS-0040 (expired rule) and T-0038 (expired marker) confirmed as numbered. Open: auto-renewing MSAs still show `[EXPIRED]`; `[ENDED]` versus exemption to be ruled at wire-in.
- GATE 2 ruling (Trinity): auto-renewing expired MSAs show `[TERM ENDED · auto-renews]`, field-based (AS-0040 amendment); AS-0041 (schema_v1 keeps auto_renew boolean in term section) added, owned by Trinity. T-0039 (auto-renew split) and T-0040 (Brief-tab marker) confirmed as numbered; T-0041 (auto_renew bool schema guard) added as its own file; label hyphen is U+2011 (renders in the PDF font).
- GATE 2 STAMP fix: `STAMP` in `gen/bia562gen/generate.py` now reads "Fictional test data generated for BIA 562 under D-0022 (fake data)." gen/out carries it from the GATE 2 regeneration on; the regeneration commit records the new manifest.

## v0.2
- **D-0036 (v0.2 scope):** Accepted 2026-11-13 11:42 PT. The owner: "Generate a version 0.2 of this application (little blue)". Scope as in the spec `docs/spec-v0.2.md` §0 and §9: brief comparison, must-cover talking points from computed numbers, voice notes, and a Salesforce-shaped payload with a simulated send to SQLite, looked up by rep + date + company.
- **D-0039 (v0.2 deploy GO):** Accepted 2026-11-13 11:49 PT. The owner: "GO covers v0.2 build, merge, and deploy to [the app server]" (bracket: editorial redaction of a server hostname). Little Blue only; each merge and each deploy still needs the Architect's approval. The deploy plan is kept outside this repository.
- **D-0037 (no real Salesforce):** Accepted 2026-11-13 14:26 PT. The owner: "No actual send. Just create the payload and place it into a database record." No Salesforce network calls, client library or credentials. The payload is stored as a database record only (AS-0057 (sf payload is a database record, not a send)).

## GATE 2 path B: schema_v1 (spec v1.1)
- **Supersessions:** D-0034 (national file public-real) is superseded for the training scope by D-0041 (the file stays public-real; its app benchmark use is unchanged). D-0029 (synthetic supplier and products) is superseded for the training scope by D-0043 and for the counterparty by D-0044. T-0025 is retired for gen by D-0042.
The owner's answers of 2026-11-13, verbatim. At 4:54 PM PT: "Still on, but invent the data that is missing for training purposes. That way we know the answers before we ask the questions. Per-system works. Why can't the national file feed the generator? Real brand names are allowed, and their information is public. 5. OK. Use defaults." On the follow-up card: "Yes, let the national file feed the generator for training." On the R1 card, 4:57 PM PT: "Name real manufacturers as the contract party." At 4:58 PM PT: "This is a proof of concept, and it is for demo purposes only in the context of a class project.  This will not be used by the public in any way shape or form."
- **D-0041 (national file is generator and training input):** the owner: "Yes, let the national file feed the generator for training." Supersedes D-0034 (national file public-real) for the training scope. `gen/bia562gen/national.py` reads the national file (only its ten listed columns), checks its sha256 against the recorded value and fails closed when the file is missing, altered or short of a column; there is no fallback to synthetic peers. Its pooled figures appear in every EXH1 (§11, §12) and may be training input. gen/out holds no national row. The file stays public-real and the app's benchmark use is unchanged. Tests: T-0065, T-0066.
- **D-0042 (T-0025 retired for gen):** follows from D-0041. T-0025 (national file never training or gen input) is retired for gen and replaced by T-0065 (national used as specified) and T-0066 (train_guard: the national file only by its recorded sha256). The other refusals stay: visit records and DBs (T-0051) and any other non-synthetic file.
- **D-0043 (real names in generated data):** the owner: "Real brand names are allowed, and their information is public." Supersedes D-0029 (synthetic supplier and products), AS-0014 and AS-0015 for the training scope: real manufacturer and product names from the input files may appear in generated documents and Q&A. The D-0035 guardrails stay: no pricing advice and no efficacy or safety claims (T-0068).
- **D-0044 (real manufacturer as the contract party):** the owner: "Name real manufacturers as the contract party." Also supersedes D-0029 for the counterparty; "Synthetic Supplier Co." is retired. Each invented contract names as its party the top-dollar manufacturer of the system's primary class (FULL window, ties by name), and covers only that manufacturer's brands (T-0074). The terms stay invented and stamped synthetic (D-0022 (fake data)); every document carries the fixed marker "SYNTHETIC TRAINING DOCUMENT. NOT A REAL AGREEMENT. Terms are invented." as its header line and as its footer line after a rule, the manifest has `contract_terms: "invented"` and every Q&A row has `terms_invented: true` (T-0073). Scope, the owner at 4:58 PM PT: "This is a proof of concept, and it is for demo purposes only in the context of a class project.  This will not be used by the public in any way shape or form." The residual risk is accepted in AS-0069 (accepted risk: real manufacturer as the party to invented terms).
- **Spec v1.1 §5.3 amended (the Architect's GATE 2 ruling):** "terms_invented: true on every qa row", replacing "on every qa row citing a contract anchor". The repository does not carry the spec; this entry, D-0044, T-0073 and architecture.md restate it.
- **Defaults applied ("Use defaults"):** a single refusal string, still exactly "not in the contracts" (D-0027 (refusal string)), refusal kinds told apart only by `question_type`; switching compares the same-season windows 202410-202503 and 202510-202603 at a 15-point share change (AS-0064); the seam gains a `num` field and answer type (a seam addition like D-0028).

## v0.2-f Salesforce dry run (app/)
- **D-0045 (Salesforce dry run):** Accepted 2026-11-14 06:54 PT. The owner's selections: "GO on the Salesforce dry-run build and Deploy-4 after GATE 2"; "Yes, re-root on Visit__c"; "Save setup in the app DB, non-secret fields only". The Architect's build order v0.2-f follows (07:38 PT). D-0037 (no real Salesforce) and AS-0057 (sf payload is a database record, not a send) stand unchanged: there is still no Salesforce connection, no client library, no credentials and no network call. What changes:
  - New saves use payload lb-sf-tree-0.3, rooted on Visit__c (AS-0070 (sf payload lb-sf-tree-0.3, Visit__c root)). Rows saved before keep lb-sf-tree-0.2 and still read back (AS-0049 (sf payload field names) describes that shape).
  - A new "Integration (dry run)" tab saves a setup with non-secret fields only, append-only in the app DB (AS-0071 (dry-run setup, non-secret fields only)).
  - The Visit record tab shows "Preview Salesforce request" after a save or a lookup: the requests a real integration would make, as text and a download. Nothing is sent, and no action is labelled Send.
  - Guards: T-0047 (updated), T-0077 to T-0080.

## 6c one Composite request (app/)
- **D-0046 (one Composite request, allOrNone):** the Architect's PR 12 review, ruling 1 ("Follow-up 6c: switch the dry run from three Composite Tree requests to one POST /composite request with allOrNone=true"). The owner's GO for the next task after a green Deploy-4. D-0045 (Salesforce dry run), D-0037 (no real Salesforce) and AS-0057 (sf payload is a database record, not a send) stand: nothing is sent, and there is no client, credential or network call.
  - "Preview Salesforce request" shows ONE request, `POST {instance}/services/data/v{api}/composite`, body `{"allOrNone": true, "compositeRequest": [...]}`, in the order and with the bodies of AS-0072 (composite subrequest mapping). The Visit__c is first (referenceId `visit`); the outcomes, the Event and every Task point at `@{visit.id}`, which now resolves inside the one request. This closes F-0033.
  - At most 25 subrequests (Salesforce's Composite limit). More is refused with a clear error and no preview; the payload is still stored.
  - **Preview-only, no new payload version.** The stored lb-sf-tree-0.3 tree (AS-0070) already holds every record, its referenceId, the Account external-id relationship and `WhatId` = `@{visit.id}`. Only the outcome's master-detail field is missing, and that is a setup name, not visit data. So stored payloads, their `schema_version`, their sha256 and the visit file are unchanged, and every 0.3 row saved under v0.2-f previews as one Composite request. 0.2 rows still show "No preview".
  - The setup gains one non-secret field, `outcome_parent_field` (AS-0072).
  - The headers, the `Bearer <NOT CONFIGURED>` placeholder, the curl text, the request-set download (now `lb-sf-dryrun-requests-0.2`), the DRY RUN banner and the no-Send rule are unchanged.
  - Guards: T-0078 (updated), T-0081 and T-0082.

## v0.2-g missed talking-point follow-up (app/)
- **D-0047 (missed talking-point follow-up):** the owner, 10:46 PT 11/14: "I'll need visit narratives to test the feature. Probably five should do it. Pick the facilities, and intentionally miss some talking points. The system should then ask you what about the ones not covered? (Mark as not addressed with a reason, or give another chance to address the ones missing.)" The Architect's spec v0.2-g and G0 rulings follow. D-0045 (Salesforce dry run), D-0046 (one Composite request, allOrNone), D-0037 (no real Salesforce) and AS-0057 (sf payload is a database record, not a send) stand: nothing is sent.
  - After the notes are typed (or pre-filled by voice), the hint pre-fills each talking point as Raised, Partially or Not raised (AS-0073 (three-state hint)). The rep confirms or changes each one.
  - A "Not covered yet — What about these?" panel lists every point that is not Raised. For each, the rep picks (A) "Mark not addressed" with a reason from a fixed list (AS-0075 (reason pick list)), or (B) "Address now": a typed addendum, checked with the same hint **only for the (B) points and only on the addendum text**. A point that comes back Raised leaves the panel; the rest return to it. Rounds repeat with no limit, and the status never goes down. Covered points are never asked about again.
  - Save is disabled, with an inline warning naming the keys, until every point is resolved. Nothing is resolved by a silent default: neither the path nor the reason is pre-picked. `visits.save_visit` refuses an unresolved outcome itself (ValueError), and the lb-sf-tree-0.4 schema refuses it a third time (AS-0074 (lb-sf-tree-0.4 and visit file 0.3)).
  - Every point ends as Raised, Partially with a reason, or Not raised with a reason. Each addendum round is added to the saved notes as `Addendum n: …`, and the point is stored with `addendum` true.
  - Save loaded visit goes through the same gate, with path (A) only: the notes of a past visit are not extended.
  - The status values are the existing Addressed values. "Partially" already existed in the payload and file schemas; v0.2-g adds a way for the hint to pre-fill it and the reason fields, not a new value.
  - The owner's two §14 questions are built with the Architect's defaults, which the owner can override: a manual switch to Raised needs no evidence quote (AS-0076 (manual Raised)), and the five-item reason list stays as written (AS-0075).
  - Test inputs: five synthetic narratives in `app/tests/fixtures/narratives/` with their planted coverage in `expected.md` (T-0084, T-0088).
  - Guards: T-0083 to T-0088; T-0046_stt_ui, T-0047, T-0048, T-0059, T-0060, T-0080 and T-0082 amended.

## v0.2-h1 rule-based auto-fill of the evidence quote and follow-up (app/)
- **D-0048 (auto-fill visit fields, rules part):** the owner, 11:28 AM PT 11/14: "for a given visit, the UI should automatically load the talking points for that visit so when the salesperson logs the visit, it will automatically fill in the fields for each point." And on the 11:51 AM PT card, Q1: "No, wait for the LLM before shipping Customer response auto-fill." The Architect's spec v0.2-h1 (@0.2) follows. D-0047 (missed talking-point follow-up), D-0045, D-0046, D-0037 (no real Salesforce) and AS-0057 stand: nothing is sent, and no model is used.
  - When the rep logs a visit, every Raised or Partially talking point gets two suggested fields from the notes, by deterministic rules: the **Evidence quote** (verbatim, AS-0077 (evidence quote rule)) and the **Follow-up** (only when the text has a cue, AS-0078 (follow-up cue rule)). A point that an addendum lifted (D-0047 path B) is filled from the addendum text only. Not raised points get nothing; they go to the "Not covered yet" panel as before.
  - Each filled field is labelled "auto (rule-based)" under one fixed caption: "Suggestions from keyword rules. Review every value before saving. Accuracy has not been measured." No accuracy is claimed (AS-0079 (error rate unmeasured)).
  - **Edits win.** A field the rep changed is `edited` and is never written again, through any re-run (notes changed, hints re-run, addendum checked). Nothing reaches the store before Save.
  - **Customer response is not auto-filled** (owner's Q1; deferred to v0.2-h2, design only). **Quality (score) is never auto-filled.** Both keep today's widgets and defaults.
  - Provenance (`auto-rule`, `edited`, `none` per field) is app-side only: `visits.outcomes_json` and the visit file lb-visit-file-0.4; the payload stays lb-sf-tree-0.4 and the Salesforce mapping is unchanged (AS-0080 (provenance is app-side)).
  - Every non-empty follow-up is one Task, so a 7-point visit with every follow-up filled is 16 Composite subrequests, within 25 (AS-0072).
  - In the same build (PR 14 review follow-ups): the 'Not covered yet' state of a system is cleared on Save (N7); save_visit's own refusal and the 'Save loaded visit' gate get tests and mutations of their own (N4, N5); the gap helper in the tests is batched (N1) and every test run has a per-test timeout (N2, F-0031; pytest step 15 minutes, red-proof step still 45).
  - Guards: T-0089 to T-0093; T-0085, T-0086, T-0087 and T-0088 amended.

## v0.2-h2 Gate 1: Bluebird Customer response, flagged OFF (app/)
- **D-0049 (Bluebird Customer response, flagged):** the owner, 7:27 PM PT 11/16: "Certify 0.C as a pass; 199/200 valid and ±1 vs laptop are acceptable." and "GO on Gate 1." The Gate 1 brief: a feature-flagged Bluebird backend, default OFF, following the intent of the v0.2-h2 @0.3 design draft: a sidecar-shaped client, Customer response only, talking points stay templated, edits win, and a model that is down never silently saves Neutral. No weights in the repository, no sidecar deployed, and the flag is on in no deploy file. D-0048 (auto-fill, rules part), D-0047, D-0045, D-0046, D-0037 and AS-0057 stand: nothing is sent to Salesforce.
  - **Flag:** `LB_BLUEBIRD`, read on every run by `config.bluebird_on()`. Only the value `on` (any case, surrounding spaces ignored) switches it on; unset or anything else is off. `config.LLM_MODE` stays `"off"`, and the Brief and Talking points tabs do not change either way.
  - **Flag off:** today's app, unchanged. app.py does not import the client, `visit_tab.render` gets no response provider, Customer response defaults to Neutral, and there is no Bluebird button or caption.
  - **Flag on:** the Visit record tab gets a "Suggest Customer responses (Bluebird)" button. One click asks the sidecar once per Raised or Partially point (the auto-fill's status, so a Not raised pick withdraws; F-0040) and fills only the Customer response box. The Evidence quote and Follow-up stay rule-based (D-0048), Quality is never filled, and Not raised points are never sent.
  - **No silent default:** with the flag on, no Customer response is pre-picked. Save stays disabled, with a warning naming the keys, until every point's response is picked by the rep or filled by the model (AS-0083 (model down is not Neutral)).
  - **Edits win:** a response the rep picked is `edited` and is never overwritten by a later click. A model value made from notes that have since changed is withdrawn, and the rep is told to click again.
  - **Sidecar-shaped:** the client (`brief/bluebird.py`) talks to a separate model server over plain HTTP at `LB_BLUEBIRD_URL` (no default) (AS-0081 (sidecar, no weights here)). The visit tab and the store never import it; app.py injects it only when the flag is on.
  - **No accuracy is claimed** for this use (AS-0082 (response suggestions unmeasured)).
  - Guards: T-0094 to T-0096.
- **D-0050 (Bluebird Contract Q&A, flagged):** the owner, 2026-11-17: Bluebird should work in the Contract Q&A tab, and the interface should show it. Contract Q&A is the task Bluebird v1.0 was trained and evaluated on, so it uses the same flag and sidecar as D-0049 (`LB_BLUEBIRD`, OFF by default; AS-0081). With the flag off the tab is unchanged: TermSet lookup, LLM off. D-0027 (refusal string), D-0009 (no pricing advice) and system isolation stand.
  - **Interface:** with the flag on, the page caption and the tab heading say Bluebird; an **Ask Bluebird** button sends the question once; the checked answer is shown with each quoted span in bold and its cited clause; the rule-based TermSet lookup stays under it for comparison and as the fallback. Nothing is sent before the click.
  - **Prompt = training prompt:** the training system text and user turn on the Qwen2.5 template, with the Gate 0 bench's greedy settings and JSON-slot grammar, over clauses of ONE system chosen to mirror the training document sets (AS-0084 (Q&A clause choice)).
  - **Nothing unchecked is shown** (AS-0085 (Q&A answer checks)): an answer whose quoted spans are not word for word in the clauses sent, or with a stray number, mismatched slots or commercial advice, is rejected and not shown. Pricing-advice questions are refused without asking the model.
  - **Accuracy is stated, not hidden:** measured through this tab's own path on the 0.C 200-question sample (laptop CPU, the same GGUF): 132 right (66%); 133 answers shown, 41 of them wrong; 50 refusals; 17 rejected; median 4.9 s, p95 11.5 s per question. The Gate 0 bench, which sent the exact training prompts, scored 152/200; the gap is the clause choice (AS-0084). By route: contract 80/113, exhibit 38/53, proposal 5/11, amendment 4/5, cross-document 4/18. The tab states these figures, warns on every cross-document answer, and keeps the TermSet lookup alongside. A checked span proves the quote is real, not that it answers the question.
  - **D-0023 kept:** the digit rule rejected 9 of the 200 answers, 7 of which were otherwise right ("Band 2 is reached after {S1} doses"). Allowing a number the question itself contains would recover them; that is a change to D-0023 and is left to the owner and the Architect.
  - Guards: T-0097, T-0098.
