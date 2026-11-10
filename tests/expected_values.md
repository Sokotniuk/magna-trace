# D5 preparation — independent expected values

Prepared 2026-11-10 by Student D's preparation task. The H/K cases are synthetic hand-arithmetic cases, not Oracle observations, B2 examples or backend results. O01–O03 below separately record Student D’s redacted manual SQL verification report. No implementation was run to derive expectations. Hxx/Oxx are checklist identifiers, never evidence IDs. See [QA checklist](qa_checklist.md) for dependencies and conflicts.

## Hand-calculated expectations

Quoted inputs denote raw strings; `null` denotes an absent database value, not the string `"NULL"`. Values/limits below are unitless synthetic inputs with a known test unit supplied unless stated otherwise. Raw values must be preserved. Numeric results describe mathematical expectations; B2 must finalize JSON formatting and deviation fields for within-bounds/not-evaluable cases. “No breach” does not prescribe null versus zero on the wire.

All application comparisons are **PENDING EXECUTION**. Equality expectations are **PROVISIONAL** pending confirmation. Quality entries list relevant numeric flags; code semantics and absent-unit flags are additive, never replacements for range status.

| ID | Raw value | Raw lower | Raw upper | Independent reasoning / deviation | Expected range | Relevant numeric flags |
| --- | --- | --- | --- | --- | --- | --- |
| H01 | `"197.592"` | `"190"` | `"195.000"` | 197.592 − 195.000 = **2.592** | ABOVE | None |
| H02 | `"-0.500"` | `"0.000"` | `"1.000"` | 0.000 − (−0.500) = **0.500** | BELOW | None |
| H03 | `"0"` | `"0"` | `"1"` | Equals lower; no breach | WITHIN_RECORDED_BOUNDS (provisional equality) | None |
| H04 | `"1.0"` | `"0"` | `"1"` | 1.0 = 1 numerically; equals upper | WITHIN_RECORDED_BOUNDS (provisional equality) | None |
| H05 | `"8"` | `"8"` | `"8"` | 8 = both bounds; no breach | WITHIN_RECORDED_BOUNDS (provisional equality) | None |
| H06 | `" -0.5 "` | `"-1"` | `"0"` | Trim for parsing only; −1 < −0.5 < 0 | WITHIN_RECORDED_BOUNDS | None |
| H07 | `"0.300000000000000001"` | `"0"` | `"0.3"` | Exact subtraction = **0.000000000000000001** | ABOVE | None |
| H08 | Each of `""`, `"   "`, null | `"0"` | `"1"` | No numeric value; no numeric deviation | NOT_EVALUABLE | BLOCKED: MISSING (AGENTS) vs UNPARSEABLE for blanks (architecture); resolve C-2 |
| H09 | Each of `"abc"`, `"12mm"`, `"NaN"`, `"Infinity"`, `"1e3"` | `"0"` | `"1"` | Strict format rejects each; no calculation | NOT_EVALUABLE | UNPARSEABLE |
| H10 | Each of `"1,5"`, `"1.234,5"`, `"1 000"` | `"0"` | `"2000"` | Ambiguous separators rejected; do not normalize | NOT_EVALUABLE | UNPARSEABLE |
| H11 | `"5"` | `"10"` | `"1"` | 10 > 1 makes bounds invalid; no deviation | NOT_EVALUABLE | LIMIT_INVALID |
| H12 | `"5"` | null | null | No comparison possible | NOT_EVALUABLE | LIMIT_UNKNOWN |
| H13 | `"5"` | `"4"` | null | 5 ≥ 4; upper unknown; no recorded breach | WITHIN_RECORDED_BOUNDS | PARTIAL_BOUNDS |
| H14 | `"3.25"` | `"4.00"` | null | 4.00 − 3.25 = **0.75** | BELOW | PARTIAL_BOUNDS |
| H15 | `"5"` | null | `"6"` | 5 ≤ 6; lower unknown; no recorded breach | WITHIN_RECORDED_BOUNDS | PARTIAL_BOUNDS |
| H16 | `"6.125"` | null | `"6.000"` | 6.125 − 6.000 = **0.125** | ABOVE | PARTIAL_BOUNDS |
| H17 | `"5"` | `"abc"` | `"6"` | Lower bound cannot be parsed; do not guess a bound or result | BLOCKED pending A/B2 malformed-bound policy | Exact flags/status unspecified |
| H18 | `"5"` | `"0"` | `"10"` | 0 < 5 < 10; unit absent | WITHIN_RECORDED_BOUNDS | UNIT_UNKNOWN (range unchanged) |

Numeric equality cross-check: parsed `"1"` = parsed `"1.0"`; their difference is 0. This does not establish permission for an extension comparison; raw-limit and sample-count conflicts C-3 remain unresolved.

