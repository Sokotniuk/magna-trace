# Independent backend audit — 2026-11-11

## A. Executive verdict

**NOT READY — BLOCKING DEFECTS** for unconditional shared/demo acceptance.

The patched active backend passes the offline checks below. This is not a live
Oracle/provider acceptance. Existing demo password hashes were generated from a
900,000-combination space and must be replaced by the team before shared use.
The legacy backend advertised as a fallback has incompatible numeric/error
semantics and must not be substituted for the active backend. The explicit
technician-conflict review flow still needs B/C agreement. After these deployment
decisions, run the actual revised application against Oracle and the approved
provider twice with D's independent SQL expectations.

Audited input: **codexsfunclub-main (2).zip**, SHA-256
`ab3f7e35a8c29973c26a6b0159b9296e85d5b959b4bf59cc77ab6d3e8b0bd56a`.
The earlier ZIP had SHA-256
`13124d161ac9dff373a5e6669b143e4e4080f17a26491f5b9742413b7e147da4`.
The second archive arrived during the audit. Its added employee authentication,
attribution, frontend and D34 decision were retained; fixes were ported with
context review. No team worktree, original ZIP, frontend, approved schema or
Oracle data was modified. The archive has no .git: no verifiable commit or branch
can be asserted. Audit work is in the extracted latest-source directory.

Task coverage: A8/B7/C9/D6 independent verification and narrowly scoped fixes,
explicitly authorized across backend ownership by the audit request. No A7/B8
comparison implementation, commit, merge, push or Git bundle.

## B. Findings summary

14 grouped findings: **P0 2, P1 7, P2 5, P3 0**. Twelve groups have code fixes;
F07 also requires account regeneration. F13/F14 remain deployment/test-layout
limitations. External acceptance gaps are listed separately, not counted as newly
discovered code defects. Severity describes the original defect, not residual risk.

## C. Confirmed defects, reproduction and disposition

Paths/lines below refer to the patched tree; inspect the accompanying patch for
the removed statements. All reproductions use synthetic inputs, never real secrets.

