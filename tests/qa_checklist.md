# D5 preparation — independent QA checklist

Prepared for Student D on 2026-11-10. Scope: D5 scenarios, independent expected-value tables and a redacted manual SQL verification summary supplied by Student D. Student D reports checking O01–O03 in real Oracle using a read-only SELECT; the agent did not execute Oracle queries. No module tests, API calls, tenant calls, D6 runs or gate verification were executed by this update.

Reconciled for D5 against the team-approved files in `/home/nikita/Documents/Важный_файл_Хакатон/`: `decisions.md` D03–D06 (dated 2026-11-10), `architecture.md` §§3–5/7 and `AGENTS.md` §7.2. Approval was confirmed by Student D. Repository source-document migration is outside this update; no source document is copied or changed. Decision approval settles expectations, not execution results.

## Completed preparation checks

- [x] Read `docs/AGENTS.md`, `docs/plan_v1.0.md`, `docs/architecture_v1.1.md` and `docs/product.md`; root `AGENTS.md` is empty.
- [x] Confirmed working branch is `feature/nikita`; initial working tree was clean.
- [x] Inspected repository file inventory: `backend/` contains only `.gitkeep`; no `backend/app/schemas.py`, B2 example JSON, or `copilot/openapi.v2.json` exists in this checkout. Architecture §3 is a proposed outline, not a published B2 freeze.
- [x] Confirmed `docs/decisions.md` and `docs/data-baseline.sql` are absent. Student D has now supplied the minimal manual SQL summary below; no complete row handoff is stored here.
- [x] Prepared synthetic hand-arithmetic expectations in [expected_values.md](expected_values.md) and three Oracle verification slots, now updated from Student D’s manual SQL report.

Checked preparation boxes above describe document/repository inspection. Manual SQL completion is separately attributed to Student D below. Every other scenario is **PENDING EXECUTION** unless explicitly marked **BLOCKED**. Later record PASS/FAIL, reviewer, date, actual result and a redacted proof reference; an unchecked box is never a pass.

## Missing dependencies and reconciled contract conflicts

| ID | Dependency / conflict | Required follow-up; current effect |
| --- | --- | --- |
| B2-1 | Frozen schemas and example JSON for every tool and error are absent. | B/B2 must publish request and response examples for open_case, get_evidence, record_answer, get_handover, list_stations and any enabled extension, plus errors. Contract assertions and example-driven mocks are BLOCKED. D does not author a replacement contract. |
| B2-2 | Envelope outline leaves field types, required/null fields, success/error exclusivity, HTTP mappings (apart from no-key 401), validation details, request limits and non-breach deviation representation unspecified. | B/B2 must specify these, including invalid/missing/stale question IDs, invalid answer bodies and evidence representation. Do not invent response fields, HTTP statuses or error codes. |
| C-1 | RESOLVED — approved `decisions.md` D03; `architecture.md` §§3/5. | Expect `CASE_NOT_FOUND_OR_EXPIRED` for unknown, expired and pre-restart case IDs. Do not accept the older `CASE_EXPIRED` alternative. Backend/API execution remains PENDING. |
| C-2 | RESOLVED — approved `decisions.md` D04; `architecture.md` §4; `AGENTS.md` §7.2. | Null, empty and whitespace-only numeric input → `MISSING`; nonempty invalid text → `UNPARSEABLE`. Unusable values/intervals → `NOT_EVALUABLE`; malformed/reversed bounds → `LIMIT_INVALID`; malformed nonempty numeric text is `UNPARSEABLE`. Only a missing counterpart permits a one-sided check with `PARTIAL_BOUNDS`. Execution remains PENDING. |
| C-3 | RESOLVED — approved `decisions.md` D06; `architecture.md` §7. | Documented P1 rule only: verified keys, same measurement, compatible recorded units and test/product context, Decimal-equal bounds and parseable values. Fix station/count distinct serials, or fix serial/count distinct stations; fewer than two → `NOT_COMPARABLE`, exactly two → `LOW_SAMPLE`, at least three → no low-sample warning if other criteria pass. Preserve row count, both distinct counts and time coverage; repeated rows add no independent entity. No P1 feature or execution scenario is introduced by this D5 reconciliation. |
| C-4 | RESOLVED — approved `decisions.md` D05; `architecture.md` §4. | Preserve original undocumented code strings and null; include `SEMANTICS_UNKNOWN` in both cases, independently of numeric range. Meaning remains unknown; no PASS/FAIL inference. Execution remains PENDING. |
| D-1 | Approved revisions are available externally; `docs/architecture.md`, `docs/plan.md` and `docs/decisions.md` are still absent from this checkout. | Use the approved external decisions cited above for this authorized reconciliation. Source migration remains with the team/integrator, outside these two files. Equality/strict parsing remain provisional under D09; units, timezone and keys remain open under D10. Approval does not prove runtime correctness or B2 delivery. |
| A/C prerequisites | A2–A4/A6, B3–B7 and C's protected live connector are unavailable in this checkout. | Execution waits for owner handoffs. Student D’s manual SQL check is recorded, but backend execution still waits for A’s repository/analysis and B’s cases/evidence/API handoffs. C provides real tenant/tunnel proof without secrets. |

