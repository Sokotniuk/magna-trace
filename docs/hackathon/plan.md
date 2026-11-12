# MAGNA TRACE — Delivery Plan v1.0

> **Status:** FINAL / APPROVED — team development baseline. Inputs are `docs/product.md` v1.0 and `docs/architecture.md` v1.1.
> **Team:** four students, 24 hours. Hour fields are nonbinding estimates. Dependencies, gates and each task's acceptance criteria govern execution.
> **P0:** run the live Copilot → backend → Oracle journey twice, including clarification, recorded answer, evidence and a concise evidence-backed handover from the active case. Persistent history and richer reports/exports are P1.

## 1. Roles

| Student | Area | Owns (files) | Backs up |
| --- | --- | --- | --- |
| **A** | Data & analysis | `oracle_repo.py`, `measurements.py`, `comparisons.py`, `docs/data-baseline.sql` | B |
| **B** | Backend & cases | `main.py`, `api.py`, `schemas.py`, `evidence.py`, `cases.py`, `diagnostics.py` | A |
| **C** | Copilot & integration | `copilot/` (instructions, `openapi.v2.json`, setup), tunnel, auth | D |
| **D** | Dashboard & verification | `frontend/`, `tests/` E2E checklist, `README.md`, pitch | C |

Each student has **19 h of own tasks + 3 h shared** (syncs, two rehearsals, pitch) and 2 h of buffer and breaks. Unit tests are written by the module owner; D verifies independently.

## 2. Timeline and gates

| Phase | Hours | Goal | Exit |
| --- | --- | --- | --- |
| 0. Setup | H+0–2 | Environment, access, **contract freeze** (B2) | Everyone can run Oracle and backend; mock JSON published |
| 1. Proofs | H+2–6 | Copilot reaches backend; data baseline verified | **G0** (C) — hard decision point at H+6 |
| 2. Core | H+6–10 | Real queries, numeric rules, evidence, cases | **G1** (A, D checks) |
| 3. Journey | H+10–16 | Full dialogue in real Copilot chat | **G2** (all) |
| 4. Hardening | H+16–21 | Negative paths, two rehearsals, extensions that are ready | **G3** (D leads) |
| 5. Freeze | H+21–24 | No new features; pitch, backup recording, final run | Demo |

**Sync:** 10 minutes every 3 hours (H+3, 6, 9, …): gate status, blockers, who needs what. Decisions go to `docs/decisions.md` at once.

## 3. Tasks

### Student A — Data & analysis (19 h)

| ID | Task | h | Window | Done when |
| --- | --- | ---: | --- | --- |
| A1 | Oracle container up; SELECT-only user; **one minimal read-only query function** (`COUNT(*)` of measurements) handed to B first; then `data-baseline.sql` (`COUNT(*)` all four tables, distinct stations/serials, units, raw codes, row uniqueness) | 2 | H+0–2 | B has the query by H+2; baseline reruns cleanly |
| A2 | `oracle_repo.py`: fixed parameterized SELECTs (stations; measurements by station/time/serial), row limit, timeout, deterministic order | 3 | H+2–5 | B calls it; no string-built SQL |
| A3 | `measurements.py`: preserve raw inputs; parse Decimal; compute range, quality flags and raw code independently | 4 | H+5–9 | Hand arithmetic and fixtures cover equality, missing/invalid inputs, partial/reversed bounds, raw `1001` and null |
| A4 | Pick demo station; verify ≥ 3 abnormal observations and the in-range coded row independently; hand safe fixtures to B/C/D | 2 | H+3–9 | Reproducible SQL and permitted scope references recorded; exports stay local |
| A5 | Verify join keys (serial, station, work order), units, timestamp meaning | 2 | H+9–11 | Each key marked verified or disabled |
| A6 | Failure paths: Oracle down, timeout, empty result | 1 | H+11–12 | Correct error codes, no fallback data |
| A7 | Conditional `comparisons.py` for both modes under architecture §7. Requires A2–A6, G1 and stable P0 including A8. | 4 | H+12–18 | Both modes checked for allowed and refused comparisons, counts, coverage, warnings and specific `NOT_COMPARABLE` reasons |
| A8 | P0 integration support for B; verify A-owned fixes with D | 1 | H+18–21 | B consumes A2/A3/A6 outputs; D checks independent expectations on the integrated revision |

**A dependency order.** A1 → A2 → A3 → A4 → A5 → A6 → A8. A7 follows only if its gates hold. D5 independently checks each deliverable.

**A3 contract.** Null, empty and whitespace-only numeric input → `MISSING`; invalid nonempty input → `UNPARSEABLE`. An invalid value or unusable interval gives `NOT_EVALUABLE`; two absent bounds give `LIMIT_UNKNOWN`, malformed/reversed bounds give `LIMIT_INVALID`, and one valid bound with the other missing permits a flagged one-sided check (`PARTIAL_BOUNDS`). Preserve the raw fail code and flag `SEMANTICS_UNKNOWN` for undocumented codes including null; the numeric status is independent.

