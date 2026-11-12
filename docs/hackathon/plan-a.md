# MAGNA TRACE | Student A implementation plan

**Status:** FINAL / APPROVED — team development baseline. Implementation status is recorded separately in §10.

## 1. Role, goal, scope and non-goals

Student A supplies the read-only Oracle records, exact numeric results and provenance that Student B can capture in a case. A successful handoff lets D reproduce each demo finding from SQL and hand arithmetic.

- **P0 required.** A1–A6 and A8 cover the live count, bounded reads, measurement rules, demo evidence, verified or disabled relationships, failure behavior and integration support. A supplies the captured inputs for B’s concise evidence-backed handover from the active case. Persistent history and richer exports are P1.
- **P1 conditional.** A7 compares observations only where the data support it. P0 runs with comparison disabled. The P0 assessment remains `UNDETERMINED`.
- **Ownership.** A owns the three Python modules named below, their unit tests and `docs/data-baseline.sql`. A may append verified decisions. B owns routes, authentication enforcement, schemas, cases, IDs and evidence storage. C owns Copilot and tunnel setup. D owns dashboard, E2E tests and independent expected-value tables.
- **Deferred ideas.** Knowledge retrieval, incident grouping, persistence and extra analytics have no A deliverables here. Machine control, unrestricted SQL, predictive models and a second LLM are outside the project scope.

## 2. Source documents and assumptions

Read the canonical files in this worktree. The user adopted Product v1.0, Architecture v1.1 and Delivery Plan v1.0. Each is approved for development. A1 and A4 must independently reproduce the historical Oracle observations.

| Canonical document | Use in Student A work |
| --- | --- |
| `docs/product.md` v1.0 | P0/P1 scope and acceptance criteria, including the basic active-case handover. |
| `docs/architecture.md` v1.1 | API, data, case, evidence, security and comparison contracts. |
| `docs/plan.md` v1.0 | A1–A8, receiving owners, task dependencies and gate checkers. |
| `AGENTS.md`, `tips.md` | Execution rules and supplementary explanations. |
| `docs/decisions.md` | D01–D08 record baseline choices; D09–D12 identify provisional behavior and verification still needed. Append dated resolutions. |

Consult D09–D12 when a task depends on source facts or concrete integration settings. An unknown relationship disables the affected join or comparison. Escalate a failed live demo criterion to A/D and the team.

## 3. Workspace and Git strategy

Work in `F:\tuke\hackaton\magna-trace-student-a` on `feature/student-a`, linked to `codexsfunclub` and created from local `main` at `af2c628`. The original checkout uses `feature/vasyl`. Archives stay outside both trees.

Before edits, run `git status --short --branch` and `git worktree list`. Inspect only the current task's files and decisions. Use the team's Python environment and existing dependencies. Ask before adding a package. Stop for foreign-owned edits or an unapproved contract change.

Review paths, untracked files, `git diff --check` and the exact staged diff for secrets, dumps and real exported rows. Commit only on student request after verification, with an A-task prefix. Record the commit or “uncommitted” in the ledger. No push, reset, rebase or merge during planning.

For later authorized integration, bring current shared `main` into A’s branch with the owners. D checks that result before B integrates. Use a full branch bundle when the receiver’s history is uncertain. For A, `git bundle create ../trace-student-a.bundle feature/student-a` includes reachable branch history. Use `main..feature/student-a` only after B confirms all prerequisite commits are present. B runs `git bundle verify <file>` in the receiving repository before `git fetch <file> feature/student-a:incoming/student-a`. Inspect outgoing history for secrets before authorized transfer.

## 4. Dependencies and integration contracts

Execution order is A1 (count to B first, baseline second) → A2 → A3 → A4 → A5 → A6 → A8 for P0. A7 is a separate branch of work after A2–A6, D's G1 check and stable P0. Run A8 integration checks for A7 only if it ships. Give each handoff as soon as its prerequisite passes.

The input/output responsibilities below follow architecture §§3–5. Hand the scalar count to B1 first. A/B confirm the internal Python names/types and remaining B2 configuration in D12; B owns Pydantic validation, JSON field names, the envelope, error mapping and case-local evidence IDs.

