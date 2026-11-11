# MAGNA TRACE

*Evidence-Driven Diagnostic Copilot* for MAGNA Hackathon **Task 9 — AI asistent
pre technikov údržby a testovania**. The project aims to help technicians inspect
abnormal measurements, distinguish observations from hypotheses, and hand over
an investigation with traceable evidence and explicit unknowns.

**Current runnable scope: local React dashboard + SYNTHETIC mock API.** This
checkout does not demonstrate live Oracle/backend or Microsoft Copilot
integration. The dashboard is a parallel read-only view; the required MVP still
includes the real Copilot journey. No downtime savings, diagnostic accuracy or
confirmed physical causes are claimed.

## Team and sources of truth

| Student | Responsibility |
| --- | --- |
| A | SELECT-only Oracle access, Decimal measurement analysis, data verification and conditional comparisons |
| B | FastAPI contract, authenticated endpoints, cases, evidence and diagnostic snapshots; integration into main |
| C | Microsoft Copilot Studio, tool specification, authentication and permitted HTTPS connection |
| D | React dashboard, independent QA, README and presentation material |

Read [agent rules](docs/AGENTS.md), [product requirements](docs/product.md),
[architecture](docs/architecture.md), [delivery plan](docs/plan.md) and
[decisions](docs/decisions.md). Approved design is distinct from implementation
or a passed gate.

## Architecture

The implemented local path is:

```text
React + TypeScript → relative /api/v1 requests → Vite development proxy
                                              → Node SYNTHETIC fixture server
```

Vite adds `X-API-Key` server-side. React receives no credential. The dashboard
displays returned Decimal strings or null without calculating deviations,
rounding values or deriving diagnostic statuses. Both range status and quality
flags remain separate from the raw fail code. Neither `1001` nor null establishes
PASS/FAIL; the meaning is unknown. P0 assessment remains `UNDETERMINED`.

The **target**, still pending integration in this checkout, is:

```text
Technician → Microsoft Copilot Studio → authenticated HTTPS tools
           → FastAPI /api/v1 → in-memory cases and captured evidence
                            → Python Decimal analysis → SELECT-only Oracle
```

The backend owns facts, calculations, evidence IDs and case state. Copilot owns
dialogue and tool selection. Oracle access must use fixed parameterized SELECTs;
the dashboard never connects to Oracle. P0 uses one backend worker and loses
cases on restart. These are architecture requirements, not verified runtime
claims. See [architecture §§2–6](docs/architecture.md).

## Local setup and startup

Use the existing **Node 22** environment and npm, as documented in
[frontend/README.md](frontend/README.md). A browser is needed for the dashboard;
the browser test suites also require Firefox on `PATH`. No Oracle, tunnel or
Copilot credentials are needed for this synthetic local path.

From the repository root, start the mock in terminal 1 (Bash):

```bash
cd frontend
npm install
read -rsp 'Local TRACE_API_KEY: ' TRACE_API_KEY; echo
export TRACE_API_KEY
export TRACE_API_TARGET=http://127.0.0.1:8001
npm run mock
```

Choose a nonempty throwaway local key at the hidden prompt. In terminal 2,
starting from the repository root, enter the **same** key:

```bash
cd frontend
read -rsp 'Local TRACE_API_KEY: ' TRACE_API_KEY; echo
export TRACE_API_KEY
export TRACE_API_TARGET=http://127.0.0.1:8001
npm run dev
```

Open the loopback URL Vite prints, normally `http://127.0.0.1:5173`. The mock
listens on `127.0.0.1:8001`. `TRACE_MOCK_PORT` can change its port; update
`TRACE_API_TARGET` to match. Missing keys fail startup. Stop each process with
Ctrl+C. Do not put keys into `VITE_*`, browser storage, source files or Git.
`node_modules/`, `dist/`, `.env` and `.env.*` are ignored under `frontend/`.

