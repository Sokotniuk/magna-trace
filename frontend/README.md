# MAGNA TRACE frontend — D4 transport support

Local Vite dashboard with explicit **mock / live API** modes and a
**SYNTHETIC ONLY** B2 fixture replay server. Mock mode remains the default.
D2 provides station selection, case opening and a findings table. D3 adds
case-local evidence details and a read-only active-case handover. D4 adds live
B2 transport support without fallback to mock. Successful live findings,
evidence and handover remain unverified; an answer-entry workflow and P1
features are not implemented.

## Pinned contract

Source: <https://github.com/fpkjpkjjjn/test1/tree/145652f917cd8b5ccda40f214a03ba45d490150d/contracts/b2>

Pinned commit: **145652f917cd8b5ccda40f214a03ba45d490150d**.
This is the corrected **B2 v1 candidate**, not the final freeze.
`mock/b2/README.md`, `schemas.json`, `examples.json` and `vite.proxy.example.ts`
are exact copies of the four source files at that commit. These are contract
artifacts, not duplicated Pydantic models or another production backend.
`mock/b2/PINNED.json` records the commit and source Git blob hashes; the smoke
test checks each copied file byte for byte against its pinned hash.
No external repository was merged. The external README's integration-provider
discussion does not change this repository's approved integration requirements.

Every mock response carries `X-Trace-Mock: SYNTHETIC` and `Cache-Control: no-store`.
The fixtures' fixed IDs, timestamps and numbers are SYNTHETIC, never Oracle data,
fresh observations, causal conclusions or gate evidence. Envelopes and HTTP codes
are replayed unchanged; no diagnostic arithmetic is performed here.

## Local startup

Use the existing Node 22 environment. From this directory:

```bash
npm install
# Choose a local development key in your shell; never commit its value.
read -rsp 'Local TRACE_API_KEY: ' TRACE_API_KEY; echo
export TRACE_API_KEY
export TRACE_API_TARGET=http://127.0.0.1:8001
export VITE_TRACE_API_MODE=mock
npm run mock
```

In a second terminal, export the **same** `TRACE_API_KEY` and target, then:

```bash
export VITE_TRACE_API_MODE=mock
npm run dev
```

Open the loopback URL Vite prints (normally `http://127.0.0.1:5173`). The mock
listens on `127.0.0.1:8001`; `TRACE_MOCK_PORT` can change its port. Update
`TRACE_API_TARGET` accordingly. Missing mock or Vite credentials fail startup.
The Vite configuration also supports server-only `.env.local` values; the mock
reads shell environment variables, so export the key for both processes.
`.env` and `.env.*` are ignored.

### Explicit live mode

Keep the real FastAPI process running according to its owner's instructions.
From `frontend/`, stop any previous Vite process, enter the backend's existing
key at the hidden prompt and select its actual loopback address. For the
existing default backend target on port 8000:

```bash
read -rsp 'Backend TRACE_API_KEY: ' TRACE_API_KEY; echo
export TRACE_API_KEY
export TRACE_API_TARGET=http://127.0.0.1:8000
export VITE_TRACE_API_MODE=live
npm run dev
```

Change the target if your backend listens on a different port; a remote target
must use trusted HTTPS. `TRACE_API_KEY` and `TRACE_API_TARGET` are read by the
Node proxy only. The single public setting `VITE_TRACE_API_MODE` contains only
`mock` or `live`; it must never contain credentials. Invalid mode values fail
Vite startup/build. If unset, the mode defaults to `mock` (including builds).
Restart Vite and reload the browser after switching either mode or target;
changing a target never automatically selects live mode.

Live mode GETs `/api/v1/stations` without the synthetic search term and POSTs
only the selected `station_number` when opening a case. B2 makes time and serial
filters optional; no synthetic date range is sent. It accepts unmarked B2
responses through the existing validators, displays backend error codes/messages
and rejects any response carrying `X-Trace-Mock`. It never retries against a mock
or supplies fixture findings on failure. The labels identify **LIVE API mode**,
not a claim that a returned observation has independently passed SQL verification.