| Python interface for B (names pending B2 confirmation) | Contract |
| --- | --- |
| `count_measurements()` | Existing restricted connection settings → live integer count, or typed source/timeout error. No arguments containing SQL. |
| `list_stations(q, limit)` | Optional station search and bounded limit → ordered station IDs with matching record counts. Agree search semantics with B. Auxiliary route can be cut. |
| `read_measurements(station_number, from_time, to_time, serial_number, limit)` | Required station, optional independent time endpoints and serial → exact scope, ordered raw rows, total matching rows before cap, truncation and captured coverage. Agree default/max limits, timeout and endpoint inclusivity with B; freeze examples at both edges. |
| Raw row and capture | Source table, station, serial, measurement name, original value/lower/upper/unit/fail code and `BOOK_STAMP`. Preserve text and nulls; pass source timestamps without conversion or invented zone. Supply capture order; associate UTC ISO-8601 retrieval time with the read. B snapshots each observation and issues case-local IDs. |
| `analyze_measurement(row)` | One raw row → raw fields plus parsed Decimal value and bounds when valid, independent range status, flags, raw fail code and breach deviation with rule/inputs for B. Agree nullable non-breach deviation with B. Decimal fields crossing JSON use strings. |
| Failures | Empty successful read with exact scope → B emits `NO_DATA`. Invalid scope → `INVALID_SCOPE`; connection failure → `SOURCE_UNAVAILABLE`; timeout → `TIMEOUT`. No data on errors. Malformed source values remain attributable rows with quality flags. |
| `compare_measurements(mode, measurement, observations)` | Optional. Scoped inputs with verified context and links to B's captured observations → attributable compared values, record, distinct-serial and distinct-station counts, time coverage, warnings or `NOT_COMPARABLE` with failed criterion. Agree shape with B8. |

B alone creates `OBSERVED` and `CALCULATED` IDs and stores immutable snapshots. A supplies enough information to reproduce the calculation without re-querying old evidence. Post-B2 public changes require B/C/D agreement, a decisions entry and owner updates to Swagger and the drift test. In real Copilot, C verifies `record_answer` uses the active case and question before the reply. B owns `CASE_NOT_FOUND_OR_EXPIRED` for nonexistent, expired and pre-restart cases. A emits no case errors.

## 5. Execution steps A1–A8

All commands below are for **future approved implementation** from the worktree root. Test paths are proposed A-owned module tests under `tests/`; follow the team's agreed layout if it changes. Each step includes the evidence and recipient required to close it.

### A1 — Prove a restricted live read, then establish the baseline

- **Gate and files.** Start after explicit A1 approval. Use the existing container, an authorized student at the local console and a dedicated restricted login. Create `backend/app/oracle_repo.py`, `tests/test_oracle_repo.py` and `docs/data-baseline.sql`.
- **1. Readiness.** Inspect running container and port bindings with `docker ps`. Have the student verify session user, PDB, effective roles/system/object privileges and read access via SELECT-only metadata checks. Require loopback-only listener, intended grants on required tables, no broad/write privileges, and no privileged runtime account. Never test privileges with a write.
- **2. G0 input.** Implement only the bounded-duration scalar read `SELECT COUNT(*) FROM HACKATON.SNO_MEASUREMENT_DATA`. Student runs that SELECT independently in a restricted SQL client and compares it with the callable in the same source state. Hand the function, integer and retrieval time to B1 immediately for C4.
- **3. Baseline.** Inventory the four named tables and actual column names/types/nullability from accessible metadata. Count each with its own SELECT; profile distinct stations/serials/names, units including nulls, raw-code frequencies, time span, blank/malformed numeric text and duplicate candidate row keys. Keep row samples local and bounded.
- **Check and close.** Student runs `@docs/data-baseline.sql` twice from the restricted SQL client, compares like-for-like totals, and explains any change. Run `python -m pytest -q tests/test_oracle_repo.py`. Save query labels, safe aggregates, UTC retrieval time and verifier. The historical 1,524 is a cross-check only. B confirms receipt of the live callable.
- **Stop.** Missing schema, excess privileges, inaccessible metadata or unsafe listener goes to the environment owner. Obtain administrator attestation if privilege visibility is incomplete. No grants, DDL, database modification, imported archives, volume changes or restoration by A.

### A2 — Return bounded, evidence-ready records

- **Gate and files.** A1 verified; B agrees the read contract including scope boundaries. Extend `backend/app/oracle_repo.py` and `tests/test_oracle_repo.py`. Use A1's verified column mapping.
- **1. Query.** Implement fixed, named SELECTs for station counts/search and measurement reads. Bind all scope values and limits; never interpolate predicates, identifiers or order clauses. Filter station, serial and time independently. Keep the P0 query on the measurement table.
- **2. Bound and capture.** Enforce a positive server cap and bounded connection/call duration, release cursor/connection on every exit. Compute total before limiting in the same consistent read. Return `truncated = total > returned`; include the actual scope and covered timestamps. An exact-cap complete result is distinguishable from overflow.
- **3. Order.** Order stations by station identifier. For measurements order by `BOOK_STAMP` and verified stable tie-break fields before limiting. Test ties, nulls and duplicate projected rows. Keep multiplicity and ordinals. If ties affect which distinguishable rows survive the cap, block release until a reproducible order is agreed.
- **Check and close.** Run `python -m pytest -q tests/test_oracle_repo.py`. Compare ordered field tuples, counts, bounds of coverage and cap behavior with separately written scoped SQL, including tied times. Save bind names, query labels and D's check reference. B calls both functions and confirms raw fields survive intact.
- **Stop.** Missing columns, unsupported precision/driver conversion or ambiguous time filters require an A/B decision. No guessed keys, substitute rows or broadening a query on failure.

