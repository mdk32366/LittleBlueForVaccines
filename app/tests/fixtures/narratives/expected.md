# expected.md — planted coverage for five visit narratives

How the talking points were obtained: `brief.talking.payload_points(system_id, fsets)` / `brief.talking.build(fs)`, the same provider the Visit record tab uses (`app/app.py` passes `partial(talking.payload_points, fsets=fsets)` into `visit_tab.render`). `fsets` came from `client_metrics.compute_all(clean.clean(load.load_csv(config.DATA_PATH)), nat=benchmark.national_profile())` on the synthetic sales file plus the national file. Evidence: `evidence/selected_points.json` and `evidence/how_points.py`.

The notes are plain text in the form the Visit record tab takes in: the `Visit notes (typed)` text area (`visit_tab.render`, key `vr_notes`). A voice transcript, when STT is available, only pre-fills that same box. The tab's file uploader accepts a saved visit JSON, not a narrative file.

Each committed narrative starts with the marker line `FAKE-SYNTHETIC demo visit note: synthetic data, roles only.` (T-0088); the marker does not change any hint. Word counts below are for the note without the marker.

Planted coverage below is the human intent for each note. It is not the app's hint result. The local run is in `evidence/local_run.md`.

Coverage values: **covered**, **missed**, or **partial**.

---

## 1. All points covered (control)

- **File:** `narratives/01-SYNCP000025-all-covered.txt` (302 words)
- **Facility:** SYNCP000025 · Sunrise Care Partners 025
- **State / org type / main facility type:** FL · IDN · Primary Care (48.8% of dollars)
- **Book:** about $834.7K net
- **Contract:** live MSA, expires February 28, 2027; auto-renew is false ("does not renew automatically")
- **Switching:** flagged (hepatitis manufacturer share move)

| Key | Talking point (app text) | Planted | Covering sentence |
| --- | --- | --- | --- |
| fixed.A1 | Size: $834.7K in net dollars, 17.8% of the in-state total (synthetic peers, n = 7), and 0.0028% of national dollars. | covered | The book is about $835K in net dollars, a solid slice of the in-state total among the synthetic peers and a small slice of national dollars. |
| fixed.A2.1 | Top class: Pneumococcal leads at 49.3% of dollars against 21.5% nationally, an index of 229. | covered | We spent most of the visit on pneumococcal, which leads the mix at roughly half of dollars, well ahead of the national share, with a high index versus both the national file and in-state peers. |
| fixed.F5 | Share move: MERCK & COMPANY in Hepatitis moved from 78.9% to 48.0% of class doses between the two windows. | covered | On hepatitis, the share for Merck & Company moved down sharply between the two windows (from the high seventies to under half of class doses). |
| must.R2 | Must cover: HPV to MenACWY + MenABCWY doses is 0.21 for this system against 1.26 for the pooled national file (45,462 rows), an index of 17. | covered | HPV to MenACWY plus MenABCWY doses is low for this system against the pooled national file, and they agreed the adolescent platform needs a closer look before the next school cycle. |
| must.A2.4 | Must cover: dollar share of Shingles is 6.4% for this system against 1.1% for synthetic in-state peers (n = 7), an index of 595. | covered | Dollar share of shingles is well above in-state peers; they want to hold that volume and asked for a short peer comparison. |
| must.A2.1 | Must cover: dollar share of Pneumococcal is 49.3% for this system against 17.2% for synthetic in-state peers (n = 7), an index of 287. | covered | We also confirmed the pneumococcal dollar share versus in-state peers, which is the other must-cover on the mix. |
| question.F2 | Question to ask: what is driving purchasing in Pneumococcal, and which programs are planned for next season? | covered | I asked what is driving purchasing in pneumococcal and which programs are planned for next season. |

---

## 2. Misses one point

- **File:** `narratives/02-SYNCP000031-miss-one.txt` (326 words)
- **Facility:** SYNCP000031 · Highland Pediatric Center 031
- **State / org type / main facility type:** TX · IDN · Women's Health (43.0% of dollars)
- **Book:** about $766.3K net
- **Contract:** live MSA, expires May 31, 2028; auto-renew is false; a share-floor amendment is on file
- **Switching:** flagged (influenza manufacturer share move)
- **Deliberately missed:** must.A2.2 (dollar share of DTaP). The note never names DTaP.

