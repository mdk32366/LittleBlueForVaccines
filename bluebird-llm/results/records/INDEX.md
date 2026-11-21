# Bluebird class pack — 16 November 2026

BIA 562 / Little Blue project. Consolidated documentation for the Bluebird LLM v1.0 post-run evaluation (run r03).

All times in the report are Pacific Time (America/Los_Angeles, UTC−8).

The Word report is the class-facing deliverable. The `sources/` folder holds the filed records it was compiled from, copied byte-identically and re-hashed on the box.

Status at pack time (version 2): scoring is complete; T is a PASS by owner override; the scorer verdict on the original T run remains DEGENERATE; the JSON-format fix rerun is filed as a reported result in the v2 Word report (not a re-certification). E9 is held. The 5:22 AM files, including `BLUEBIRD-EVAL-CLASS-REPORT.docx`, are left unchanged.

| File | sha256 | Description |
|---|---|---|
| `BLUEBIRD-EVAL-CLASS-REPORT.docx` | `b3710fd0a96c63bebbc4be605772f59e9f0568ec6c44bc67059245eedfaa463d` | Consolidated BIA 562 class report (plain English body, technical appendices) for the Bluebird v1.0 post-run evaluation, compiled 16 November 2026 from the packed sources. |
| `BLUEBIRD-EVAL-CLASS-REPORT-2026-11-16-v2.docx` | `5709adf8e60f238e5f6918c3e1961ebd487e112ec9538e6f4f54479c30d5f9f5` | Version 2 of the class report, same day: adds section 5.4 with the JSON-fix T rerun as a reported result (card t441s1566). The owner-override PASS remains the record. The 5:22 AM original is unchanged. |
| `sources/ADDENDUM-bluebird-eval@0.5-A1-A2@0.0.md` | `6402ac634d6c512483a37d3330d94fb05d0bef0a02e3c937b3cbdd3edbeafa1c` | Addendum that still applies: A1 power-scheme baseline for E8, and A2 required wording for the result note. |
| `sources/HOWTO-bluebird-llm@0.1.md` | `4faca3022d8b149de364a26addac758cf7fd39795d8f09edf91e85ea1fd64b3c` | Companion BIA 562 draft paper on how Bluebird was chosen and fine-tuned (draft @0.1; its training and eval sections were marked not yet run at the time of writing). |
| `sources/JSON-FIX-PLAN.md` | `4f431224056eb5942708f185fe08057dcb070786682b1b6adfa1c7624233b1b2` | Diagnosis of the 11 malformed T test outputs and the in-progress fix plan (cap raise, constrained decoding, T rerun, re-score). |
| `sources/REPORT-jf.md` | `37e79a121dd880493eac4ba694a048eb4cb9a215b7f982b4b7c39e5be2a950b4` | Before-and-after re-score of the JSON-fix T rerun (out-T-jf): format gate PASS, accuracy unchanged at 0.7459, strict verdict INCONCLUSIVE; reported result, not a re-certification. |
| `sources/ORDER-bluebird-eval@0.7.md` | `6c13d07eaf9f5184c51fd40129f07bb6afddc6c256c37de578a2ffafb219058a` | Governing evaluation order @0.7 (draft; live authorisations are the per-command cards), including the route A re-plan. |
| `sources/OWNER-OVERRIDE-T-PASS.md` | `b4f9e72aae2f5ed849a8382bc2c251709da4486ad0ddd9ceb031c83afd8a7631` | Certified owner-override record: T judged PASS on card t391s1356, with Matt's reason quoted and the scorer DEGENERATE verdict kept on the record. |
| `sources/REDO-S-route-A.md` | `a48baf6e458fb1fa9ea695a94f605267e5e4f8a25825a2d2126f9b59c778a61a` | Class write-up of the baseline (S) abort, root-cause analysis, route A redo, later results, owner override, and JSON-fix plan (sections 12-13). |
| `sources/RESULT-NOTE.md` | `2e7cf0a01016a8c38a8f5437a7e3fc0ab859289de96ec4491917fb449b06b769` | Filed result note for run r03, including the required A2 transformers 5.22.2 sentence, scoring summary, A1/E8 outcomes, and E9 held. |
| `sources/e5-b4-s1/E5-S-GATE-RECORD.txt` | `eabf1d905ab4d37b76a73aa34bbfd1bdba0e60d3dd54cab6c691f68d2a1f468c` | E5-S-gate record: Matt ruled route A on card t382s1311; gate PASS with a logged exception for the pre-existing littleblue-app server (pids 21896 and 2580). |
| `sources/e6-s4/E6-S4-poll-2026-11-16-0359PT.txt` | `2701a9c3b9b35737ad69d12595e6a961ca36baa745e5178682edd38da783a843` | Read-only mid-run poll of the route A batch-4 S rerun, about 3:59 AM PT, status running at 723 of 893 batches. |
| `sources/e6-s4/E6-S4-poll-2026-11-16-0455PT.txt` | `710e74dcb3b5783bc327dff4f8251b66222a1e9be187ec3894421436449714e1` | Read-only completion poll of the route A S rerun, about 4:55 AM PT: exit 0 at 04:26:34, peak_alloc 5,032,707,072 bytes, EVAL_DONE 3569. |
| `sources/score/REPORT.md` | `eecf22aad959fb80df64c40a87a01abf7bcff31fba92c82c5033a4fc6dfed4e5` | Pinned scorer's published report: T verdict DEGENERATE, decision bars, T and S metrics, and the paired T-versus-S comparison. |
| `sources/score/SCORES.json` | `cd0e9ac281a72dc504c30200ad398101d71c0eb5e9208350d5e74541a248478c` | Machine-readable score artifact for the same scoring run (bars, model metrics, pins, memorisation test). |

This INDEX.md was written after BLUEBIRD-EVAL-CLASS-REPORT-2026-11-16-v2.docx was saved and hashed. The 5:22 AM Word report and its hash are retained. SHA256SUMS lists every file in this folder. The zip, if built, is stored next to this folder, not inside it.

sha256 of this INDEX.md (hash of the content above this line): `e36ff1f7712c6a017e99a7484265dfdb3bbbb9de67bcc77b98f349f001f159f8`