C-1 through C-4 are reconciled using the approved decisions above. This closes their requirement ambiguity only; it does not mark backend/API/evidence checks passed. B2-1/B2-2 and implementation dependencies remain blocked. No schema, example JSON, source document or other owner’s file is changed.

## Measurement values, limits and deviations

- [ ] M1: Run synthetic cases H01–H18 in expected_values.md against A's module once delivered; compare raw strings, parsed numeric values, range status, flags and raw code independently. Expected results must not be copied from implementation output.
- [ ] M2: Verify above/below deviations use exact decimal subtraction, are nonnegative and retain precision; no float arithmetic or display rounding. Confirm decimals travel as JSON strings per frozen B2.
- [ ] M3: Check equality at lower, upper and identical bounds (provisional within-bounds policy), negative/zero values, whitespace trimming and numeric equality of `1` and `1.0`.
- [ ] M4: Check blank, whitespace-only, null, text, ambiguous separators, NaN, Infinity, exponent notation, reversed bounds, no bounds and each single-bound direction. Apply D04: blank/whitespace/null → `MISSING`; malformed nonempty text → `UNPARSEABLE`; malformed bounds → `NOT_EVALUABLE` + `LIMIT_INVALID` (also `UNPARSEABLE` for malformed numeric text). Do not treat malformed bounds as missing.
- [ ] M5: Preserve `1001` and null separately from range/quality; never infer PASS/FAIL, a cause, or certified quality. Check in-range `1001`, above-range null and unknown other codes. Apply D05: undocumented codes and raw null both add `SEMANTICS_UNKNOWN` without changing numeric range.
- [ ] M6: Missing unit adds UNIT_UNKNOWN without changing range. BOOK_STAMP stays as stored with unknown timezone; retrieved_at is UTC ISO-8601. Do not guess units or convert source timestamps.
- [x] M7-SQL: Student D reports manual SQL verification of O01–O03 at ST3003 using a read-only SELECT in real Oracle: Angle, Vibration and Motor Speed values and upper limits are recorded in the redacted summary in expected_values.md. Exact subtraction confirms deviations 7.592, 0.354 and 50.457 respectively. All three carry raw code 1001; meaning remains unknown. This records Student D’s verification, not an agent database check or a gate pass.
- [ ] M7-API: Compare O01–O03 against actual API responses and resolve backend-issued evidence. **API VERIFICATION PENDING; EVIDENCE IDs PENDING; Copilot comparison PENDING.** Lower limits, units, timestamps and row identities were not supplied in the summary; do not infer they are absent in Oracle. Full bounds/quality validation remains pending.

## Case and evidence isolation

Use only IDs returned by the running backend. For invalid-ID scenarios, supply a deliberately invalid test input at execution time; it is never a claimed evidence reference.