| Key | Talking point (app text) | Planted | Covering sentence |
| --- | --- | --- | --- |
| fixed.A1 | Size: $766.3K in net dollars, 3.9% of the in-state total (synthetic peers, n = 32), and 0.0026% of national dollars. | covered | I opened with the size of the book: about $766K in net dollars, a few percent of the in-state total (there are many synthetic peers in the state) and a small slice of national dollars. |
| fixed.A2.1 | Top class: Shingles leads at 42.1% of dollars against 4.3% nationally, an index of 975. | covered | The top class is shingles, which leads at a little over two fifths of dollars, far ahead of the national share and with a very high index versus in-state peers. |
| fixed.F5 | Share move: GSK PHARM in Influenza moved from 0.0% to 100.0% of class doses between the two windows. | covered | On manufacturer mix, GSK Pharm in influenza moved from none of the class doses in the first window to all of them in the second. |
| must.R5 | Must cover: Shingles to adult-labelled Influenza doses is 20.68 for this system against 0.17 for synthetic in-state peers (n = 32), an index of 12037. | covered | We spent the middle of the visit on that dollar share and on the must-cover ratio: shingles to adult-labelled influenza doses is far above the in-state peer figure. |
| must.A2.1 | Must cover: dollar share of Shingles is 42.1% for this system against 3.5% for synthetic in-state peers (n = 32), an index of 1210. | covered | The top class is shingles, which leads at a little over two fifths of dollars, far ahead of the national share and with a very high index versus in-state peers. |
| must.A2.2 | Must cover: dollar share of DTaP is 12.4% for this system against 3.6% for the pooled national file (45,462 rows), an index of 347. | missed | We did not get to the other must-cover item on today's list. Time ran out after the shingles and influenza discussion, and I did not open the remaining mix point. |
| question.F2 | Question to ask: what is driving purchasing in Shingles, and which programs are planned for next season? | covered | I asked what is driving purchasing in shingles and which programs are planned for next season. |

---

## 3. Misses two points

- **File:** `narratives/03-SYNCP000083-miss-two.txt` (271 words)
- **Facility:** SYNCP000083 · Cedar Valley Physician Alliance 083
- **State / org type / main facility type:** MI · IDN · Urgent Care (72.9% of dollars)
- **Book:** about $1.86M net (the largest book in this file)
- **Contract:** MSA expired May 31, 2026 (`[EXPIRED]`); auto-renew is false ("No rollover occurs"); a share-floor amendment is on file
- **Switching:** no material switching
- **Note:** this system has too few in-state peers for an in-state size share, so `fixed.A1` includes the words "too few" and "comparison" (unlike the other four, whose size points have no hint keywords).
- **Deliberately missed:** fixed.F5 (switching) and must.A2.3 (dollar share of Influenza). The note avoids the words "switching", "material", and "influenza".

| Key | Talking point (app text) | Planted | Covering sentence |
| --- | --- | --- | --- |
| fixed.A1 | Size: $1.86M in net dollars, in-state comparison: too few in-state peers, and 0.0063% of national dollars. | covered | In-state comparison is limited: too few in-state peers to show a state share, so I used the national dollars figure (a small slice of the national file) when we talked scale. |
| fixed.A2.1 | Top class: RSV leads at 70.1% of dollars against 5.3% nationally, an index of 1332. | covered | RSV leads the mix at about seven tenths of dollars, far ahead of the national share, with a very high index. |
| fixed.F5 | Switching: no material switching between the two windows. | missed | I did not get to every must-cover item or to manufacturer-window moves; the visit stayed on scale and the RSV block. |
| must.R6 | Must cover: RSV Vaccine to adult-labelled Influenza doses is 0.00 for this system against 0.08 for the pooled national file (45,462 rows), an index of 3. | covered | I also walked the other RSV must-cover: RSV vaccine to adult-labelled influenza-season doses is near zero for this system against the national file. |
| must.A2.1 | Must cover: dollar share of RSV is 70.1% for this system against 5.3% for the pooled national file (45,462 rows), an index of 1332. | covered | That dollar share of RSV was the first must-cover item, and the operations lead said urgent care traffic is where most of that volume shows up. |
| must.A2.3 | Must cover: dollar share of Influenza is 3.9% for this system against 14.8% for the pooled national file (45,462 rows), an index of 26. | missed | I did not get to every must-cover item or to manufacturer-window moves; the visit stayed on scale and the RSV block. |
| question.F2 | Question to ask: what is driving purchasing in RSV, and which programs are planned for next season? | covered | I asked what is driving purchasing in RSV and which programs are planned for next season. |

---

## 4. Misses most points