| ID | Severity | Location | Failure / cause / impact | Correction and evidence |
| --- | --- | --- | --- | --- |
| F01 | P0 | agent/chat.py:157 | A no-tool model reply was forwarded verbatim. A scripted provider returned EQUIPMENT_LIKELY, an invented measurement and evidence reference; all reached the technician despite D33. | Free prose is replaced by a deterministic capabilities/refusal response. Only rendered tools supply facts. `test_untrusted_model_prose_is_not_a_fact_channel` failed before and passes after. |
| F02 | P0 | agent/chat.py:196 | The model's answer_text was stored as TECHNICIAN_REPORTED even when it contradicted the actual user's sentence. | For chat record_answer, use the current technician message, not model-authored text. `test_report_uses_actual_technician_text` failed before/passes after. MCP clients remain responsible for the text they submit; no cryptographic human-attestation claim. |
| F03 | P1 | agent/tools.py:103,113 | Failed open_case retained the old case/question; subsequent answer could modify that old case. Expiry also left stale active context. | Clear context before a scope switch and on CASE_NOT_FOUND_OR_EXPIRED. Both stale-context tests failed before/passed after. Existing cases remain immutable and independently retrievable. |
| F04 | P1 | agent/tools.py:136 | Arbitrary invented strings ending in a number were repaired into valid current-case evidence IDs. Wrong provenance could appear valid. | Accept full canonical IDs or explicit bare numeric ordinals only; reject arbitrary suffixes before REST. Invented-reference test failed before/passes after; foreign canonical ID stays foreign. |
| F05 | P1 | agent/chat.py:112 | Configured provider-route allowlist was checked only when x-routed-via existed; missing header bypassed verification. | With an allowlist, absent or unapproved routing headers fail closed. Missing-route test failed before/passes after. A response header is still provider attestation, not independent proof of routing; transmission happens before the response. |
| F06 | P1 | student_b/answers.py:27; student_b/evidence.py:18 | Evidence report was published before updated snapshot validation. Injected diagnostic failure returned 500 but left an orphan report, allowing retry inconsistencies. | Stage the evidence dictionary, validate snapshot, publish under existing per-case lock. Immutable prior items are shared safely. Partial-failure test reproduced the orphan before the fix and now passes. D34 attribution preserved. |
| F07 | P1 | agent/make_employees.py:29 | Password generator chose 10 words × 10 words × 9000 numbers = 900,000 possibilities, about 19.8 bits; salted hashes are distributed in the archive. Offline guessing is not stopped by login throttling. | Generator now uses 18 random bytes (144 bits). Existing passwords/hashes were NOT rotated or cracked. Team must regenerate and privately distribute credentials; this remains a deployment blocker. Test verifies generated shape/uniqueness, source establishes entropy. |
| F08 | P2 | agent/chat.py:112,157 | Empty provider choices caused IndexError/500 and left an unmatched user history entry. No whole provider-call deadline or action-count bound. | Validate a single choice/at most one tool before effects, bound arguments, use a 30-second model deadline and rollback history on recognized malformed/provider errors. Tests cover malformed choices, cancellation and rejection of two actions. This deadline does not resolve Oracle D15. |
| F09 | P2 | agent/chat.py:87,236; agent/auth.py:144 | max_history bounded only transmitted history, while stored history grew indefinitely. Throttle.blocked inserted every unknown username. Busy conversations could be evicted. | Trim stored history, avoid evicting locked conversations, prune expired throttle entries and do not allocate on probes. Tests cover history and 1000 unknown usernames; busy-eviction change inspected, not load-tested. |
| F10 | P2 | student_b/main.py:158; agent/main.py:43 | Chat/auth key checks did not consume B's request-rate budget; model-only requests bypassed it. | Reuse B's authentication/rate admission. Independent test confirms second model-only request is 429 under budget one. MCP metadata is not given a new global limiter. |
| F11 | P2 | agent/main.py:64; agent/chat.py:208 | Model HTTP client was never closed; toolbox cleanup was skipped on lifespan failure. | Close both clients in nested finally blocks. Normal test-client lifespans pass; all shutdown/cancellation combinations were not instrumented. |
| F12 | P1 | student_c/backend/app/oracle_repo.py:32 | Legacy connect logs included username, DSN and arbitrary driver message; future credentials/connection internals could leak. | Log exception type only. Synthetic sensitive sentinel absent from captured logs in new legacy regression. No actual production credential leak is asserted. |
| F13 | P1 | student_c/backend/app/measurements.py:47; oracle_repo.py:50 | Legacy evaluator can evaluate a valid side despite a malformed other bound, omits SEMANTICS_UNKNOWN for null codes, uses ambient Decimal precision; timeout matching recognizes only DPI-1067. Legacy interval is inclusive and schema differs from B2. | Legacy is not imported by active agent.main. Do NOT use it as the demo fallback. Broad legacy semantic changes were withheld: its own tests/decisions reflect a different interface. Owner must retire it or separately reconcile it. Existing 52 green legacy tests do not establish canonical correctness. |
| F14 | P2 | student_c/tests imports and duplicate backend.app package | Collecting active and legacy suites in one process produces three ImportErrors for services because both use backend.app. | Run legacy tests separately from student_c. No test deleted/skipped/weakened to conceal this. README's active-suite command is valid; repository-wide single-process collection is not. |

Independent tests originally produced **8 failed / 11 passed** against the first
archive. A subsequent transactional injection produced **1 failed / 27 passed**
before F06. Those failures establish sensitivity to actual broken behavior, rather
than merely asserting the corrected implementation. The latest baseline still
contained those defective paths; its employee layer was separately retested.

## D. Security and architecture

Active call graph:
`agent.main → student_b.main/router → OracleSource → backend.app.oracle_repo →
analyze_measurement → immutable B2 raw/calculated evidence → snapshot`.
Chat selects tools; Toolbox uses authenticated in-process ASGI requests to those
same REST routes. MCP tools use the same Toolbox. Answers update only report,
action and case state; handover/evidence retrieval read captured RAM state.