- [ ] I1: Open two cases, record an offered-question answer in one, verify the other's answers, snapshot and handover do not change. Claim case isolation only, not user isolation under a shared connector key.
- [ ] I2: Resolve a returned evidence ID in its own case; verify raw snapshot, scope, source, BOOK_STAMP and retrieval time. CALCULATED evidence resolves input IDs and rule; every factual finding resolves.
- [ ] I3: Use a real ID from case A with case B: EVIDENCE_NOT_IN_CASE with no foreign data. Unknown evidence within a valid case: EVIDENCE_NOT_FOUND with no substitute evidence.
- [ ] I4: Unknown, expired and pre-restart case IDs return no recovered data; expect `CASE_NOT_FOUND_OR_EXPIRED` under D03. Backend/API execution remains PENDING.
- [ ] I5: Record a contradictory technician answer: add TECHNICIAN_REPORTED evidence with offered question_id, time and attribution; preserve original observations/calculations, mark conflict, keep UNDETERMINED and update next action.
- [ ] I6: Repeated evidence retrieval returns the immutable captured snapshot without an Oracle refresh, including after the source changes or becomes unavailable in a controlled test.
- [ ] I7: Same station or nearby timestamps alone do not merge records into an incident; snapshot contains at most five findings and one next action. Handover preserves scope, observations, reports, gaps and next action.

## API errors and Oracle unavailability

Future API checks use B's mocked repository first; live failure checks require a controlled environment. No outage is induced during preparation.

- [ ] F1: Missing/wrong connector credential fails closed; no-key response is 401 UNAUTHORIZED and exposes no measurements or secret. Verify every public tool route.
- [ ] F2: Invalid/missing station, malformed time range, from > to, invalid field types and oversized input are rejected per B2. Exact validation mapping is BLOCKED until specified; INVALID_SCOPE is the documented scope error.
- [ ] F3: Empty query yields NO_DATA with exact scope and no measurements; never describe the station as healthy.
- [ ] F4: Oracle unavailable yields SOURCE_UNAVAILABLE; timeout yields TIMEOUT. Both carry no cached, synthetic or substitute measurements; Copilot reports the error honestly.
- [ ] F5: Check request_id correlation, retrieved_at, envelope and data/error exclusivity against B2 examples on every path. Logs contain no credentials or full row dumps.
- [ ] F6: Existing observations are not relabeled as newly retrieved during an error. If mentioned in chat, earlier data retain their retrieval time.

## End-to-end Copilot verification (planned only)

- [ ] E1: In real Copilot chat, verify protected HTTPS tool call and live Oracle-derived value; match fresh request_id/value to redacted backend log. Local curl, mock data and dashboard screenshots cannot pass G0.
- [ ] E2: Open a validated station case; compare ≥3 values/limits to independently checked O01–O03, resolve every factual finding and retain UNDETERMINED with explicit unknown code/unit/timezone semantics.
- [ ] E3: Agent asks one question Oracle cannot answer. Reply naturally without naming a tool; confirm agent calls record_answer before responding, with the same case_id and offered question_id. Repeat with a differently worded reply; retain actual request references later.
- [ ] E4: Confirm updated next check and source-grounded handover; observations unchanged, technician report distinguished, no unsupported cause or physical intervention advice.
- [ ] E5: Later exercise tool errors and invalid/foreign evidence in chat; prompt injection in technician text/tool output must not change tool rules. Requests to guess values or provide unsupported intervention advice yield a safe data check or escalation.
- [ ] E6: Later complete the full journey twice and retain separate redacted proof for each run. No G0/G1/G2/G3 or demo-readiness claim is made here; D6/D8 execution is outside this stage.

## Redacted SQL verification status

O01–O03 received **MANUAL SQL VERIFIED — Student D reported** status. Only the authorized minimal measurement summary is retained in expected_values.md; no real serial numbers, complete Oracle rows or confidential production details are stored. The SQL execution date, query reference and external proof location were not supplied and are not invented. No evidence ID has been supplied or issued here. The three upper breaches do not establish the reported in-range Screw Count pattern, NULL-code coverage, an incident link or a cause; those checks remain pending.

Remaining D5 dependencies: B2 frozen schemas and examples, including the approved D03–D05 behavior; A2/A3 repository and measurement logic; B3–B6 immutable evidence, isolated cases, snapshots and endpoints, with B7 mocked-repository API tests. The manual SQL summary supplies expected upper-breach arithmetic only; it does not verify any backend behavior. Full D5 remains incomplete. Next D5 action: obtain B2 schemas/examples from B and compare them against these settled expectations before executing checks as A/B modules arrive. Equality remains provisional; the missing source references and full source bounds for O01–O03 are not invented.

## Execution record template (unfilled)

| Scenario ID | Status | Expected reference | Actual result | Reviewer/date | Redacted proof / defect |
| --- | --- | --- | --- | --- | --- |
| To be selected | PENDING EXECUTION | To be selected | Not run | Not recorded | Not available |