- **File:** `narratives/04-SYNCP000024-miss-most.txt` (247 words)
- **Facility:** SYNCP000024 · Pioneer Family Clinic 024
- **State / org type / main facility type:** TX · Corporate Owner · Pediatric Medicine (31.3% of dollars)
- **Book:** about $429.6K net (a smaller book)
- **Contract:** MSA ended December 31, 2025, and auto-renews (`[TERM ENDED · auto-renews]`); TermSet `auto_renew` is true
- **Switching:** no material switching
- **Deliberately covered only:** size (fixed.A1) and the switching status (fixed.F5). Mix, ratios, and the purchasing question are left for a later visit.

| Key | Talking point (app text) | Planted | Covering sentence |
| --- | --- | --- | --- |
| fixed.A1 | Size: $429.6K in net dollars, 2.2% of the in-state total (synthetic peers, n = 32), and 0.0015% of national dollars. | covered | I started with a scale snapshot only: about $430K in net dollars, a couple of percent of the in-state total among the synthetic peers and a small slice of national dollars. |
| fixed.A2.1 | Top class: Pneumococcal leads at 18.5% of dollars against 21.5% nationally, an index of 86. | missed | I did not open mix, class shares, or ratio pages, and I did not ask the purchasing-drivers question. |
| fixed.F5 | Switching: no material switching between the two windows. | covered | We then confirmed switching: no material switching between the two windows. |
| must.R5 | Must cover: Shingles to adult-labelled Influenza doses is 0.52 for this system against 0.19 for the pooled national file (45,462 rows), an index of 268. | missed | I did not open mix, class shares, or ratio pages, and I did not ask the purchasing-drivers question. |
| must.A2.3 | Must cover: dollar share of Hepatitis is 10.9% for this system against 4.7% for the pooled national file (45,462 rows), an index of 230. | missed | I did not open mix, class shares, or ratio pages, and I did not ask the purchasing-drivers question. |
| must.R6 | Must cover: RSV Vaccine to adult-labelled Influenza doses is 0.04 for this system against 0.08 for the pooled national file (45,462 rows), an index of 44. | missed | I did not open mix, class shares, or ratio pages, and I did not ask the purchasing-drivers question. |
| question.F2 | Question to ask: what is driving purchasing in Pneumococcal, and which programs are planned for next season? | missed | I did not open mix, class shares, or ratio pages, and I did not ask the purchasing-drivers question. |

---

## 5. One point only partial / vague

- **File:** `narratives/05-SYNCP000098-partial.txt` (294 words)
- **Facility:** SYNCP000098 · Lakeside Community Health 098
- **State / org type / main facility type:** MN · Corporate Owner · General Acute (35.3% of dollars)
- **Book:** about $665.3K net
- **Contract:** live MSA, expires November 30, 2027; auto-renew is false
- **Switching:** no material switching
- **Deliberately partial:** must.A2.3 (dollar share of Rotavirus). The name comes up, but the share and index are parked for a later call. Every other point is covered in full.

| Key | Talking point (app text) | Planted | Covering sentence |
| --- | --- | --- | --- |
| fixed.A1 | Size: $665.3K in net dollars, 10.8% of the in-state total (synthetic peers, n = 10), and 0.0023% of national dollars. | covered | Scale first: about $665K in net dollars, roughly a tenth of the in-state total among the synthetic peers and a small slice of national dollars. |
| fixed.A2.1 | Top class: RSV leads at 39.3% of dollars against 5.3% nationally, an index of 748. | covered | RSV leads the mix at close to two fifths of dollars, well above the national share, with a high index. |
| fixed.F5 | Switching: no material switching between the two windows. | covered | Switching was straightforward: no material switching between the two windows, and they did not dispute that. |
| must.A2.1 | Must cover: dollar share of RSV is 39.3% for this system against 5.3% for the pooled national file (45,462 rows), an index of 748. | covered | We walked the must-cover dollar share of RSV in detail, and the immunization lead agreed the general acute sites are where that volume concentrates. |
| must.A2.3 | Must cover: dollar share of Rotavirus is 8.7% for this system against 2.0% for the pooled national file (45,462 rows), an index of 437. | partial | Rotavirus came up only in passing. The pharmacy director said the name was on their list but they were not ready to talk about the dollar share versus the national file, did not want to walk the index today, and asked to park that point for a later call. |
| must.R1 | Must cover: MenB + MenABCWY to MenACWY + MenABCWY doses is 0.99 for this system against 0.49 for synthetic in-state peers (n = 10), an index of 203. | covered | We also covered the meningococcal must-cover in full: MenB plus MenABCWY to MenACWY plus MenABCWY doses is about double the in-state peer ratio. |
| question.F2 | Question to ask: what is driving purchasing in RSV, and which programs are planned for next season? | covered | I asked what is driving purchasing in RSV and which programs are planned for next season. |