### A3 — Compute exact bounds, statuses and deviations

- **Gate and files.** After A2, create `backend/app/measurements.py` and `tests/test_measurements.py`. Use the approved D04/D05 rules and capture the expected outputs as synthetic fixtures before running the code.
- **1. Parse.** Preserve originals and trim only the parsing copy. Null, empty and whitespace-only → `MISSING`. Reject nonempty malformed text, ambiguous separators, exponents and non-finite values as `UNPARSEABLE`. Parse valid decimal text directly to `Decimal`; check subtraction beyond default context precision against hand arithmetic.
- **2. Evaluate.** Missing or invalid measurement value → `NOT_EVALUABLE`. Two absent bounds → `NOT_EVALUABLE` + `LIMIT_UNKNOWN`. Reversed or malformed supplied bounds → `NOT_EVALUABLE` + `LIMIT_INVALID`; classify nonempty malformed text as `UNPARSEABLE`. One valid bound and one missing → evaluate the recorded side and flag `PARTIAL_BOUNDS`.
- **3. Emit.** Equality is provisionally within bounds. Compute upper breach as value minus upper and lower breach as lower minus value, preserving scale. Preserve null or raw code; include `SEMANTICS_UNKNOWN` for undocumented codes and null. Add `UNIT_UNKNOWN` when unit is absent. Keep range status independent of these flags.
- **Check and close.** Run `python -m pytest -q tests/test_measurements.py` against §6 hand calculations and raw-input preservation checks. Save the synthetic expected/actual pairs, agreed flag mapping and test outcome. B5 verifies one raw-plus-calculated pair can be captured and serialized exactly.
- **Stop.** If source grammar differs or equality is disputed, record the evidence, get a dated decision and update expectations before widening the parser.

### A4 — Select and independently verify demo evidence

- **Gate and files.** A1–A3 ready. Extend `docs/data-baseline.sql` with reproducible bound queries, and A-owned tests with synthetic analogues. Append only confirmed demo references to `docs/decisions.md`. D owns the independent QA table.
- **1. Locate.** Start with the reported ST3003 lead. Select three individually identifiable abnormal observations within one reproducible station scope. Separately look for the reported in-range Screw Count row carrying raw `1001`; record its actual scope even if different.
- **2. Verify.** A student checks original field values, limits, units, raw codes, timestamps and query order locally. Calculate each deviation by hand. D uses separate SQL and compares with A2/A3 outputs. Confirm B's selected scope/cap actually exposes the findings.
- **D5 handoff format.** For each finding, D records a permitted source reference, raw inputs checked, independently expected status/deviation, observed output, match or discrepancy, and reviewer. The shared Git record can point to the restricted verification sheet when row details must stay local.
- **Check and close.** Rerun the labelled A4 SELECTs from `@docs/data-baseline.sql` and `python -m pytest -q tests/test_measurements.py`. Record permitted scope references, query labels/ordinals, check date and verifier. Share the procedure and safe synthetic fixtures with B/C/D; keep real row exports out of Git, logs and prompts.
- **Stop.** Shortfall, ambiguous locator, mismatched arithmetic or missing coded example stays open. Recheck a permitted alternative scope or seek a team decision. Preserve each observation separately; G1 requires D's independent check.

### A5 — Establish which relationships the data support

- **Gate and files.** A4 verified. Extend `docs/data-baseline.sql`; append dated results in `docs/decisions.md`. Inspect `MACHINE_LINES`, `SNO_BOOKINGS_WP`, `SNO_MEASUREMENT_DATA` and `WORKORDERS` with the restricted account.
- **1. Investigate.** For each candidate station, serial, part, booking or work-order relationship, inspect declared constraints, type/domain compatibility, nulls, duplicates, unmatched keys and join multiplicity in both directions. Count expanded matches against the source counts. Check product/test and unit semantics with the data owner.
- **2. Decide.** Record relationship, direction, cardinality, coverage, evidence query and permitted use. Mark verified, rejected or unknown; disable rejected and unknown paths. Record unit, timezone and bound-equality confirmations or provisional policy. Check whether a durable key exists separately from a useful join.
- **Check and close.** Student reruns labelled A5 SELECTs via `@docs/data-baseline.sql`; D inspects aggregate counts and representative ambiguous cases locally. Give B/D the verified-or-disabled matrix. An explicitly disabled relationship is a valid A5 result.
- **Stop.** Unexplained fan-out, undocumented semantics or incomplete keys disable the affected join/comparison. Matching values, station names or close timestamps alone cannot establish incident identity.

### A6 — Make every failure observable to B

