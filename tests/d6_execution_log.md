# D6 execution log

## D6.1 — Git-tracked repository secrets scan

Executed 2026-11-10 at 20:51:55 UTC, with candidate review completed in the same session. Reviewer: Student D's coding agent. Scope authorized: D6.1 only, following `docs/AGENTS.md` §§3/5/8/12 and `docs/plan.md` §3 D6.

- Branch: `feature/nikita`.
- Scanned commit: `7187a97f8d5d48f29f61e637c88aaf53907c9bcf`.
- Initial `git status --short --branch`: clean working tree on the expected branch.
- Inventory: 38 Git-tracked project files; 38 scanned, 320,705 bytes; zero unreadable blobs and zero binary files.
- Exclusions: any path component `.git`, `node_modules` or `dist`. No tracked inventory entry fell under these exclusions. Git metadata was accessed only through Git commands; `.git` contents were not scanned as project files.
- Only this execution log was created. No credentials were deleted, rotated, modified, tested against providers or printed. No dependencies were installed, application builds/tests started, or live endpoints contacted. No commit or push was performed.

### Method and limits

Used `git status --short --branch`, `git branch --show-current`, `git rev-parse HEAD` and `git ls-files -z`. A Python standard-library scanner read every included committed blob using `git show HEAD:<tracked-path>` with Git error output suppressed. The initially clean working tree/index matched the committed snapshot. The new execution log is untracked and is not included in the 38-file baseline.

Checks covered private-key headers; recognizable GitHub/GitLab, Google, AWS, Slack, OpenAI, Stripe, SendGrid and npm token formats; JWT-like strings; credential-bearing connection URLs and Oracle login commands; Basic/Bearer literals; credential-named assignments; and quoted token-like literals of at least 32 characters with Shannon entropy at least 4 bits per character. Tracked path checks covered environment files and conventional credential/configuration/key filenames, including npm, netrc, AWS/Docker and private-key/container formats. Content matches were reported only as path, line and category; matched values and surrounding source lines were never emitted by the scanner.

A supplemental pass checked cloud connection secrets, credential-bearing URL query parameters and additional conventional environment/credential filenames across the same 38 blobs. It completed with zero candidates.

Reviewed generic matches separately rather than suppressing an entire fixture directory. The B2 examples blob matched its previously pinned source Git blob hash. Its matched case IDs, evidence IDs and route strings belong to the explicitly synthetic contract fixture. Dependency integrity fields were classified as package verification metadata, not credentials. Runtime environment references and random test-key generation do not embed a stored key. Interactive secret entry and explicitly synthetic invalid-auth literals are not real credential disclosures.

This is a custom pattern/heuristic scan of the current committed snapshot, **not proof that the repository contains no secrets**. It can miss unrecognized formats, low-entropy passwords, split/encoded/encrypted values or sensitive data without credential-like context. It did not inspect earlier history, other branches, ignored/untracked files, remote systems or provider validity. Those areas are outside this D6.1 result. No provider-specific scanner or external service was installed or used.

### Executed results

PASSED means the stated local check completed without an unresolved possible credential under these rules. FAILED means a possible real credential or scan failure remains unresolved. PENDING means the check was not executed; it is never a pass.

| Check | Status | Redacted result |
| --- | --- | --- |
| Expected branch and initial Git state | PASSED | Expected Student D branch; clean initial working tree/index. |
| Current tracked-content coverage | PASSED | All 38 included files scanned; zero read errors. |
| Recognizable credential and private-key patterns | PASSED | No unresolved possible real credential identified by these patterns. |
| Suspicious tracked environment/credential paths | PASSED | Zero matching tracked paths. |
| Generic assignment/entropy candidate review | PASSED | Remaining matches resolved as the non-secret categories below; zero unresolved candidates. |

**FAILED: none.** No executed scan check or possible credential review remains unresolved. This does not certify absence of all secrets.

### Redacted reviewed match locations

These are reviewed non-secret matches, not confirmed credential leaks. No matched values are retained here. Line numbers refer to the scanned commit.

