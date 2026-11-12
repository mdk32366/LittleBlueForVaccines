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