## Raw code independence

| Scenario | Inputs from above | Raw fail code | Expected independent outcome |
| --- | --- | --- | --- |
| K01 | H05, synthetic Screw Count example | `"1001"` | Within recorded bounds provisionally; preserve code; SEMANTICS_UNKNOWN; no PASS/FAIL. This reproduces a reported pattern only, not a verified Oracle row. |
| K02 | H05 | null | Same numeric outcome; preserve JSON null, unknown semantics, never PASS. Exact SEMANTICS_UNKNOWN flag blocked on C-4. |
| K03 | H01 | null | ABOVE, deviation 2.592; null does not suppress deviation or prove a failure-code meaning. Flag policy blocked on C-4. |
| K04 | H01 | `"1001"` | ABOVE, deviation 2.592; preserve code and SEMANTICS_UNKNOWN independently. |
| K05 | H06 | `"other-undocumented-code"` | Within recorded bounds; raw code unchanged with SEMANTICS_UNKNOWN; no diagnostic label derived from it. |

## Real Oracle measurement verification — redacted manual summary

**Provenance:** Student D reports manually verifying three measurements at station ST3003 in the real Oracle database using a read-only SELECT. O01–O03 now have **MANUAL SQL VERIFIED — Student D reported** status for the supplied values, upper limits and raw fail codes. The agent did not access Oracle; it independently checked the subtraction using Decimal from the supplied numbers. SQL execution date, query reference and external proof location were not supplied.

Only this authorized minimal summary is retained. No real serial numbers, complete Oracle rows, timestamps, row fingerprints, credentials or other confidential production details are stored. Oxx identifiers are QA slots, never Oracle keys or evidence IDs. No common incident or cause is inferred from the shared station or code.

| Slot | Measurement | Value | Upper limit | Independent upper-breach arithmetic | Raw fail code | Manual SQL status | API / chat shown result | Backend evidence ID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| O01 | Angle | 197.592 | 190 | 197.592 − 190 = **7.592** | 1001 | MANUAL SQL VERIFIED — Student D reported | PENDING API VERIFICATION / PENDING Copilot comparison | PENDING — no ID supplied |
| O02 | Vibration | 2.354 | 2 | 2.354 − 2 = **0.354** | 1001 | MANUAL SQL VERIFIED — Student D reported | PENDING API VERIFICATION / PENDING Copilot comparison | PENDING — no ID supplied |
| O03 | Motor Speed | 1350.457 | 1300 | 1350.457 − 1300 = **50.457** | 1001 | MANUAL SQL VERIFIED — Student D reported | PENDING API VERIFICATION / PENDING Copilot comparison | PENDING — no ID supplied |

Each supplied value exceeds its supplied upper limit. Expected range status is ABOVE when the full recorded bounds are valid; lower limits were not supplied in this redacted summary, so full bounds validation and the complete quality-flag set remain pending. Do not equate an omitted lower limit or unit here with a database NULL. Preserve raw code 1001 independently with unknown meaning (SEMANTICS_UNKNOWN); it never implies PASS/FAIL or explains the breach. Units, source timezone and lexical formatting beyond the supplied numbers are not established by this summary.

The synthetic H01 case intentionally retains its synthetic upper limit 195.000 and deviation 2.592; it is distinct from real-summary O01. All H01–H18 and K01–K05 cases remain unchanged and pending application execution. These three upper breaches do not verify the in-range Screw Count pattern or NULL-code behavior.

Remaining verification steps (not executed by this update):

1. A/B provide the repository, analysis and frozen API contract. Use a secure local verification context to identify the originally checked records; do not add real serials, complete rows or confidential production data here. Do not assume station + serial + BOOK_STAMP is a unique key.
2. Compare actual API values, limits, deviations, raw code and quality flags with O01–O03 and the full source bounds. Keep authorized source-row details outside Git; record only a redacted result here. Never fill gaps with synthetic results.
3. Record and resolve only backend-issued case-local evidence IDs once available. Confirm immutable source snapshots and calculation inputs; all evidence IDs remain PENDING until that happens.
4. Record API comparison and live Copilot comparison separately from Student D’s manual SQL verification. No module, API, Copilot or gate pass follows from this summary alone.

## Remaining work

B must publish B2 frozen schemas and tool/error example JSON, resolve contract conflicts with the relevant owners, and deliver B3–B6 evidence/cases/snapshot/API functionality and B7 mocked-repository API tests. A2/A3 repository and measurement logic remain dependencies for execution. Student D’s manual SQL verification of O01–O03 is recorded; full bounds/quality checks, expected-versus-API comparison and backend evidence resolution remain pending. C enables later real Copilot verification. No automated application tests, live failure runs, full D5 completion or gate passes are claimed by this update.