Latest employee gate requires a cookie AND connector key for web API routes.
Login/info still require the key. Toolbox uses a random process-only token and
forwards the employee context for attribution. MCP continues to use connector-key
authentication without employee sign-in, explicitly per D34. **There is no per-user
case ACL, role authorization or corporate identity guarantee**; D34 expressly
excludes these. Another authenticated employee with an ID can access the shared
case. Cross-case evidence-reference rejection and answer isolation are different
properties and were tested.

Verified offline: missing/invalid auth across all five REST tools, chat and MCP;
login/logout/cookie flags/session expiry and internal-token tests; production dev
routes disabled; no wildcard CORS; bounded request bodies; exact decimal wire
strings; redacted source failures; foreign/invented evidence; stable observations;
same-case concurrent answers return one success and one 409; isolated second case;
fixed SELECT/binds, no dynamic user SQL and no cross-table runtime joins. Full
source pages remain private to the backend; public evidence intentionally exposes
the approved B2 subset. No live path imports SyntheticSource or activates mocks.

Source/archive scan found no confirmed plaintext operational secret or private
key. Tests use synthetic values/random keys; documentation has placeholders.
employees.json contains intentionally distributed fictional identities and password
verifiers, not plaintext passwords; F07 still applies. No .env or local generated
password file was included. Custom pattern scans cannot prove absence of all
secret formats; Git history cannot be inspected because the archives omit it.

Remaining security/runtime limits: cookies are not Secure on the explicitly local
HTTP demo (D34); do not treat this as an approved public login deployment. Throttle
check/failure recording is not an atomic reservation, so parallel attempts may
exceed the nominal failed-login allowance. RequestBoundary reads before auth and
has no application body-read timeout. MCP Host protection is disabled for tunnels;
retain key and approved ingress policy. /readyz is unauthenticated and contacts
Oracle: restrict support-route exposure. HTTP disconnect does not prove an Oracle
worker/query was cancelled; ASGITransport's client timeout is not a hard worker
deadline. No resource soak test, network penetration test or provider data-routing
attestation was performed. Tool-output/user text remain untrusted data even after
deterministic rendering; an LLM can still select the wrong otherwise-allowed tool.

## E. Requirements and DoD traceability

Authority: product v1.0 → architecture → plan → agent instructions, with dated
verified decisions resolving provisional facts. D32 explicitly substitutes the
approved stand-in model; lack of Copilot credits is not silently treated as a
failed mandatory stand-in requirement. D33 requires deterministic presentation;
D34 adds provisional employee sign-in. B2 models/schema/examples are unchanged.
Root Plan A is stale (A1-era ledger); docs/student_a and actual source/tests provide
later handoff claims. D19–D29 are absent from the root decision register but selected
A decisions are in docs/student_a. Prior acceptance reports are provenance, not
new verification. Missing root copilot/openapi.v2.json/setup prevents Swagger2 drift
acceptance; actual MCP registration is tested instead under the approved alternate.