Student D reports HTTP 200 for backend health/readiness and authenticated echo
(including echo through Vite), with 1524 measurement rows. The station request
through Vite currently returns HTTP 503 `SOURCE_UNAVAILABLE` with
`A2 station adapter is not connected`. These are supplied observations, not live
checks executed by this frontend change. The dashboard now displays that B2
error instead of requiring a synthetic marker. Successful live station/case/
evidence/handover verification remains pending A2/A3 and B's integration.

To return to mock mode, restart Vite with:

```bash
export VITE_TRACE_API_MODE=mock
export TRACE_API_TARGET=http://127.0.0.1:8001
read -rsp 'Local TRACE_API_KEY: ' TRACE_API_KEY; echo
export TRACE_API_KEY
npm run dev
```

Start `npm run mock` in another terminal with the same local key, as above.
No live credential is needed by the synthetic server. Builds bake in the public
mode: use `VITE_TRACE_API_MODE=live npm run build` for a live-labelled build.
Static preview still has no API proxy. The repository's root README and D7 pitch
describe the earlier synthetic-only preparation snapshot; they are deliberately
outside this D4 change.

## D2 dashboard

In default mock mode, the station selector loads `list_stations` through the Vite proxy. Choose
`SYNTHETIC-STATION`, then select **Open diagnostic case**. The request uses the
exact pinned replay scope shown on screen; `src/demo-scope.json` contains only
the request's from/to/serial fields, verified against the pinned fixture by the
UI test. No response fixtures are imported into React or used as error fallbacks.

The table displays measurement, raw value/unit/bounds, returned deviation, range
status, quality flags and raw fail code in separate columns. Observed and
calculated evidence IDs now open their captured details through GET requests. Raw
strings retain their precision/whitespace; null is visibly rendered as `null`.
ABOVE, BELOW, WITHIN_RECORDED_BOUNDS and NOT_EVALUABLE have distinct labels and
styling; they are never derived from values or codes. In particular the pinned
in-range Count row retains code `1001` without a pass/fail diagnosis.

Warnings and source retrieval time are displayed as returned. Changing the
station, reloading stations or opening another case clears prior findings.
Errors show the returned code/message and exact queried scope when supplied;
network, non-JSON and unexpected responses produce a technical error without
substitute findings. Loading disables duplicate submissions. Mock mode accepts
only responses labeled `X-Trace-Mock: SYNTHETIC`; live mode rejects marked mock
responses. Neither mode silently switches to the other.

## D3 evidence and handover

Open a case, then select either reference in a findings row. Observations use
`evidence_id`; calculations use `calculation_evidence_id`. The dashboard retains
the API-issued active `case_id` and GETs
`/api/v1/cases/{case_id}/evidence/{evidence_id}`. It checks the returned case and
evidence ID before displaying the classification and exact captured JSON.
OBSERVED includes raw source fields, queried scope, source timestamp, row
ordinal and retrieval time. CALCULATED includes input references, rule and
result; input references open their observations. TECHNICIAN_REPORTED includes
the reported answer, question, attribution, time and conflict references.
The evidence-ID lookup requests details only; it never creates an evidence ID.
The two pinned invalid/foreign IDs show their actual API errors without retaining
old detail data. No request re-queries Oracle or computes a measurement here.

**Load handover** GETs `/api/v1/cases/{case_id}/handover`. The view uses actual
B2 fields: `observations`, `technician_reports`, `assessment.unknowns`, unverified
`assessment.hypotheses` and their `limitations`, `open_questions`, `gaps`,
`scope.coverage_warnings` and `next_action`. B2 has no top-level handover
`warnings` field; warning entries in `gaps` remain there, while the separately
loaded snapshot warnings remain labeled above. The P0 assessment must be
`UNDETERMINED`; a different label is rejected rather than rewritten. Returned
data is also available under **Exact SYNTHETIC handover data**. Observations,
reports, hypothesis references and next-action evidence all retain their IDs.

Changing/reopening the case clears evidence and handover state and aborts
in-flight detail requests. A new detail request clears its old data before
loading, and errors remain local to that panel. The original findings keep
their source retrieval timestamp; a failed detail call is never presented as a
fresh observation. No response fixture is used as a UI fallback.

### Preparing the existing post-answer handover fixture