- **Gate and files.** A2–A5 complete; agree canonical errors with B6. Extend `backend/app/oracle_repo.py`, `tests/test_oracle_repo.py` and, for malformed rows if needed, the A3 module/test.
- **1. Exercise boundaries.** Use a recording cursor/connection double for empty fetch, connect failure, call timeout and failure after partial fetch. Check invalid station, reversed/incomplete scope per B2, and invalid limits before issuing SQL. Optional omitted time endpoints follow the agreed scope contract.
- **2. Verify mapping.** Preserve exact queried scope for empty success. Propagate typed source/timeout errors, discard partial results, release resources and keep diagnostics credential-free. Pass malformed source numerics to A3; a bad value cannot turn a successful query into `NO_DATA`.
- **Check and close.** Run `python -m pytest -q tests/test_oracle_repo.py tests/test_measurements.py`. B7/D6 check envelope code, exact scope where applicable and absence of measurement data on errors. Verify a genuinely empty scope by separate SELECT. Coordinate live negative checks on an isolated test connection without stopping shared Oracle.
- **Evidence and stop.** Save a scenario → observed code/row-count table with unit/mock/live provenance. Hand to B/D. Unmapped driver errors, leaked partial data or unverified live behavior remain explicit blockers for the affected check.

### A7 — Compare compatible observations (conditional P1)

- **Gate and files.** Require completed A2–A6, student-verified G1, stable P0 including A8 and verified scope keys. Then create `backend/app/comparisons.py` and `tests/test_comparisons.py`. B8 owns optional route wiring.
- **1. Select.** For `same_station_across_serials`, hold station fixed and count distinct comparable serials. For `same_serial_across_stations`, hold serial fixed and count distinct comparable stations. Repeated tests retain their row count without increasing independent coverage.
- **2. Verify compatibility.** Require verified scope keys, matching measurement name, compatible recorded units, numerically equal Decimal bounds, verified compatible test and product context, and parsed values. Refuse if missing evidence prevents a mandatory check. Do not infer conversion or event identity.
- **3. Return.** Use `COUNT(DISTINCT serial_number)` at a fixed station and `COUNT(DISTINCT station_number)` for a fixed serial. Fewer than two comparable entities → `NOT_COMPARABLE` with the failed criterion. With all checks met, exactly two → `LOW_SAMPLE`; at least three → no warning. Return evidence references, record count, distinct serial and station counts, and min/max source time.
- **Check and close.** Run `python -m pytest -q tests/test_comparisons.py`; hand-count both modes, refuse each criterion individually and check counts/coverage against independent scoped SQL. Save allowed/refused synthetic fixtures and decision reference for B8/D5. No causal label or assessment change.
- **Stop or cut.** An unverified key or incompatible inputs require a criterion-specific refusal. If the extension cannot be validated within team scope, record `OPTIONAL_NOT_IMPLEMENTED` and tell B to keep it disabled.

### A8 — Verify Student B can consume Student A's outputs

- **Gate and files.** After A6 for P0; repeat affected checks if A7 ships. Change only affected A-owned modules/tests, baseline or dated decisions. Use B2's actual examples and B's caller on the integrated revision.
- **1. Trace.** With B, trace one scoped read through raw capture and calculation inputs to the displayed evidence. Compare decimals as strings, raw null/code, scope, ordinal, source time and retrieval time against independent references. Inspect all A6 outcomes through B's caller.
- **2. Resolve.** Reproduce deviations using the smallest synthetic fixture, fix only A-owned defects, rerun the focused test then `python -m pytest -q` in the agreed integrated test environment. D performs SQL spot checks and G3 negatives; A supports D's two rehearsals.
- **Check and close.** Save command, actual result, revision, D5 evidence reference and B's acknowledgement. List outstanding external checks by owner. Missing B caller or unresolved discrepancies block integration sign-off; pass B/C/D defects to their owners.

## 6. Testing and verification matrix

Unit tests use synthetic rows, a recording driver double and independently written expected literals. Live checks are explicitly student-run in the restricted SQL client against the existing database; ordinary pytest must run without credentials or network access. Label each result **unit**, **live SQL** or **integrated**.