| Requirement | Owner | Implementation / evidence | Status | Notes |
| --- | --- | --- | --- | --- |
| P0-01 / C1–C4 alternate model channel | C | D32; agent/main/chat/mcp; scripted chat and actual MCP ASGI tests | IMPLEMENTED BUT NOT VERIFIED | No live provider/tunnel run in this audit; original G0 not passed |
| P0-02 / A1 restricted Oracle baseline | A/D | fixed count; A tests; prior 1524/23 claims | BLOCKED BY ENVIRONMENT | No Oracle credentials; grants/current counts not reverified |
| A2 scope/binds/order/count/cap/truncation | A | unchanged oracle_repo; SQLite relational/reference tests and B adapter driver tests | VERIFIED | Offline; Oracle dialect/live rows not retested |
| A2 station search and limits | A/B | literal case-sensitive substring; q=None, blank rejected; internal 500, B cap 200, stations cap100 | VERIFIED | B2 notes reconcile earlier prefix/inclusive proposals |
| P0-03 / A3 strict Decimal/independent statuses | A | unchanged measurements; equality/null/malformed/reversed/single-bound/code and precision tests | VERIFIED | D09 provisional; raw null/code never PASS/FAIL |
| A4 ≥3 independent real findings and coded equality | A/D | historical Angle 7.592, Vibration .354, Position Accuracy .292; 8 within 8..8 code1001 | BLOCKED BY ENVIRONMENT | No source-row export used as new proof; D must recheck actual revised runtime |
| A5 keys/units/time semantics | A/D | no runtime joins; unknown warnings | PARTIALLY IMPLEMENTED | Disabled joins verified; D10 formal disposition remains external |
| A6 canonical failures/no fallback/cleanup | A/B | source classifier; B status 404/422/503/504; independent injected failures and empty page | VERIFIED | Offline; DPY-4024/ORA-01013 live reports historical; D15 open |
| A8 integrated A→B outputs | A/B/D | real modules with synthetic driver through REST and exact precision | PARTIALLY IMPLEMENTED | Live integrated revision + D sign-off pending |
| B1 auth/envelope/request logging/support routes | B | main middleware; existing tests + independent unauthorized surface matrix | VERIFIED | Shared connector; support ingress responsibility remains |
| B2 frozen schemas/examples/decimal serialization | B/C/D | unchanged schemas; 35-fixture validator and drift tests | VERIFIED | Swagger2 file absent; not a Copilot import verification |
| P0-04 / B3 evidence/immutable snapshots | B | private source capture; separate observed/calculated/report models; resolution tests | VERIFIED | No Oracle requery; ROWID never evidence identity |
| B4 lifecycle/TTL/cap/locks/restart/answer isolation | B | CaseStore; concurrent answer and second-case checks; F06 staging | VERIFIED | RAM only; open_case retries create separate cases by design, no idempotency contract |
| B4 contradictory technician report | B/C | reviewed_conflicts internal helper; REST always unreviewed | PARTIALLY IMPLEMENTED | Existing accepted open issue; needs explicit review flow agreement, no inferred NLP conflict rule added |
| P0-05 / B5 max5/UNDETERMINED/hypotheses | B | deterministic diagnostics; schema literal; all suites | VERIFIED | D31 prioritization remains provisional B review |
| P0-06 / B6/C7 answer before reply | B/C | actual report update; scripted model+MCP journey; F02 original message | PARTIALLY IMPLEMENTED | Live autonomous selection on two differently phrased answers pending |
| P0-07 fixed data check/escalation; no unsupported procedure | B/C | diagnostics + deterministic no-tool fallback | VERIFIED | Offline; no SOP knowledge enabled |
| P0-08 handover and two real complete journeys | B/C/D | stored snapshot handover, immutable observations | IMPLEMENTED BUT NOT VERIFIED | Full live rehearsals still required |
| B7 negative/isolation/fault tests | B/D | original + independent suites, redacted HTTP errors | VERIFIED | Synthetic/loopback, not authenticated Oracle |
| C tool schemas/auth/registration/state | C | five MCP tools; MCP open/evidence/answer/handover; F03/F04 | VERIFIED | Tenant connectivity unavailable |
| C provider outage/malformed response/routing guard | C | F05/F08; no deterministic backend dependency on provider | VERIFIED | Scripted responses and cancelled synthetic coroutine only |
| D34 demo employee session/attribution | C/B | unchanged identity flow, auth tests and new throttle/generator checks | PARTIALLY IMPLEMENTED | Existing password rotation and B review outstanding |
| D6/D8 security/rehearsals | D/team | archive/diff scans and fault injection | PARTIALLY IMPLEMENTED | No full live negatives/two timed runs |
| One worker, bounded state, cleanup | B/C | settings guard, CaseStore/Sessions, bounded chat history and cleanup | PARTIALLY IMPLEMENTED | D15, client disconnect and load behavior remain limits |
| Source timezone/semantics/raw values | A/B/C | six-digit source text, UTC retrieval separately, warning propagation | VERIFIED | Semantics deliberately UNKNOWN; no incident merge |
| Frontend API compatibility | D | api.ts models/proxy inspected; schema and frontend bytes unchanged from latest ZIP | IMPLEMENTED BUT NOT VERIFIED | No browser/build run; UI completion not backend prerequisite |
| A7/B8 comparison, persistence, knowledge, exports | team | absent/disabled | NOT REQUIRED / OPTIONAL | Not started or added |
| Legacy alternative canonical behavior | C | separate implementation, F13 | FAILED | Exclude from demonstration deployment |

