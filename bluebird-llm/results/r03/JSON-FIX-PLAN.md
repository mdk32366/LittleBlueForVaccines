# Bluebird T: the 11 malformed JSON outputs and the fix plan (2026-11-16)

Source: score/per_row.jsonl (from score/REPORT.md sha eecf22aa…d4e5) and out-T/predictions-bluebird-v1.0-e2.jsonl (sha 8b2fab15…fed3). All 11 are test rows.

## Breakdown
| Cause | Count | Rows |
|---|---|---|
| Truncated at the 128-token output cap (hit_max true, invalid_reason not_json); the model was quoting a long clause in full as span text | 7 | SYNCP000069/015/168/082/004 -Q12; SYNCP000134/040 -Q28 |
| Span written as a bare string instead of {anchor, text} (bad_span_key / bad_span_obj) | 3 | SYNCP000076/154 -Q21 (bad_span_key); SYNCP000023 -Q21 (bad_span_obj) |
| Answer omits a span slot it carries (slot_mismatch: S1 defined, only {S2} used) | 1 | SYNCP000174 -Q29 |

## Plan (Matt GO 5:08 AM PT, t394u)
1. Trinity specs one eval change: raise max_new_tokens (proposed 256) and add schema-constrained decoding so output must match the answer/spans JSON schema.
2. Kaylee reviews the change.
3. One full T rerun on the laptop with the new settings (about 70 min); each laptop step on its own Matt card.
4. Re-score with the same scorer pins; report the before and after side by side.

## Honest caveat for the class
Fixing all 11 clears the format gate (G-F) only. The accuracy floor (A-T, 0.7459 against an LB bar of 0.8149) would still fail, so the owner-override PASS (OWNER-OVERRIDE-T-PASS.md) is unaffected either way. Constrained decoding also changes how the model is run, so the after score measures the model plus the decoder, and has to be reported that way.

## Status
- Brief sent to Trinity: 2026-11-16 ~5:09 AM PT.
- E9 (deleting the laptop work dir) stays held until this rerun is done.