**A7 contract.** `same_station_across_serials` holds station fixed and counts distinct comparable serials. `same_serial_across_stations` holds serial fixed and counts distinct comparable stations. Require two entities on that dimension, warn `LOW_SAMPLE` at exactly two, and clear the warning at three. Return row count, distinct serials, distinct stations and time coverage. Apply verified keys, matching measurement, compatible recorded units, Decimal-equal bounds, compatible test/product semantics and parseable values; refuse each failed criterion explicitly.

### Student B — Backend & cases (19 h)

| ID | Task | h | Window | Done when |
| --- | --- | ---: | --- | --- |
| B1 | FastAPI skeleton: envelope, `request_id`, API-key dependency, `/healthz`, `/readyz`, `health/echo`; by H+4 `health/echo` also returns A's live Oracle `COUNT(*)` | 2 | H+0–4 | C can tunnel `health/echo` (H+2) and gets an Oracle value (H+4) |
| B2 | `schemas.py` **contract freeze** + example JSON for every tool and error | 2 | H+1–3 | Published to C (spec) and D (mock server) |
| B3 | `evidence.py`: captured snapshots, `E-<case>-<n>` IDs, foreign/unknown ID rejection | 3 | H+3–7 | Evidence never re-queried or replaced |
| B4 | `cases.py`: in-memory store, states, expiry, per-case lock; unknown, expired or pre-restart IDs all return `CASE_NOT_FOUND_OR_EXPIRED` | 3 | H+7–10 | Two cases do not share answers; one code in API, tests and docs |
| B5 | `diagnostics.py`: snapshot (max 5 findings), hypotheses, `UNDETERMINED`, question and next-action candidates | 3 | H+9–13 | One question with `question_id` per snapshot |
| B6 | Endpoints `open_case`, `get_evidence`, `record_answer`, `get_handover`, `list_stations`; error mapping | 3 | H+10–14 | All five answer on real data |
| B7 | API tests with mocked repository: isolation, error codes, answer never rewrites observations | 2 | H+14–16 | Tests green with independent expected values |
| B8 | `compare_case` wiring; integration fixes | 1 | H+17–21 | — |

### Student C — Copilot & integration (19 h)

| ID | Task | h | Window | Done when |
| --- | --- | ---: | --- | --- |
| C1 | Open the real Copilot Studio environment; record agent type and permissions; ask organizers about demo channel, tunnel and cloud-data rules | 2 | H+0–2 | Answers in `decisions.md` |
| C2 | Permitted HTTPS tunnel + API key: find how Copilot really sends it | 2 | H+2–4 | No key → `401`; agent call logged with header |
| C3 | Minimal Swagger 2.0 `openapi.v2.json` (echo); import; first agent call | 2 | H+3–5 | Request ID matches chat and log |
| C4 | Second call returning the live Oracle `COUNT(*)` via `health/echo` (needs only A1 + B1, not the full repository); record G0 evidence | 1 | H+5–6 | **G0 passed** or blocker escalated |
| C5 | Full `openapi.v2.json` for five tools; drift test against FastAPI spec | 3 | H+6–10 | Import succeeds; test fails on mismatch |
| C6 | `instructions.md`: behavior rules, multi-turn rule, tool descriptions incl. when not to call | 3 | H+9–13 | Agent cites evidence IDs, one question per turn |
| C7 | Multi-turn check: agent calls `record_answer` by itself on two differently worded replies; refusal tests (“what do I replace”, “ignore your rules”, “just estimate”) | 3 | H+13–17 | Backend log shows calls; refusals correct |
| C8 | `setup.md`, pre-demo check, latency vs. connector timeout | 2 | H+17–20 | Another student repeats setup from the doc |
| C9 | Integration fixes | 1 | H+20–21 | — |

### Student D — Dashboard & verification (19 h)

| ID | Task | h | Window | Done when |
| --- | --- | ---: | --- | --- |
| D1 | Vite + React + TS scaffold; mock server from B2 examples; dev proxy that adds the API key server-side | 2 | H+1–3 | UI runs without backend; no key in browser code |
| D2 | Station selector; findings table with range, quality and raw code shown separately | 3 | H+4–8 | In-range `1001` row displayed honestly |
| D3 | Evidence drill-down panel; case summary / handover view | 3 | H+8–11 | Every number opens its source |
| D4 | Switch to real API through dev proxy; comparison view later, only if A7 ships | 2 | H+14–16 | No logic duplicated in TypeScript |
| D5 | **Independent QA from the start:** test cases written together with B2 (scenario list, expected values from own SQL and hand arithmetic, ≥ 3 values and limits); run against each module the moment it lands | 3 | H+3–4, then H+9–10, H+13–14 | Cases shared by H+4; expected vs. shown table in `tests/` |
| D6 | Full E2E and negative runs: no data, Oracle down, invalid/foreign evidence ID, unknown case ID, secrets scan of repo | 2 | H+16–18 | Each scenario marked pass/fail with note |
| D7 | `README.md` (startup, actual features, limits); three-minute script; labelled backup recording | 3 | H+18–22 | Script timed; recording saved |
| D8 | Rehearsal lead: runs both full demonstrations, logs defects | 1 | H+19–22 | Two clean runs |