| File path | Line numbers | Issue category / disposition |
| --- | --- | --- |
| `frontend/README.md` | 34 | Reviewed interactive secret prompt; no embedded value. |
| `frontend/mock/b2/README.md` | 75 | Reviewed authentication placeholder. |
| `frontend/mock/b2/examples.json` | 24, 153, 163, 200, 210, 240, 250, 287, 297, 327, 337, 374, 384, 416, 426, 458, 599, 608, 785, 806, 832, 853, 874, 886, 902, 914, 978, 999 | Reviewed synthetic B2 case IDs. |
| `frontend/mock/b2/examples.json` | 51, 52, 67, 68, 85, 86, 98, 110, 130, 154, 165, 201, 212, 215, 241, 252, 288, 299, 302, 328, 339, 375, 386, 389, 417, 428, 485, 486, 501, 502, 519, 520, 526, 542, 554, 573, 574, 584, 635, 636, 651, 652, 669, 670, 676, 692, 704, 734, 735, 887 | Reviewed synthetic B2 evidence IDs. |
| `frontend/mock/b2/examples.json` | 148, 195, 235, 282, 322, 369, 411, 443, 594, 866, 970, 991 | Reviewed synthetic B2 route strings. |
| `frontend/mock/b2/vite.proxy.example.ts` | 6 | Runtime environment reference; no stored credential. |
| `frontend/mock/server.mjs` | 99 | Runtime environment reference; no stored credential. |
| `frontend/package-lock.json` | 24, 41, 58, 75, 92, 109, 126, 143, 160, 177, 194, 211, 228, 245, 262, 279, 296, 313, 330, 347, 364, 381, 398, 415, 432, 449, 466, 480, 494, 508, 522, 536, 550, 564, 578, 592, 606, 620, 634, 648, 662, 676, 690, 704, 718, 732, 746, 760, 774, 788, 802, 816, 830, 837, 847, 857, 864, 906, 924, 939, 958, 965, 978, 1007, 1016, 1028, 1074, 1080, 1090, 1107, 1121 | Reviewed dependency integrity metadata. |
| `frontend/scripts/case-details.test.mjs` | 15, 22, 24, 27, 28 | Runtime test-key generation/environment references; no stored credential. |
| `frontend/scripts/dashboard.test.mjs` | 15, 23, 25, 28, 29 | Runtime test-key generation/environment references; no stored credential. |
| `frontend/scripts/dashboard.test.mjs` | 95 | Reviewed synthetic invalid-auth test literal. |
| `frontend/scripts/mock.test.mjs` | 36, 43, 56, 58, 61, 62 | Runtime test-key generation/environment references; no stored credential. |
| `frontend/scripts/mock.test.mjs` | 110 | Reviewed synthetic invalid-auth test literal. |
| `frontend/vite.config.mjs` | 8 | Runtime environment reference; no stored credential. |

### Live D6 checks — not executed

| Check | Status | Reason / prerequisite |
| --- | --- | --- |
| Live backend authentication and public ingress | PENDING | Requires B/C's running authenticated backend and approved endpoint. No calls made. |
| Real no-data query with exact scope and no substitute measurements | PENDING | Requires the live backend/Oracle path. Synthetic fixture tests are separate evidence only. |
| Real Oracle unavailability and query timeout | PENDING | Requires a controlled A/B environment. No outage induced. |
| Live invalid/foreign evidence IDs and case isolation | PENDING | Requires backend-issued case/evidence IDs; no IDs fabricated. |
| Live unknown/expired/pre-restart case handling | PENDING | Requires B's case lifecycle and controlled restart/expiry checks. |
| Real Copilot end-to-end journey and negative paths | PENDING | Requires C's live tenant/connector; local checks cannot establish gate passage. |

D6.1 is complete for the stated tracked-snapshot scan. Overall D6 and G3 remain incomplete. Previously executed mock/UI tests are not rerun or relabeled as live results here. Further D6 work must retain separate mock versus live status and redacted evidence; no next task was started.

## D6.2 — Frontend transport and malformed-response negative tests

Executed 2026-11-10 on `feature/nikita`, production baseline commit `eeb0a769c2a9a8303ad21cb3e7a466ef378bab8b`. Initial working tree was clean. Scope: frontend test additions and this log only. This section records a later run; it does not change the historical D6.1 result.

### Existing coverage and added scope

Reviewed `docs/AGENTS.md`, `docs/plan.md`, `docs/architecture.md`, `docs/decisions.md`, this log, the production frontend API/UI and all existing frontend test files. Existing suites already cover valid B2 error envelopes, missing/wrong-key responses, unknown/foreign evidence, stale answers, failed handover refresh, case reset and late evidence completion. The pre-answer handover check covers the particular non-JSON HTTP 501 replay-limit response. Those scenarios were not duplicated in the new suite.

Added only `frontend/scripts/transport.test.mjs`, reusing the existing Firefox helper. No production source, package scripts, dependencies, proxy, mock server or pinned B2 artifact was changed. Run the new suite explicitly from `frontend/` using `node --test scripts/transport.test.mjs`; it is not implicitly included in the unchanged `npm run test:dashboard` command.

