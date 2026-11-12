# Integration plan — one MAGNA TRACE system (draft, 2026-11-11)

> Prepared by student C before the remaining team files arrive. Read-only survey; nothing in A/B/D code has been changed.

## 1. Inventory

| Source | What it is | Live Oracle data? | Verified |
| --- | --- | --- | --- |
| `main` · `backend/app/oracle_repo.py` (A) | `count_measurements()` only; typed `SourceUnavailableError` / `OracleTimeoutError` | Count only | A's tests (`tests/test_oracle_repo.py`) |
| `main` · `backend/app/schemas.py` + `contracts/b2/` (B2) | The REST contract: strict Pydantic models, JSON Schema, 21 synthetic examples, validator | — | `contracts/b2/validate.py` |
| `main` · `student_b/` (B) | FastAPI implementing B2: cases, evidence, answers, handover, stations; `DataSource` protocol | **No** — `fetch_measurements` / `list_stations` return `SOURCE_UNAVAILABLE` ("A2/A3 not started") | 36 tests, synthetic source |
| `feature/nikita` (D), **not merged** | React + Vite frontend on B2 (mock and live mode), QA checklist, expected values, demo backup plan, pitch | Live checks only for `/healthz`, `/readyz`, echo | Frontend tests; D5: 3 passed, 2 pending (waiting for A2/A3) |
| `main` · `student_c/` (C) | Own backend with live Oracle queries, Decimal evaluation, evidence, cases, handover; MCP `/mcp`; interim chat agent | **Yes** (all 23 stations, 1524 rows) | 51 tests; full agent journey |

## 2. Key findings

1. **B left exactly the hole C fills.** `student_b/source.py` is the A/B boundary: B writes no SQL and no arithmetic; it expects a `DataSource` with `count_measurements()`, `fetch_measurements(scope, limit) -> Batch[AnalyzedRow]` and `list_stations(q, limit)`. C already has the SQL (`oracle_repo.measurements_for_station`, `list_stations`) and the evaluation (`measurements.evaluate`).
2. **C's REST does not match B2.** Validation of live C responses against B2 models: only the error envelope is valid; open_case 66 errors, record_answer 42, handover 64, stations 92 (ID formats, field names, `parsed_value`, string fail code, answer snapshot shape, evidence `classification`).
3. **D's frontend speaks B2.** It needs B's API with real data, not C's REST.
4. **C's agent layer is independent of REST shape.** The MCP server and the interim chat only need service functions to call and texts to show.

## 3. Recommended target architecture

```
React (D) ──Vite proxy, X-API-Key──┐
                                   ├─► FastAPI of B  (/api/v1, contract B2)
Agent (C): chat ↔ MCP /mcp ────────┘        │
                                            ▼
                               DataSource = C adapter
                     (C's fixed SELECTs + Decimal evaluation, TRACE_RO)
                                            ▼
                                   Oracle FREEPDB1 / HACKATON
```

- **One REST backend: B's**, because the contract and the frontend are built on it.
- **Data: C's adapter implementing B's `DataSource`** (using A's error types and count function where they fit).
- **Agent: C's MCP server mounted on B's app**, tools calling B's service layer; ready-made texts rendered from B2 objects in the MCP layer (REST stays pure B2).
- **C's own REST, cases and evidence are retired** after the switch; `student_c/` stays runnable until then as the demo fallback.

## 4. Steps

| # | Step | Touches | Done when |
| --- | --- | --- | --- |
| 1 | Branch `integration/all` from `main`; merge `feature/nikita` (D) | D's files only | Frontend tests pass on the branch |
| 2 | C adapter: `fetch_measurements` → `Batch` of `AnalyzedRow` (`RawFields` upper-case names, string fail code, `row_ordinal`, `CalculationResult` with `parsed_value`, deviation `"0"` inside bounds as B2 requires); `list_stations` → `Stations` (`record_count`) | new module, e.g. `backend/app/measurement_source.py` | Unit tests + live ST3003 values match the D5 expected values |
| 3 | Select the adapter in B's production source factory | `student_b/source.py` (**B's file**) | B's 36 tests pass; live `open_case ST3003` validates against B2 |
| 4 | MCP on B's app: five tools → B's handlers; renderers for B2 snapshot / evidence / answer / handover | C's MCP module | MCP tool list + live calls return B2 data plus a ready text |
| 4b | **Web chat** (decided 2026-11-11: the technician interface is a web page, not GitHub Copilot or a terminal): move the harness loop server-side as `POST /api/v1/chat` (model choice, pinned routes, rate-limit wait, ready-text relay, conversation per case); add a chat panel to D's React app next to the dashboard, calling it through the existing Vite proxy; model and API keys stay server-side | new chat module in the backend; D's frontend (chat panel) | A browser conversation runs the full journey; the dashboard shows the same case |
| 5 | Agent instructions and harness re-checked against B's semantics (`next_action.kind` lowercase, answer request has no `answer_kind`) | `copilot/`, `harness/` (C) | Full journey: case → evidence → autonomous `record_answer` → handover, no waits |
| 6 | Frontend in live mode against the integrated API | — | Station list, case, evidence, handover visible with real data |
| 7 | One README at the root, one requirements file, one test command; merge decision logs | docs | Fresh start from README works |
| 8 | PR `integration/all` → `main` | — | Team review |

## 5. Decisions needed

1. **Architecture:** B's REST core + C's data adapter + C's MCP (recommended), or reshape C's backend to B2 and drop B's code (more work, discards B's tested API).
2. **Ownership:** step 3 changes one line area in B's `source.py`; step 2 may live in A's area. Ask A and B, or agree that the integrator does it.
3. **Behaviour after an answer:** B2 has no `answer_kind`; the next step after `record_answer` follows B's logic. Accept, or extend B2 (contract change, needs B and D).
4. **Demo fallback:** keep `student_c/` working unchanged until the integrated system passes the full journey twice.

## 6. Risks

- Time before the presentation; the integrated path must be rehearsed again.
- Agent behaviour was tuned on C's texts; renderers for B2 objects must keep the same guarantees (no recomputed values, IDs exact, `listed_because`-style wording).
- B2 deviation `"0"` inside bounds differs from C (`null`): follow B2 in the integrated system.