## F. Commands and results

Python: `F:\tuke\hackaton\.venvs\backend-audit\Scripts\python.exe` (3.13.15).
Installed existing declared dependencies into isolated audit venv; no requirements
files changed. Resolved versions include FastAPI 0.141.1, Pydantic 2.13.4,
oracledb 26.1.0, pytest 9.2.0, httpx 0.28.1, MCP 1.30.0, OpenAI 3.49.0.
These installed versions are not a claim about the team's other machine.

Commands below run from the latest extracted root unless specified:

```powershell
$py = 'F:\tuke\hackaton\.venvs\backend-audit\Scripts\python.exe'
& $py -B -m pytest -q -p no:cacheprovider tests student_b/tests agent/tests audit_tests devtools/student_b/tests --ignore=tests/d5_live_smoke.py
& $py -B contracts/b2/validate.py
# Separate process and working directory for legacy duplicate package:
Set-Location student_c
& $py -B -m pytest -q -p no:cacheprovider tests
& $py -m pip check
```

| Check | Actual result |
| --- | --- |
| First archive original active+devtool suite | 304 passed, 10 subtests passed, 15.88 s |
| Latest archive original active+devtool suite | 312 passed, 10 subtests passed, 17.82 s |
| Latest patched active+independent+devtool suite | **342 passed, 10 subtests passed, 20.84 s** |
| Original isolated legacy suite | 51 passed |
| Patched isolated legacy suite | **52 passed, 0.25 s** |
| B2 validator | PASS: 35 fixtures; nine codes; evidence/decimal/null/time constraints |
| pip check | No broken requirements found |
| One-process active+legacy collection attempt | Three ImportErrors; see F14, no false green claim |

Added 30 active independent tests and one legacy logging regression. Tests cover
HTTP/MCP auth, actual A2/A3→B with injected source rows, high precision, null/code
preservation, immutable evidence, same-case concurrency, cross-case references,
NO_DATA, invalid time/scope, typed failures, orphan report rollback, adversarial
model output, missing route, malformed response, provider deadline, multi-action
rejection, stale context, history bound, throttle storage and password generation.
Original tests are unchanged. No deliberately mutated source remains. The old
d5_live_smoke runner is intentionally not an offline test: no live access exists.
student_b/live_check is connector-only and predates D34; it cannot authenticate
to the latest web API without an employee session. Use the procedure below.

## G. Changed files and evidence

- agent/chat.py: safe no-tool output, original testimony, provider validation/deadline,
  bounded history, no busy-conversation eviction, model-client cleanup.
- agent/tools.py: stale-context clearing and strict evidence-reference resolution;
  latest internal-token/employee forwarding retained.
- agent/main.py and student_b/main.py: shared connector rate admission, guaranteed cleanup.
- student_b/evidence.py and answers.py: staged atomic report publication, attribution retained.
- agent/auth.py: prune throttle history; avoid allocating unknown-name probes.
- agent/make_employees.py: high-entropy generation for future credentials only.
- student_c/backend/app/oracle_repo.py: redact legacy connection/error logs.
- audit_tests/test_independent_backend.py; student_c/tests/test_audit_logging.py: new tests.
- docs/FINAL_BACKEND_AUDIT.md; docs/AUDIT_MANIFEST.json: audit results/provenance.