| Subject | Stimulus and independently checkable expectation |
| --- | --- |
| Bounds and precision | `2.50` in `1..3` → within; `3.015` in `1..3.000` → ABOVE by `0.015`; `-2.50` in `-2.00..0` → BELOW by `0.50`. Include long significant digits and trailing zeros. |
| Equality and code | At each bound (including zero) → `WITHIN_RECORDED_BOUNDS` provisionally. Synthetic `8 / 8..8 / "1001"` → within, raw code intact, semantics unknown. Repeat with null code and absent unit; preserve null, add `SEMANTICS_UNKNOWN` for both code cases, add `UNIT_UNKNOWN`. |
| Missing or invalid limits | No bounds → `NOT_EVALUABLE` + `LIMIT_UNKNOWN`; reversed → `NOT_EVALUABLE` + `LIMIT_INVALID`; one bound → `PARTIAL_BOUNDS`, check breached and unbreached on either side. A malformed supplied bound gives `NOT_EVALUABLE` + `LIMIT_INVALID` and classifies the bad text as `UNPARSEABLE`. |
| Numeric input | Preserve `" 1.0 "` raw, parsed numerically equal to `"1"`. Null/empty/spaces → `MISSING`. Commas, grouped spaces, NaN, Infinity, exponent, letters, suffix → `UNPARSEABLE` and no evaluable value. |
| Station and filters | Known station and counts match independent grouping; absent station → empty exact scope. Serial alone within station, each time endpoint, both together and combined serial/time exclude known nonmatches. Check exact boundary timestamps. |
| Bind safety and ordering | Record statement text and bind map across ordinary and quoted inputs. SQL stays constant. Repeated reads under unchanged source with tied times yield the same ordered projections, including cap boundary. |
| Limits and failures | Exercise below/exactly/above cap plus zero matches. Total and truncation agree with independent COUNT. Timeout, connection failure, mid-fetch loss and invalid scope map per §4 with no data; inspect cleanup. |
| Both comparison modes | For each mode hold its fixed field constant: one entity repeated → refuse; two comparable entities plus duplicates → `LOW_SAMPLE`; three → no warning, including **one serial at three stations**. Count all rows separately. Vary key, name, units, numeric limit equality (`1` vs `1.0`), test/product context and parseability one at a time. Verify the named refusal and source coverage. |

## 7. Definition of done

| Deliverable | Required proof |
| --- | --- |
| Oracle readiness / baseline | Restricted account and loopback verified; B receives the live count matching independent SQL. Four exact counts, profiles and uniqueness checks rerun; historical discrepancies explained. |
| Read-only repository / numeric analysis | B calls the bounded adapter; fixed SQL and binds inspected; raw rows, ordering and totals match separate SQL. Agreed A3 statuses/flags, precise deviations and preserved codes match hand expectations. |
| Demo / relationships | Three abnormal rows checked independently and coded in-range case reproduced by independent SQL. Reproducible safe references recorded. Every candidate key explicitly verified or disabled with evidence. |
| Failure behavior / optional comparison | A6 mappings survive B's caller with zero fallback rows. If shipped, A7 meets the agreed criteria in both modes and B/D reproduce accept/refuse outcomes; otherwise record optional disposition. |
| Integration readiness / final A completion | B accepts interfaces, D records independent verification, full suite outcome is recorded, no unresolved P0 defect, and §11 checked. Team gates require real student evidence. |

## 8. Handoffs to Student B and team

| Provider → consumer | Deliver at the first verified boundary |
| --- | --- |
| A1 → B1 → C4 | Callable, restricted-access prerequisites, independent live count and time. C owns two real agent calls; B checks matching request IDs and unauthenticated rejection for G0. |
| A2/A3 → B2/B3/B5/B6 | Agreed signatures, scope/coverage rules, raw nullable row, paired synthetic calculation and flag/deviation examples. B can snapshot both without recalculation. |
| A4/A5 → B/C/D5 | Reproducible scope and SQL labels, independent arithmetic, synthetic fixture and verified/disabled keys. D retains independent expectations; C confirms which fields may leave the laptop. |
| A6/A8 → B6/B7/D6 | Typed failures, empty scope and negative-test results; integrated revision, discrepancies and owners. |
| A7 → B8/D5 if shipped | Per-mode dimension, row/distinct counts and time coverage; examples at one, two and three entities and named refusals. Otherwise document the disabled extension. |

## 9. Risks, blockers and scope cut rules

Record newly discovered conflicts in `docs/decisions.md` and stop its implementation until the team decides. Keep secrets, dumps, exports and private verification material outside Git and cloud tools. Refer only to approved local evidence by safe identifier. Do not label the source timezone or assign meaning to `1001` or null without verified documentation.

Team cut order is knowledge retrieval → dashboard comparison view → A7 → dashboard polish → auxiliary station listing. Coordinate any public route change with B/C/D. Protect exact numbers, evidence resolution, live dialogue and negative paths. At team feature freeze, allow blocker fixes only.

## 10. Progress ledger and context recovery

`NOT_STARTED` = no implementation run; `BLOCKED` = named unmet prerequisite; `DONE` = required proof and receipt recorded; `SKIPPED_BY_SCOPE` = explicit team scope exclusion; `OPTIONAL_NOT_IMPLEMENTED` = unshipped conditional capability. Never use a scope disposition to close a failed P0 check.