Choose **SYNTHETIC-STATION**, then **Open diagnostic case**. Inspect the findings,
warnings, and Observed/Calculated evidence links. For handover, first submit the
existing synthetic answer using the exact preparation command in
[frontend/README.md — Preparing the existing post-answer handover fixture](frontend/README.md#preparing-the-existing-post-answer-handover-fixture),
then select **Load handover**. There is no answer-entry UI. Reopening the case
resets the answer; the pinned replay has no pre-answer handover and returns an
HTTP 501 replay-limit notice in that state.

`npm run build` creates the static bundle. `npm run preview` previews that bundle;
it does not provide the development API proxy. Changing the proxy target alone
does not implement D4: the current client explicitly requires responses marked
`X-Trace-Mock: SYNTHETIC`. Backend/Oracle startup commands are not available here:
`backend/` contains only `.gitkeep`, and no `copilot/` implementation is present.

## B2 contract and available mock operations

The local [B2 artifacts](frontend/mock/b2/README.md) and
[pin metadata](frontend/mock/b2/PINNED.json) come from
[test1/contracts/b2 at the pinned commit](https://github.com/fpkjpkjjjn/test1/tree/145652f917cd8b5ccda40f214a03ba45d490150d/contracts/b2).

**Pinned SHA: `145652f917cd8b5ccda40f214a03ba45d490150d`. Corrected B2 v1
candidate; not the final freeze.** `schemas.json`, `examples.json`, README and
proxy example are preserved contract artifacts. Mock tests check their pinned
Git blob hashes.

| Operation | HTTP route | Local availability |
| --- | --- | --- |
| `list_stations` | `GET /api/v1/stations?q=SYNTHETIC&limit=20` | Station selector; response `case_id` is null |
| `open_case` | `POST /api/v1/cases` | Exact pinned scope; starts/resets the single fixture case |
| `get_evidence` | `GET /api/v1/cases/{case_id}/evidence/{evidence_id}` | Captured OBSERVED/CALCULATED evidence; TECHNICIAN_REPORTED after the answer |
| `record_answer` | `POST /api/v1/cases/{case_id}/answers` | Exact fixture request via local preparation; `data` is the updated snapshot directly |
| `get_handover` | `GET /api/v1/cases/{case_id}/handover` | Exact post-answer fixture in the dashboard |

All five fixture successes use HTTP 200 and the B2 envelope with `request_id`,
`retrieved_at`, `status`, `case_id`, `data` and `error`. Direct mock requests with
missing/wrong keys return the pinned HTTP 401 error. Evidence errors use GET
routes. Decimal results remain strings or null, including valid scientific
notation in computed strings. All fixture IDs, timestamps and results are
**SYNTHETIC**, with `X-Trace-Mock: SYNTHETIC` and `Cache-Control: no-store`.

The mock replays fixed examples; it does not query Oracle or calculate results.
Unsupported requests return plain-text HTTP 501, a harness limitation rather
than a proposed B2 error. It does not implement arbitrary searches/answers,
multiple cases, real expiry or persistent storage. No comparison route is enabled.

## Testing and recorded evidence

Run from `frontend/` after installation:

```bash
npm run build
npm run test:mock
npm run test:dashboard
node --test scripts/transport.test.mjs
```

The mock suite checks fixture integrity, five operations, authentication, proxy
behavior and absence of its random test key in React sources and `dist/`.
Dashboard tests exercise D2/D3 in headless Firefox, including evidence, handover,
errors and stale-data cleanup. The separate transport suite injects local
connection failures and malformed responses. It is not included implicitly in
`test:dashboard`. Tests manage their own local servers.

The [D6 execution log](tests/d6_execution_log.md#d62--targeted-validation-fixes-and-retest)
records the **2026-11-10 targeted retest**: build PASSED, mock suite PASSED,
two dashboard tests PASSED, and 41 transport leaf scenarios PASSED (42 TAP tests
including the parent). The five earlier failing scenarios passed after the two
targeted validation fixes; the original failure record is retained. These are
historical local synthetic results, not tests rerun for this documentation update
or live integration evidence.

Independent scenarios and hand arithmetic are in the
[D5 checklist](tests/qa_checklist.md) and [expected values](tests/expected_values.md).
O01–O03 record Student D's reported manual read-only SQL verification; their
API/Copilot comparisons and backend evidence IDs remain PENDING. D5 documents
retain historical dependency notes from their preparation; the candidate
artifacts now available above do not establish a final B2 freeze. D6.1 records a
bounded tracked-snapshot secrets scan, not proof of absence of all secrets.

## Current status and remaining integration

| Area | Confirmed status in this checkout |
| --- | --- |
| D1–D3 | Local scaffold, fixture server/proxy, station/case/findings, evidence and handover implemented against the candidate |
| D5 | Independent expectations and redacted manual SQL summary recorded; integrated comparisons pending |
| D6 | Local negative tests and targeted validation retest recorded; live backend/Oracle/Copilot checks PENDING |
| D7.1 | README, [Slovak pitch](tests/demo_pitch_sk.md) and [backup preparation plan](tests/demo_backup_plan.md) prepared; script timing and recording PENDING |
| Live MVP / gates | Not established by these mock results; full D7 and G0–G3 sign-off are not claimed |

Remaining dependencies are A's Oracle/analysis and verified source context,
B's final agreed B2 contract and authenticated case/evidence API, and C's real
tenant, tool import/authentication, permitted HTTPS route and cloud-data
approval. See decisions D10–D12. D4 live dashboard integration is pending.
The mandatory P0 proof is two real Copilot journeys including autonomous
`record_answer`, SQL-checkable findings, resolved evidence and handover.

Code meanings, units where absent, source timezone and valid record relationships
remain unknown; bound equality is provisional. No physical cause, repair advice
or machine control is provided. Persistent history, richer exports, comparisons
and knowledge retrieval are outside the implemented scope. Keep the repository
private and keep credentials, Oracle dumps and confidential rows out of Git and
demo recordings.