The new test uses an ephemeral loopback relay in front of the unchanged synthetic mock and the actual Vite proxy. Every scenario first loads a valid synthetic case, evidence and post-answer handover. The existing exact answer fixture is used only to prepare the test state. Faults are then injected at transport/HTTP boundaries. Corrupted payloads are cloned from fixtures; they are deliberately invalid inputs, not new B2 schemas, examples, error codes or promises about backend behavior. Real connection-loss checks close only the test Vite server, causing native browser fetch failures. No live backend, Oracle or Copilot calls were made.

### Actual commands and outcomes

Commands ran from `frontend/` with permission to start loopback servers and an isolated headless Firefox. No dependencies were installed. Servers and browser profiles were cleaned up by the tests.

| Command | Status | Actual outcome |
| --- | --- | --- |
| `node --test scripts/transport.test.mjs` | FAILED | Exit 1. Final run: 41 leaf scenarios, 36 passed and 5 failed. Node TAP counts 42 tests and 6 failures because it additionally counts the failed parent test; there are five failing scenarios, not six separate defects. |
| `npm run test:dashboard` | PASSED | Exit 0; both existing D2/D3 browser tests passed. |
| `npm run test:mock` | PASSED | Exit 0; existing mock/proxy suite passed, including its `npm run build`, pinned-artifact integrity and random-key scans of React sources and `dist/`. |

The initial negative run found the same five failures. A second run added redacted DOM-visibility diagnostics to failing assertions and confirmed them. No failing assertion was weakened, skipped, deleted or marked as an expected pass. The required-error assertion failed with: `Malformed/failed requests must display a clear error, not a successful view`. Diagnostics contain only visibility booleans and option counts, not credentials or source records.

### PASSED — local synthetic checks

| Negative scenario | Coverage / observed result |
| --- | --- |
| Upstream socket reset | Passed for station list, case opening, evidence and handover. Vite reports the local proxy failure; the UI displays a technical error rather than diagnostic fallback data. |
| HTTP 500 HTML, with and without the synthetic marker | Passed for all four operations. Non-JSON or missing-marker errors are displayed; response HTML is not used as findings. |
| HTTP 200 truncated JSON | Passed for all four operations; parse failures display errors. |
| HTTP 200 JSON null | Passed for all four operations; invalid top-level response rejected. |
| HTTP 200 invalid envelope status | Passed for all four operations; no successful result rendered. |
| HTTP 200 missing operation data | Passed for all four operations; empty data rejected. |
| HTTP 500 with success-shaped JSON | Passed for all four operations; non-success HTTP status is not ignored merely because the payload resembles a success fixture. |
| Numeric Decimal corruption | Passed for open-case findings, CALCULATED evidence and handover observations; numeric deviations are rejected rather than accepted as string results or recalculated. |
| Native browser connection loss | Passed for handover, evidence, case opening and station reload after shutting down only the test Vite server. Clear connection errors appear; case/list requests leave no stale diagnostic view. |

For passing case/list failures, earlier case, evidence and handover views disappear and no substitute rows are displayed. For passing evidence/handover refresh failures, the affected old detail view disappears; independent earlier findings remain unchanged with their original `observations_retrieved_at`. They are not assigned a fresh retrieval time. The tests verify that the intended injected response was actually reached before asserting UI outcomes.

### FAILED — production validation defects, not fixed in this task

| ID | Production location | Reproduction / actual result | Expected result from pinned B2 |
| --- | --- | --- | --- |
| D6-RESP-01 | `frontend/src/api.ts:103` | Remove required `request_id` and `retrieved_at` from an otherwise unchanged HTTP 200 success fixture. All four operations accept it without a visible error: station choices load, or the case/evidence/handover success view is displayed. Four failing scenarios. | Reject malformed success envelopes and show a clear error; do not present them as successful responses. The fields are required by `ListStationsResponse`, `OpenCaseResponse`, `GetEvidenceResponse` and `GetHandoverResponse` in the pinned schema. |
| D6-RESP-02 | `frontend/src/api.ts:152` | Replace OBSERVED evidence `raw_fields` with an empty object. It is accepted and shown as evidence details without an error. One failing scenario. | Reject incomplete captured evidence and display an error. Pinned `RawFields.required` specifies the source fields; an empty object does not satisfy it. Checking only the types of existing values does not establish required-field presence. |

These failures are response-validation gaps. The injected numeric/text data came from synthetic fixtures; this run does not claim that the frontend calculated new physical diagnoses. It cannot assert that **all** malformed responses fail closed: malformed success responses in the two categories above are still presented as successful. Both defects require separately authorized production-code changes and retesting. Production code was deliberately left unchanged under this task's restriction.