| Step | Status | Commit | Verification | Blockers / open prerequisites | Next action |
| --- | --- | --- | --- | --- | --- |
| A1 | DONE | uncommitted | Both baseline runs verified; SQL/Python count 1524; B accepted the complete handoff; 48 tests pass | No outstanding A1 requirement; D15 accepted and unresolved for A6 | Prepare the isolated A1 changes for commit authorization; keep A2 unstarted |
| A2 | NOT_STARTED | — | — | A1, B interface | Confirm scope and ordering |
| A3 | NOT_STARTED | — | — | A2 read contract | Prepare D04/D05 fixtures |
| A4 | NOT_STARTED | — | — | A3, student SQL access | Locate candidate rows |
| A5 | NOT_STARTED | — | — | A4 | Inspect candidate keys |
| A6 | NOT_STARTED | — | — | A5, B error mapping | Exercise failure matrix |
| A8 | NOT_STARTED | — | — | A6 and B caller | Verify integrated P0 |
| A7 | NOT_STARTED | — | — | A2–A6, G1, stable P0, verified keys | Check eligibility on the selected dimension |

**Checkpoint after each future step.** Record date, task/status, branch/revision or uncommitted state, changed files, commands and actual outcomes, independent expected vs observed, safe evidence references, handoff/recipient, deviations or blocker/owner, and the next single action. Update the ledger even when blocked. Commit only on student request after verifying the staged diff.

**A1 checkpoint — 2026-11-10.** Development authorized on `feature/student-a`, based on `ce92256`; changes are uncommitted. Files are `backend/app/oracle_repo.py`, `tests/test_oracle_repo.py`, `docs/data-baseline.sql` and this ledger.

- `docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'` reported `oracle-free` healthy with `127.0.0.1:1521->1521/tcp`. No database connection was attempted. The student confirmed that the dedicated account is not ready and authorized continued work without credentials.
- With permission, installed `oracledb 26.1.0` and `pytest 9.2.0` with their transitive dependencies in `F:\tuke\hackaton\.venvs\student-a`, outside the worktree, using Python 3.13.15.
- Ran `& 'F:\tuke\hackaton\.venvs\student-a\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider` → **46 passed in 0.27s**. Ran that interpreter's `-m pip check` → **No broken requirements found.** These tests use a synthetic count of seven, separately test zero, and check driver failures without opening a socket.
- SQL checks are static. The baseline contains identity, effective privileges, role/object grants, exact table counts, column metadata and candidate constraints. Neither Oracle syntax/name resolution nor query results have been validated. Station/serial, unit/code, numeric-format and uniqueness profiles remain pending the actual column inventory.
- **B1 handoff prepared; receipt pending.** Import `count_measurements` from `backend.app.oracle_repo`. The draft Python signature accepts keyword-only `user`, `password` and `dsn`, with provisional `call_timeout_ms=5000` and `connect_timeout_seconds=5`. B supplies approved server-side settings and records retrieval time. Success is an integer, including zero. `SourceUnavailableError.code` is `SOURCE_UNAVAILABLE`; `OracleTimeoutError.code` is `TIMEOUT`. Invalid internal settings raise `ValueError` before connecting. No API route or envelope was added.
- **To unblock live A1.** The environment owner must provide an approved dedicated login to `FREEPDB1` with login privilege and SELECT access to the four required `HACKATON` tables, with effective privileges verified through the metadata queries or administrator attestation. Make `ORACLE_USER`, `ORACLE_PASSWORD` and `ORACLE_DSN` available locally to the verification process; keep the password out of chat and Git. An authorized student then runs the scalar SELECT independently, compares it with the callable, runs the baseline twice, and verifies the source column mapping before adding the remaining fixed profiles. B1 acknowledges the callable and live result. A1 remains blocked until that evidence is recorded.
- **Next single action.** Obtain the approved restricted connection settings. A2–A8 have no implementation changes; follow the dependency gates.

**A1 live-evidence update — 2026-11-10.** The student resolved the account/access blocker and supplied independent live evidence (D13/D14). Historical notes above describe the initial offline session.

| A1 check | Evidence and current disposition |
| --- | --- |
| Restricted connection | Both logs show `MAGNA_TRACE_RO`, `FREEPDB1`, `CREATE SESSION`, four explicit SELECT grants, no enabled roles, no direct column grants and no owned objects. The student separately verified loopback port `127.0.0.1:1521`. Password entry remained local to the student. |
| Independent scalar read | Student's SQL `COUNT(*)` = **1524**, live `count_measurements()` = **1524**. The supplied results match the historical measurement count; source retrieval timestamp was not supplied. |
| Other exact counts | Student's SQL returned `MACHINE_LINES=29`, `SNO_BOOKINGS_WP=150`, `WORKORDERS=58`. These replace approximate statistics for this reported source state. |
| Column inventory | Student supplied 23 columns from `ALL_TAB_COLUMNS`; A1-08–A1-15 now use those exact names, including raw numeric/null fail codes and TIMESTAMP(6). No stable key or join has been established. |
| Baseline execution and DoD | Independent inspection found all 26 expected result sets (21 nonempty and 5 empty) in the expected order in each log, covering A1-01–A1-15. No Oracle, SQL*Plus, driver or file-open error was found. Stable output matches exactly across runs. Station, serial and unit group totals, code totals and every numeric-field partition reconcile to 1524. Detailed results follow below. |
| Latest application tests (prior session) | Existing environment is `F:\tuke\hackaton\.venvs\student-a`. Python 3.13.15, oracledb 26.1.0 and pytest 9.2.0 were confirmed. `& 'F:\tuke\hackaton\.venvs\student-a\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider` → **48 passed in 0.26s**. `-m pip check` → **No broken requirements found.** This log-review session changes documentation only; application tests were not rerun. |
| TCP timeout and retries | Real-driver socket-call integration with an injected TCP timeout observed exactly one connection attempt and a 1-second timeout despite a DSN requesting 20 seconds and two retries. Synthetic tests verify the post-login `call_timeout` setting and error mapping. |
| Timeout limitation | An initial stalled-handshake probe did not finish and was terminated. A bounded repeat accepted one TCP connection, withheld the handshake and closed at 3 seconds; the callable returned `SourceUnavailableError` after **3015 ms** with a 1-second TCP timeout. Student B accepted D15 as an unresolved A6 follow-up. A hard Oracle handshake deadline and live post-login query timeout/cancellation remain unverified. |
| B1 acknowledgement | **ACCEPTED — 2026-11-10.** The student explicitly reported B's acceptance of the complete A1 handoff, exact `count_measurements()` interface, live Oracle count **1524** and documented D15 limitation. No real Copilot call is claimed. |