## 4. Hand-offs

| From → To | What | By |
| --- | --- | --- |
| B → C, D | Frozen contract + example JSON (B2) | H+3 |
| B → C | Tunnel-ready `health/echo` (B1) | H+2 |
| A → B → C | **Early Oracle path for G0:** one read-only query (A1) → `health/echo` with Oracle value (B1) → Copilot call (C4) | H+2 → H+4 → H+6 |
| D → A, B, C | Test cases and expected values (D5) | H+4 |
| A → B | Repository functions (A2), measurement results (A3) | H+5, H+9 |
| A → B, C, D | Permitted demo scope, reproducible SQL references and synthetic fixtures (A4) | H+9 |
| C → all | G0 result and auth mechanism (C4) | H+6 |
| B → C | Working five endpoints (B6) | H+14 |
| A → B, D | Conditional comparison module (A7), if shipped | H+18 |

After the B2 contract freeze, a public contract change requires agreement from B, C and D, a dated entry in `docs/decisions.md`, and corresponding spec and drift-test updates.

## 5. Gate checklist

| Gate | Owner | Checker | Proof |
| --- | --- | --- | --- |
| G0 | C | B | Two real authenticated agent calls, the second returning A1's live Oracle count; matching request IDs and `401` without key |
| G1 | A | D | Baseline SQL kept; ≥ 3 values match independent check; numeric tests green |
| G2 | B + C | D | Full journey in real chat; agent calls `record_answer` itself; label stays `UNDETERMINED` |
| G3 | D | A | Two clean runs; all negative scenarios; no secrets in repo |

## 6. Rules under pressure

- **G0 not passed at H+6:** C and B go to mentors immediately; D pauses the dashboard and helps C. No fallback UI is presented as meeting the Copilot requirement.
- **Dashboard never blocks P0:** D5, D6 and D8 take priority over D2–D4 whenever a gate is due. Dashboard requests for backend changes wait until G2.
- **Dashboard never holds the Copilot key:** not in React code, browser storage or any `VITE_`-prefixed variable (those are bundled into the client). Local demo goes through the dev proxy, which reads the key from a server-side variable. Public API routes keep full authentication; no CORS opening or auth exemption for the UI.
- **Comparison never delays the MVP.** Keep `compare_case` disabled unless A7 meets its prerequisites and its independently verified acceptance criteria.
- **Cut order:** RAG → comparison view in dashboard → comparison module → dashboard polish → `list_stations`. Never cut: correct numbers, evidence resolution, the live Copilot journey.
- **Feature freeze at H+21.** After that only blocker fixes, rehearsal and pitch.
- **Scope.** D develops the optional dashboard against the common contract in parallel. Comparison and richer reporting remain conditional. RAG requires approved manuals and permission to use them.

## 7. Git integration protocol

- **Branches:** one per student, `feature/<name>` (for example the existing `feature/vasyl`), cut from `main`. `main` must always start and pass tests.
- **Ownership:** each student edits only the files listed for them in §1. A change in someone else's module is requested from the owner or agreed with them first; nobody overwrites or reformats another owner's files.
- **Integrator:** **B** merges into `main`; **A** is backup. Nobody else pushes to `main`; no force-push, no history rewrite on shared branches.
- **Before a merge:** the author merges current `main` into their branch and resolves conflicts there; **D** runs the tests on the result and confirms; only then B merges. A conflict in another owner's file is resolved together with that owner.
- **Rhythm:** commit small and often; integrate at every sync (every 3 h) and before each gate. B tags `g0`, `g1`, `g2`, `g3` on `main` when a gate passes — a known-good point to return to.
- Use a full branch bundle when the receiver’s history is uncertain. For A, `git bundle create ../trace-student-a.bundle feature/student-a` includes reachable branch history. Use `main..feature/student-a` only after B confirms all prerequisite commits are present. B runs `git bundle verify <file>` in the receiving repository before `git fetch <file> feature/student-a:incoming/student-a`. Inspect outgoing history for secrets before authorized transfer.
- **Never in Git or a bundle:** credentials, API keys, tunnel tokens, `.env`, Oracle dumps, exported rows.

## 8. Open questions to close early

| Question | Owner | By |
| --- | --- | --- |
| Demo channel, tunnel vendor, fields allowed in the cloud | C | H+2 |
| Meaning of `1001`, units, timezone, bound equality | A | H+9 |
| Approved manuals or SOPs available? | D | H+6 |
| Presentation length and repository rules | D | H+6 |