### PENDING — unresolved work and live checks

- Production fixes and reruns for D6-RESP-01 and D6-RESP-02: **PENDING**, outside this test-only authorization. The red tests remain in the new suite.
- Live-backend authentication/ingress, real no-data queries, real Oracle unavailability/timeouts, backend evidence/case isolation, expiry/restart and the real Copilot journey: **PENDING**, unchanged from the live-check table above. Local relay disconnection is not a real Oracle outage or backend timeout test.
- Overall D6 and G3: **PENDING / incomplete**. Passing the existing suites does not override the new suite's FAILED result or establish a live gate pass.

Only the new frontend test file and this execution log changed. No credentials were printed, no pinned fixture changed, no production fix was attempted, and no commit or push was performed. Stop point: D6 transport/malformed-response testing completed with the two documented defects outstanding; no next task was started.

## D6.2 — Targeted validation fixes and retest

Retested 2026-11-10; commands completed by 21:13:59 UTC on `feature/nikita`. Authorization for this continuation explicitly allowed only the two confirmed production fixes and an appended execution record. The initial working tree already contained the preceding failure log changes and the untracked `frontend/scripts/transport.test.mjs`; both were preserved. The original failure record above remains unchanged and describes the pre-fix state.

### Targeted changes

Only production file changed: `frontend/src/api.ts`.

- **D6-RESP-01:** The common success-envelope check now requires string-valued `request_id` and `retrieved_at`. Missing either field fails validation for list stations, open case, evidence and handover before any success data is returned to React. Existing error-envelope handling runs first and is unchanged.
- **D6-RESP-02:** OBSERVED evidence now checks the eight required `RawFields` keys from the pinned B2 schema, rather than relying only on the types of values already present. Nullable raw values remain allowed; `station_number` must be a string as specified. Incomplete captured evidence produces the existing technical error instead of a valid observation view.

The changes add no API fields, calculations, coercion, formatting, fallback data, dependencies, live integration or P1 behavior. The UI's existing error display, abort handling and stale-data cleanup are unchanged. This is a targeted validation correction, not a claim of complete JSON Schema validation for every possible malformed response.

### Actual retest commands

All commands ran from `frontend/`. Browser tests used isolated headless Firefox and ephemeral local synthetic servers only. The socket-reset proxy errors printed by the transport suite are intentional fault injection, not test failures. All processes completed and test-server/browser cleanup ran.

| Command | Status | Actual result |
| --- | --- | --- |
| `node --test scripts/transport.test.mjs` | PASSED | Exit 0; all 41 leaf scenarios passed. TAP reports 42 passed tests including the parent, zero failures, zero skipped/todo tests. All five formerly failing scenarios now pass with their original assertions unchanged. |
| `npm run build` | PASSED | Exit 0; TypeScript checking and Vite production build succeeded. |
| `npm run test:mock` | PASSED | Exit 0; one suite test passed, including its build, exact fixture integrity, auth/proxy behavior and random-key scan of React sources and `dist/`. |
| `npm run test:dashboard` | PASSED | Exit 0; both existing D2/D3 browser tests passed, including evidence/handover fidelity, error display and stale-request cleanup. |
| `git diff --check` and preservation checks | PASSED | No whitespace errors; previous log content preserved as a byte-for-byte prefix. All existing frontend files except `src/api.ts`, including every test and pinned artifact, are unchanged from the start of this continuation. |

The four missing-envelope-metadata scenarios now display technical errors and do not render the malformed response as a fresh successful case, station list, evidence or handover. The empty-raw-fields evidence scenario now displays an error and removes the previous evidence details. Other passing tests continue to verify that failed detail refreshes retain independent earlier findings only with their original source retrieval timestamp, without inventing new findings.

### Current disposition

- **PASSED / resolved in this targeted retest:** D6-RESP-01 and D6-RESP-02; all five original failing scenarios pass without test or fixture changes.
- **FAILED:** none in the commands executed during this retest. No additional confirmed defect emerged within the tested scope. The historical FAILED results above remain valid records of the pre-fix run.
- **PENDING:** every live-backend, Oracle and Copilot check listed earlier remains unexecuted and PENDING. Overall D6/G3 sign-off remains incomplete; these local synthetic results do not establish gate passage.

This continuation changed only `frontend/src/api.ts` and appended this log. No tests, expected assertions, pinned B2 files, backend, docs, proxy or other frontend production files were modified. No commit or push was performed. Stop point: the two authorized validation fixes and requested retesting are complete; no next task was started.
