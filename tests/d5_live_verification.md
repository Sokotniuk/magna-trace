# D5 verification

Independent A4 verification is complete. **D5 VERIFIED and ACCEPTED.**
Full live API integration remains pending A2/A3.

## Completed independent A4 verification

Student D connected directly to Oracle `FREEPDB1` as `TRACE_D4_RO`.

| Check | Observed result | Status |
| --- | --- | --- |
| A4-01 | `ST3003` count was 60. | PASS |
| A4-02 | Coded Screw Count lookup succeeded. | PASS |
| Angle | 9 source fields matched. `ABOVE` 7.592. | PASS |
| Vibration | 9 source fields matched. `ABOVE` 0.354. | PASS |
| Position Accuracy | 9 source fields matched. `ABOVE` 0.292. | PASS |
| Screw Count | 9 source fields matched. `WITHIN_RECORDED_BOUNDS`, deviation 0. | PASS |

## Live FastAPI and Oracle smoke verification

Scope: the available B1 health, readiness and aggregate echo paths, missing-key
rejection, and the B2 station response through Vite. See [plan D5](../docs/plan.md),
[architecture §§2–4](../docs/architecture.md), and the
[pinned B2 candidate](../frontend/mock/b2/PINNED.json). This record is separate
from the [D5 measurement expectations](expected_values.md) and
[D6 synthetic test results](d6_execution_log.md).

## Automated run — 2026-11-10, 22:20 UTC

`feature/nikita`, base revision `1caa232`, clean worktree before the D5 changes.
Ran `python3 tests/d5_live_smoke.py` with Python 3.14.8 against loopback FastAPI
on port 8000 and the existing Vite listener on port 5173. Sandbox loopback access
required permission; no service was started, restarted or reconfigured for this
run. Exit code **2**: **3 PASSED, 0 FAILED, 2 PENDING**.

### PASSED — actual live backend checks

| Request | Observed result |
| --- | --- |
| Direct `GET /healthz` | HTTP 200, valid success envelope, null `case_id` and `error`. |
| Direct `GET /readyz` | HTTP 200, valid success envelope; backend reported Oracle reachable. |
| Direct `GET /api/v1/health/echo` without `X-API-Key` | HTTP 401 `UNAUTHORIZED`, valid error envelope, `data: null`; no diagnostic fields. |

### FAILED

None in this run. The checks below did not pass merely because the local Vite
listener returned an HTTP response.

### PENDING

| Request or evidence | Reason |
| --- | --- |
| Live proxy `GET /api/v1/health/echo` and current aggregate | Port 5173 returned HTTP 501 with a mock marker. The runner excluded it and did not read its body. No fresh live count was captured. |
| Live proxy `GET /api/v1/stations` | Port 5173 returned HTTP 200 with a mock marker. The runner excluded it and did not read its body. The reported live 503 and its error body were not rechecked. |
| Successful live station/case/evidence/handover and O01–O03 API comparisons | Wait for A2/A3 and B's integration; no Oracle rows or evidence IDs obtained. |
| Independent database count, controlled Oracle outage/timeout and Copilot journey | Outside this HTTP smoke run. Readiness is a backend report, not a direct SQL check or gate pass. |

## Student D's prior manual observations

Student D reported HTTP 200 for `/healthz` and `/readyz`, Oracle reachable, and
HTTP 401 `UNAUTHORIZED` without the key. In that earlier live Vite configuration,
echo returned HTTP 200 with `measurement_rows = 1524`; stations returned HTTP 503
`SOURCE_UNAVAILABLE` because the A2 station adapter was not connected. These are
prior manual observations, not the automated proxy results above. The count is
an observation, never a fixed test expectation. No original response bodies or
credentials are retained in this report.

## Rerun after a backend update

1. Keep the owner-configured local FastAPI and Oracle services running. Set up
   Vite as described in [frontend live mode](../frontend/README.md#explicit-live-mode),
   with the same FastAPI target and its key held only by the Node proxy. Use the
   port Vite actually prints. The runner needs no API key or Oracle password.
2. From the repository root, run:

   ```bash
   python3 tests/d5_live_smoke.py
   ```

   The defaults are FastAPI 8000 and Vite 5173. For other loopback ports, pass
   `--backend-port` and `--proxy-port`, for example:

   ```bash
   python3 tests/d5_live_smoke.py --backend-port 8000 --proxy-port 5174
   ```

3. Record a new dated result with the backend revision if known. A valid HTTP
   503 `SOURCE_UNAVAILABLE` or HTTP 504 `TIMEOUT` with `data: null` validates the
   error response while leaving the operation **PENDING**. When A2 is connected,
   a valid HTTP 200 station list can pass without changing the runner. Echo
   requires a nonnegative integer aggregate and prints only that count.

The runner uses only Python standard libraries, fixed loopback GET routes,
bounded response reads and a socket timeout. It does not follow redirects, read
credential files or environment variables, connect to Oracle, require Docker or
write files. It checks envelope fields, UTC retrieval time, status and payload
shape. Structured error data and unexpected fields are rejected; response text,
station identities and IDs are withheld. A marked mock or unreachable service
is **PENDING**; an unexpected unmarked response is **FAILED**. Exit codes: **0**
all pass, **1** any failed check, **2** pending with no failed check.

Offline validator checks also passed with synthetic inputs: rejection of
diagnostic data in errors and malformed metadata, 503 classified as pending,
valid station success, varying aggregate counts, and missing-key status
validation. Those checks do not count as live results. The runner's help and
`git diff --check` were also checked. No dependencies, service changes,
commits or pushes were made.

## Live smoke run with a proxy credential mismatch

Student D observed **PASSED=3, FAILED=2, PENDING=0** while the Vite proxy's
server-side API key did not match FastAPI's configured key. Both proxied
requests, `GET /api/v1/health/echo` and `GET /api/v1/stations`, returned HTTP 401.
FastAPI health, Oracle readiness and direct missing-key rejection passed.

The two failures came from the proxy's authentication configuration. The
requests were rejected before they could check Oracle-backed operations, and
the separate Oracle readiness check still passed.

## Live smoke rerun — 2026-11-10

Student D reran the smoke test after restoring the matching server-side API key
in the Vite proxy.

Executed: `python3 tests/d5_live_smoke.py`

- PASSED: FastAPI health — HTTP 200.
- PASSED: Oracle readiness — HTTP 200.
- PASSED: Missing API key — HTTP 401.
- PASSED: Vite proxy echo — HTTP 200, measurement_rows=1524.
- PENDING: Stations — HTTP 503 SOURCE_UNAVAILABLE; A2 adapter not connected.
- FAILED: None.

Summary: PASSED=4, FAILED=0, PENDING=1.

The corrected run verified the live Oracle aggregate. The stations endpoint
remained blocked by A2. Full live API integration, including station discovery,
measurement analysis and evidence, remains pending A2/A3.