In mock mode, the pinned server supplies **only a post-answer handover**. A pre-answer request
honestly shows the existing HTTP 501 replay-limit error; no report or earlier
handover is fabricated. After opening the case in the dashboard, this optional
local test setup sends the exact existing B2 answer fixture through Vite:

```bash
node --input-type=module <<'JS'
import { readFileSync } from 'node:fs';
const fixtures = JSON.parse(readFileSync('mock/b2/examples.json', 'utf8'));
const fixture = fixtures.cases.find(item => item.name === 'record_answer');
const response = await fetch(new URL(fixture.path, 'http://127.0.0.1:5173'), {
  method: fixture.method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(fixture.request.body),
});
console.log(`SYNTHETIC answer setup: HTTP ${response.status}`);
if (!response.ok) process.exitCode = 1;
JS
```

Run from `frontend/`, adjusting the port if Vite printed a different one. Then
select **Load handover** and inspect its report reference. This is explicit
synthetic test preparation, not a dashboard answer feature or technician claim.
Reopening the mock case resets its answer; repeat the setup if needed.

React requests must use relative `/api/v1/...` URLs without credentials. Vite
reads `TRACE_API_KEY` only in Node and overwrites `X-API-Key` on every proxied
request, including a browser-supplied header. `TRACE_API_TARGET` selects the
backend without rewriting `/api/v1`. The B2 example's fallback target remains
`http://127.0.0.1:8000`; explicitly select port 8001 for this mock. Use only a
trusted HTTPS endpoint if switching to a remote backend. This is a development
proxy; `vite preview`/the static build do not provide an API proxy.

Never put a secret in `VITE_*`, React imports, Vite `define`/`envPrefix`, browser
storage, fixtures or response bodies. No API key is bundled into the dashboard.

## Replay inputs and limits

Use `mock/b2/examples.json` as the request source:

1. `open_case`: POST its exact `request.body` to `/api/v1/cases`. This starts or
   resets the single SYNTHETIC fixture case; it is not a multi-case store.
2. `get_evidence_1` through `_6`: GET the fixture paths. GET parameters belong
   in path/query, never an HTTP body.
3. `record_answer`: POST its exact `request.body` to its fixture path. The
   returned `data` is the updated snapshot directly, including
   `report_evidence_id` and `change_summary`; there is no `data.snapshot`.
   Repeating an answer or using a stale question returns the pinned 409 fixture.
4. `get_evidence_7` and `get_handover`: GET their paths after the answer. B2
   supplies only post-answer report/handover fixtures, so no earlier variant is
   fabricated.