`backend-audit-fixes.patch` is relative to the latest ZIP and contains reviewed
changes. `docs/AUDIT_MANIFEST.json` records original/final SHA-256 values and
unchanged frontend/contracts/A modules. Git diff against a commit is unavailable;
the patch is an archive-to-directory diff, checked with `git apply --check` against
a clean latest-ZIP extraction. No branch/revision is invented.

## H. Remaining limitations and decisions

D09 equality/grammar stay provisional. D15 remains OPEN: TCP establishment and
post-login per-round-trip timeouts are not whole-login deadlines. This audit does
not claim to resolve either, nor to reverify previously reported live counts,
1524/60/104 or timeout/cancellation events. No credentials for Oracle or a model
were configured; no tunnel, tenant or password was requested or read.

B/C must settle explicit conflict review, D31 finding order and D34 sign-in receipt.
No new public B2 fields were introduced. Preserve current half-open time bounds,
literal search and nullable deviation. Source user/serial fields get B2's declared
whitespace normalization; agent station uppercasing remains legacy interface
behavior and should be reconciled if mixed-case identifiers are permitted.
Bare numeric evidence ordinals remain a supported convenience, not globally unique
references. MCP receives caller-supplied testimony and identifiers; web login is
not an individual case ownership boundary. No snapshot-version API is required
by the supplied B2; current immutable observations plus case state are verified.

## I. Shortest real-data demo acceptance procedure

1. On the authorized Oracle host, deploy this patched tree. Retain one worker and
   loopback Oracle. Keep source permissions SELECT-only. Compare current independent
   baseline SQL with the historical counts; do not hardcode them as runtime output.
2. Team locally runs `python -m agent.make_employees` to regenerate weak demo
   credentials. Privately distribute the ignored local account file; never commit,
   upload or print it in audit output. Do not reuse the shipped hashes as strong secrets.
3. Configure TRACE_API_KEY, ORACLE_USER/PASSWORD/DSN and the approved model's existing
   OPENAI_API_KEY/BASE_URL/MODEL, TRACE_EXPECTED_ROUTE and TRACE_ALLOW_REAL_DATA locally.
   Set TRACE_DEV_ROUTES=false. Never put credentials in VITE_* variables.
4. Start from repository root:

```powershell
python -m uvicorn agent.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

5. Through D's live Vite proxy, sign in with a newly generated demo account. Confirm
   missing key and missing session are rejected. GET /api/v1/stations?limit=100
   returns real station groups; historical baseline is 23 stations, ST3003=60,
   ST1001=104. POST /api/v1/cases with {"station_number":"ST3003"} captures its
   source rows. Compare three findings and coded equality with independent A4 SQL,
   including source times/units/null deviation. GET each returned observed and
   calculation evidence ID; do not synthesize IDs.
6. In chat, investigate ST3003, request one calculation, answer the offered question
   in plain language, then request handover. Confirm autonomous record_answer,
   employee attribution, unchanged observations and UNDETERMINED. Repeat with a
   differently worded answer in a new case. Capture only safe request IDs, hashes,
   aggregate outcomes and reviewer, not source exports or secrets.
7. D checks empty scope and controlled source/timeout failures, foreign/invented
   evidence and unavailable provider. Use approved isolated fault configuration;
   do not stop/modify the shared Oracle service to manufacture a failure.

## J. Next actions

1. Regenerate/re-distribute weak demo accounts locally (C); deploy only agent.main.
2. B/C decide the explicit conflict-review path and acknowledge D31/D34 changes.
3. A/B/D run the patched integrated revision on the Oracle host; C runs the approved
   model journey twice. Record exact source hashes and independent SQL comparisons.
4. B/C retain D15 as a visible accepted risk and settle deployment timeout/ingress
   controls; D verifies the listener and authenticated tunnel exposure.
5. Retire the legacy fallback or separately reconcile its schema/numerics before use.
