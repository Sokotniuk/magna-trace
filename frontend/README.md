# MAGNA TRACE frontend — D2

Local Vite dashboard and **SYNTHETIC ONLY** B2 fixture replay server.
D2 provides station selection, case opening and a findings table. Evidence
drill-down (D3), live backend integration (D4) and P1 features are not implemented.

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
npm run mock
```

In a second terminal, export the **same** `TRACE_API_KEY` and target, then:

```bash
npm run dev
```

Open the loopback URL Vite prints (normally `http://127.0.0.1:5173`). The mock
listens on `127.0.0.1:8001`; `TRACE_MOCK_PORT` can change its port. Update
`TRACE_API_TARGET` accordingly. Missing mock or Vite credentials fail startup.
The Vite configuration also supports server-only `.env.local` values; the mock
reads shell environment variables, so export the key for both processes.
`.env` and `.env.*` are ignored.

## D2 dashboard

The station selector loads `list_stations` through the Vite proxy. Choose
`SYNTHETIC-STATION`, then select **Open diagnostic case**. The request uses the
exact pinned replay scope shown on screen; `src/demo-scope.json` contains only
the request's from/to/serial fields, verified against the pinned fixture by the
UI test. No response fixtures are imported into React or used as error fallbacks.

The table displays measurement, raw value/unit/bounds, returned deviation, range
status, quality flags and raw fail code in separate columns. Plain evidence IDs
provide references only; no evidence fetch or drill-down is implemented. Raw
strings retain their precision/whitespace; null is visibly rendered as `null`.
ABOVE, BELOW, WITHIN_RECORDED_BOUNDS and NOT_EVALUABLE have distinct labels and
styling; they are never derived from values or codes. In particular the pinned
in-range Count row retains code `1001` without a pass/fail diagnosis.

Warnings and source retrieval time are displayed as returned. Changing the
station, reloading stations or opening another case clears prior findings.
Errors show the returned code/message and exact queried scope when supplied;
network, non-JSON and unexpected responses produce a technical error without
substitute findings. Loading disables duplicate submissions. D2 accepts only
responses labeled `X-Trace-Mock: SYNTHETIC`, so a live backend cannot silently be
presented as mock data. Live integration remains D4 work.

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

Remaining dependencies: final B2 freeze and A/C confirmations, open D12 scope and
configuration details, B's authenticated backend and A's Oracle/analysis modules.
These local synthetic checks do not verify Oracle, Copilot, integration gates or
production deployment. D2 is complete against the pinned candidate only; D3/D4
and P1 work remain outside this change. Future work must follow the agreed
contract when the team freezes B2.