5. `list_stations`: GET `/api/v1/stations?q=SYNTHETIC&limit=20`. The fixture is
   also available with either parameter omitted (B2's default limit is 20).
   Its envelope has `case_id: null`.

All five successes use HTTP 200. Missing/wrong keys sent directly to the mock
receive the exact 401 `UNAUTHORIZED` envelope. The two supplied evidence error
paths are GET routes returning their pinned 404 responses. The supplied unknown
case handover path also returns its pinned 404. Malformed JSON returns the pinned
422 `INVALID_SCOPE` response.

To replay a source error on its documented route, restart only the mock with
`TRACE_MOCK_SCENARIO=error_SOURCE_UNAVAILABLE npm run mock`. Similarly select
`error_NO_DATA`, `error_TIMEOUT`, `error_INVALID_SCOPE`, or another pinned P0
error name. This is a local test-harness setting, not a new B2 request field,
header or production API behavior. Authentication still runs first. An error
always has `data: null`; no measurement fallback is supplied.

Unconfigured bodies, query variants, methods, IDs and pre-answer handovers return
HTTP 501 with a plain-text SYNTHETIC replay-limit notice, **not a B2 envelope**.
This is a harness limitation, not a proposed backend status/error code. General
scope searching, arbitrary answers, new cases/IDs, clock/expiry behavior and full
request validation await the real backend. No P1 comparison route is enabled.

`parsed_value` and `deviation` stay strings or null. Computed Decimal strings
may use scientific notation; this does not relax Oracle raw-input parsing.
Code `1001` and null have unknown semantics and never establish PASS/FAIL.

## Validation

```bash
npm run build
npm run test:mock
npm run test:dashboard
node --test scripts/transport.test.mjs
node --test scripts/live-mode.test.mjs
```

The smoke test invokes `npm run build` with a random server-only key, starts an
actual loopback mock and Vite dev server, and compares HTTP responses with the
pinned fixtures. It checks all five successes through the proxy, all seven
evidence snapshots, 401 for missing/wrong keys on every operation, header
overwrite, corrected evidence GET errors, stale/repeated answers, error HTTP
codes, Decimal string/null rules and scientific notation in the pinned schema.
It searches React sources, served app content and `dist/` for the random key.
The servers are closed after testing. No new packages are required.

`test:dashboard` uses the installed Firefox in headless mode with an isolated
ignored profile under `node_modules/.cache/`, plus Node's built-in WebSocket.
It starts the actual mock and Vite servers, selects the station and opens the
case in the browser, compares every displayed value with the pinned fixture,
checks independent code/status/flags and warnings, then exercises NO_DATA,
SOURCE_UNAVAILABLE, TIMEOUT, INVALID_SCOPE and station-list 401 errors. It also
checks all four status labels and exact whitespace/scientific-notation rendering
with render-only synthetic inputs, without changing any API fixtures. No
additional test dependency is installed. Firefox must be available on PATH.

The same command also runs focused D3 browser tests: all six finding references
and the report resolve to the exact pinned evidence data; calculation inputs
resolve; unknown/foreign IDs display their GET errors; pre-answer handover shows
the replay limit; an explicit test-only answer prepares the exact B2 handover.
The handover payload, unknowns, limitations, warnings/gaps and next action are
checked, as are removal of stale data on refresh errors, case reset and delayed
requests. The shared Firefox helper is in `scripts/browser.mjs`. The mock suite
continues to check pinned file hashes and absence of the random server key in
React sources and the production bundle.

The separate `live-mode.test.mjs` uses only an ephemeral local protocol stub and
unchanged synthetic example payloads; it does not contact FastAPI or Oracle.
It checks unmarked B2 success responses, the reported station-adapter error,
live labels and scope, stale-data cleanup, malformed/transport failures,
mock-marker rejection, and server-key absence in a live-mode build. These are
frontend compatibility tests, never evidence of successful live integration.
For the existing mock/dashboard/transport suites, use `VITE_TRACE_API_MODE=mock`
(or leave it unset with no local mode override).

### D4 execution record — 2026-11-10

| Command from frontend/ | Actual result |
| --- | --- |
| `npm run build` | PASSED; TypeScript and Vite build |
| `VITE_TRACE_API_MODE=mock npm run test:mock` | PASSED; one suite test, pinned hashes/auth/proxy and bundle key checks |
| `VITE_TRACE_API_MODE=mock npm run test:dashboard` | PASSED; both D2/D3 browser tests |
| `VITE_TRACE_API_MODE=mock node --test scripts/transport.test.mjs` | PASSED; 41 leaf scenarios, 42 TAP tests including the parent |
| `node --test scripts/live-mode.test.mjs` | PASSED; nine subtests, ten TAP tests including the parent; also builds in live mode and checks for key leakage |

The initial D4 test attempts were blocked by sandbox loopback permissions and
an occupied port 5173. Test runs subsequently used local-server/browser
permission and available ports. The four existing test files change only
`strictPort` to allow Vite to select a free port; their assertions are unchanged.
An existing development process was not stopped. Deliberate invalid-mode and
socket-reset checks print expected configuration/proxy errors.

All successful runs above are local frontend/protocol tests. No real FastAPI,
Oracle or Copilot call was executed in this D4 change. Live measurement/evidence
acceptance, source-side failures and gate verification remain **PENDING**.

Remaining dependencies: final B2 freeze and A/C confirmations, open D12 scope and
configuration details, B's authenticated backend and A's Oracle/analysis modules.
These local synthetic checks do not verify Oracle, Copilot, integration gates or
production deployment. D2/D3 are implemented against the pinned candidate only;
D4 live transport/error display is supported; successful live measurements and
evidence remain pending, and P1 stays outside this change. Future work must
follow the agreed contract when the team freezes B2.