**Independent log audit — 2026-11-10.** Read `F:\tuke\hackaton\data\a1-run1.log` and `a1-run2.log` in place; no log or manufacturing-row export was copied into Git. Each file has 575 lines. Their sole difference is line 11, the `SYS_EXTRACT_UTC(SYSTIMESTAMP)` result: run 1 `2026-11-10T19:43:30.060494Z`, run 2 `2026-11-10T19:43:36.312311Z`. These are SQL baseline retrieval times; the earlier live Python call has no supplied retrieval timestamp. The logs contain results without echoed SQL text; coverage was checked against the 26 ordered result layouts and empty-result positions in the current baseline.

- Run 1 SHA-256 is `bb4e4ba50e6a2755fe352f638b32875a61f5ded7f96f702a1cfddbaa663a233f`. Run 2 is `0604effecf5d5dcf3d8cd672b774707a54dc6f15060ef3584089de7e12c5394a`. After replacing only line 11 and joining lines with LF, both yield `eec9a3bbfde1c853e1f57283c9f932fc658639d6abb4dda3304fdac36aacbfef`.
- A1-01–A1-07 account for identity, privilege/role/ownership checks, four table inventories/counts, 63 column-metadata rows (8/18/23/14 across the four tables) and 28 enabled/validated check-constraint rows. No primary/unique constraint appears in the returned metadata.
- A1-03 also reports a PUBLIC `INHERIT PRIVILEGES` grant on `HACKATON`, with grantable NO. Oracle documents this as a user privilege controlling invoker-rights execution. The four inspected table grants are SELECT. This observation requires no permission change for the fixed SELECT path. [Oracle privilege reference](https://docs.oracle.com/en/database/oracle/oracle-database/26/dbseg/controlling-invokers-rights-privileges-procedure-calls-and-view-access.html)

| Profile | Identical result in both runs |
| --- | --- |
| Exact table counts | Measurements 1524; machine lines 29; bookings 150; work orders 58. |
| Population and source coverage | 23 stations, 27 serials, 164 measurement names. Missing source timestamps 0. BOOK_STAMP range `2026-11-09T10:39:13.108334` to `2026-11-09T14:36:01.099779`; source timezone remains unknown. |
| Units and codes | 30 recorded unit values; missing units 0. One measurement-name group has 22 records and 2 distinct recorded unit values. Raw code 1001 occurs 30 times; raw null occurs 1494 times. Code meaning and unit compatibility remain unverified. |
| MEASURE_VALUE format screen | 1524 total = 0 missing + 1261 decimal-text matches + 263 nonmatches. |
| LOWER_LIMIT format screen | 1524 total = 0 missing + 1503 decimal-text matches + 21 nonmatches. |
| UPPER_LIMIT format screen | 1524 total = 0 missing + 1508 decimal-text matches + 16 nonmatches. |
| Bound presence | Both fields present on 1524 rows. Both missing, lower-only and upper-only counts are each 0. |
| Locator collisions | All 1524 rows share a station/serial/time scope with another row. The extended candidate collides on 32 rows. These are affected-row counts; the number of candidate collision groups was not queried. |
| Full-row duplicates | 0 rows belong to duplicate groups over all 23 fields, hence 0 exact full-row duplicate groups. A durable row key remains unestablished. |

**Numeric screening limits.** A1-12 applies the provisional anchored decimal-text regex to whitespace-trimmed text. Its nonmatch counts establish a format-screening result. Raw-text review is still needed to distinguish categorical values, unsupported numeric spellings and malformed data. Decimal conversion, numerical bound checks, deviations and measurement semantics require A3's independent tests. The presence of both bounds does not establish a valid numerical interval. Retain raw inputs and the strict parser policy; changes require a dated decision. Unit compatibility and key validation belong to A5.

**A1 acceptance disposition — DONE, 2026-11-10.** Student B's explicit acceptance closes the handoff requirement and accepts D15 as an unresolved technical limitation for A6. The recorded evidence satisfies A1's mandatory Definition of Done. This completes the A1 task; G0 remains C4's verification responsibility.

| Mandatory A1 requirement | Recorded completion evidence |
| --- | --- |
| Owner scope and usable files | `backend/app/oracle_repo.py`, its module tests, `docs/data-baseline.sql`, this progress record and append-only decisions are A-owned deliverables. No B/C/D module or public API schema was changed. |
| Oracle readiness and least-privilege reads | Student verified the healthy loopback container; both inspected logs show the restricted identity, CREATE SESSION, four SELECT grants, no enabled roles and no owned objects (D13/D16). |
| Early live callable and B receipt | Fixed measurement COUNT returns an integer; independently executed SQL and student live Python both returned 1524. B accepted the interface, live result and complete handoff (D18). |
| Complete baseline and repeatability | All 26 expected result sets cover table counts, metadata, population, units/codes, source coverage, numeric screening and row uniqueness. Both logs have no detected SQL errors and identical stable output; hashes and retrieval timestamps are recorded above. |
| Correctness and failure checks | Final A1 run of `& 'F:\tuke\hackaton\.venvs\student-a\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider` → **48 passed in 0.23s**. `-m pip check` → **No broken requirements found.** Synthetic counts, error mapping, cleanup, SQL safety and timeout/retry configuration checks pass. |
| Contracts and provisional behavior | B accepted the exact synchronous signature below. Canonical source/timeout codes are reused. Five-second defaults remain provisional. D15's login-deadline gap and unverified live post-login timeout behavior are accepted for A6 follow-up. |
| Evidence and Git hygiene | Local log hashes were rechecked during finalization; they still match. Only aggregate findings and metadata are included in the A1 documentation. Logs, passwords and generated bytecode are excluded from the staged five-file A1 change. Complete source/diff review and both Git whitespace checks passed; explicit commit authorization remains pending. |

**A1 → B1 handoff.** Import from `backend.app.oracle_repo`. The exact synchronous signature is

```python
count_measurements(
    *,
    user: str,
    password: str,
    dsn: str,
    call_timeout_ms: int = 5000,
    connect_timeout_seconds: int = 5,
) -> int
```

Use account `MAGNA_TRACE_RO`, DSN `127.0.0.1:1521/FREEPDB1`, and a password available transiently through the approved server-side credential mechanism. Passwords must stay out of chat, logs and files. The verified returned count is **1524** (student live run). B records the UTC retrieval time at its call. Errors are `SourceUnavailableError` with code `SOURCE_UNAVAILABLE` or `OracleTimeoutError` with code `TIMEOUT`; invalid internal settings raise `ValueError` before connecting. The count is uncached and has no fallback. B accepted this complete handoff on 2026-11-10, including D15, as relayed by the student in this chat. B1 owns route wiring, server-side credentials, authentication and the API envelope. C4 owns proof in the real tenant.

**A6 follow-up, accepted and unresolved.** Preserve D15 as OPEN. Establish the login/handshake deadline and connector budget with B, then validate live post-login timeout/cancellation, cleanup and canonical error mapping under the restricted account. The existing TCP timeout and per-round-trip setting provide the scopes documented above; no hard handshake deadline or live post-login timeout has been verified. A6 remains NOT_STARTED.

**Next single action.** Await explicit authorization to commit the reviewed five-file A1 change. Suggested message is `A1: verify restricted Oracle count and data baseline`. A2–A8 remain NOT_STARTED.

**Resume.** Read the worktree’s `AGENTS.md`, this plan and `docs/decisions.md`. Run `git status --short --branch`, `git log -5 --oneline --decorate` and inspect pending diffs. Use the ledger to open only the next task's source section, modules, tests and evidence references. Recheck prerequisites and any changed baseline, then resume the first incomplete required step. Surface a blocker before changing scope.

## 11. Final Student A acceptance checklist

- [ ] B acknowledges the frozen interfaces and the implemented A outputs agree with the canonical product and architecture contracts.
- [ ] A1 live count received and baseline rerun; A2 reads and limits checked under SELECT-only access.
- [ ] A3 hand-derived expectations match; A4 findings reproduced by D; G1 evidence recorded by students.
- [ ] A5 keys and unknowns recorded; A6 checked through B with no partial or fallback data.
- [ ] A8 integrated revision, whole-suite command/result, B receipt and D check recorded. A7 either validated in both modes or explicitly left disabled.
- [ ] Changed paths belong to A; staged diff contains no secrets, private rows or binaries. Ledger identifies actual commits, gate owners and outstanding external proofs.
