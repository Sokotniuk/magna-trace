# MAGNA TRACE — Delivery Plan v1.0

> **Inputs:** `docs/product.md` v1.4 FINAL (what) · `docs/architecture.md` v1.1 (how). This file says **who does what, in which order**.
> **Team:** four students, 24 hours. Replace A–D with names. Times are hours from the start (**H+0**) and are targets, not guarantees.
> **Rule:** P0 = one live journey Copilot → backend → Oracle → clarification → evidence → handover, run twice. Nothing else outranks it.

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
| A1 | Oracle container up; SELECT-only user; `data-baseline.sql` (`COUNT(*)` all four tables, distinct stations/serials, units, raw codes, row uniqueness) | 2 | H+0–2 | Queries rerun cleanly; results noted |
| A2 | `oracle_repo.py`: fixed parameterized SELECTs (stations; measurements by station/time/serial), row limit, timeout, deterministic order | 3 | H+2–5 | B calls it; no string-built SQL |
| A3 | `measurements.py`: `Decimal` parsing, bounds, quality flags, deviation, three independent statuses + pytest | 4 | H+5–9 | Tests cover equality, blank, malformed, reversed/missing limits, `1001`, `NULL` |
| A4 | Pick demo station; confirm ≥ 3 values and the in-range `1001` row; hand fixtures to B, C, D | 2 | H+3–9 | Station and rows recorded in `decisions.md` |
| A5 | Verify join keys (serial, station, work order), units, timestamp meaning | 2 | H+9–11 | Each key marked verified or disabled |
| A6 | `comparisons.py`: two modes, six criteria, `NOT_COMPARABLE` reasons + tests (**only after G1**) | 4 | H+11–17 | Fixture for allowed and refused comparison |
| A7 | Failure paths: Oracle down, timeout, empty result | 1 | H+17–18 | Correct error codes, no fallback data |
| A8 | Integration fixes | 1 | H+18–21 | — |

### Student B — Backend & cases (19 h)

| ID | Task | h | Window | Done when |
| --- | --- | ---: | --- | --- |
| B1 | FastAPI skeleton: envelope, `request_id`, API-key dependency, `/healthz`, `/readyz`, `health/echo` | 2 | H+0–2 | C can tunnel `health/echo` |
| B2 | `schemas.py` **contract freeze** + example JSON for every tool and error | 2 | H+1–3 | Published to C (spec) and D (mock server) |
| B3 | `evidence.py`: captured snapshots, `E-<case>-<n>` IDs, foreign/unknown ID rejection | 3 | H+3–7 | Evidence never re-queried or replaced |
| B4 | `cases.py`: in-memory store, states, expiry, per-case lock, `CASE_EXPIRED` | 3 | H+7–10 | Two cases do not share answers |
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
| C4 | Second call with a live Oracle-derived value; record G0 evidence | 1 | H+5–6 | **G0 passed** or blocker escalated |
| C5 | Full `openapi.v2.json` for five tools; drift test against FastAPI spec | 3 | H+6–10 | Import succeeds; test fails on mismatch |
| C6 | `instructions.md`: behavior rules, multi-turn rule, tool descriptions incl. when not to call | 3 | H+9–13 | Agent cites evidence IDs, one question per turn |
| C7 | Multi-turn check: agent calls `record_answer` by itself on two differently worded replies; refusal tests (“what do I replace”, “ignore your rules”, “just estimate”) | 3 | H+13–17 | Backend log shows calls; refusals correct |
| C8 | `setup.md`, pre-demo check, latency vs. connector timeout | 2 | H+17–20 | Another student repeats setup from the doc |
| C9 | Integration fixes | 1 | H+20–21 | — |

### Student D — Dashboard & verification (19 h)

| ID | Task | h | Window | Done when |
| --- | --- | ---: | --- | --- |
| D1 | Vite + React + TS scaffold; mock server from B2 examples | 2 | H+1–4 | UI runs without backend |
| D2 | Station selector; findings table with range, quality and raw code shown separately | 3 | H+4–8 | In-range `1001` row displayed honestly |
| D3 | Evidence drill-down panel; case summary / handover view | 3 | H+8–11 | Every number opens its source |
| D4 | Switch to real API through dev proxy; comparison view if A6 is ready | 2 | H+14–16 | No logic duplicated in TypeScript |
| D5 | **Independent SQL spot-check** of ≥ 3 values and limits; deviations recomputed by hand | 2 | H+9–10, H+13–14 | Table of expected vs. shown in `tests/` |
| D6 | E2E checklist and negative runs: no data, Oracle down, invalid/foreign evidence ID, secrets scan of repo | 3 | H+16–19 | Each scenario marked pass/fail with note |
| D7 | `README.md` (startup, actual features, limits); three-minute script; labelled backup recording | 3 | H+18–22 | Script timed; recording saved |
| D8 | Rehearsal lead: runs both full demonstrations, logs defects | 1 | H+19–22 | Two clean runs |

## 4. Hand-offs

| From → To | What | By |
| --- | --- | --- |
| B → C, D | Frozen contract + example JSON (B2) | H+3 |
| B → C | Tunnel-ready `health/echo` (B1) | H+2 |
| A → B | Repository functions (A2), measurement results (A3) | H+5, H+9 |
| A → B, C, D | Demo station and verified rows (A4) | H+9 |
| C → all | G0 result and auth mechanism (C4) | H+6 |
| B → C | Working five endpoints (B6) | H+14 |
| A → B, D | Comparison module (A6) | H+17 |

A contract change after H+3 needs agreement from B, C and D and a line in `decisions.md`.

## 5. Gate checklist

| Gate | Owner | Checker | Proof |
| --- | --- | --- | --- |
| G0 | C | B | Two real agent calls, matching request IDs; `401` without key |
| G1 | A | D | Baseline SQL kept; ≥ 3 values match independent check; numeric tests green |
| G2 | B + C | D | Full journey in real chat; agent calls `record_answer` itself; label stays `UNDETERMINED` |
| G3 | D | A | Two clean runs; all negative scenarios; no secrets in repo |

## 6. Rules under pressure

- **G0 not passed at H+6:** C and B go to mentors immediately; D pauses the dashboard and helps C. No fallback UI is presented as meeting the Copilot requirement.
- **Dashboard never blocks P0:** D5, D6 and D8 take priority over D2–D4 whenever a gate is due. Dashboard requests for backend changes wait until G2.
- **Comparison starts only after G1** and ships only if its tests pass by H+17; otherwise `compare_case` stays disabled.
- **Cut order:** RAG → comparison view in dashboard → comparison module → dashboard polish → `list_stations`. Never cut: correct numbers, evidence resolution, the live Copilot journey.
- **Feature freeze at H+21.** After that only blocker fixes, rehearsal and pitch.
- **Scope note:** product v1.4 lists comparison and dashboard after P0. This plan runs them as a side track (D) and a post-G1 task (A) by team choice; neither counts toward P0 acceptance.

## 7. Open questions to close early

| Question | Owner | By |
| --- | --- | --- |
| Demo channel, tunnel vendor, fields allowed in the cloud | C | H+2 |
| Meaning of `1001`, units, timezone, bound equality | A | H+9 |
| Approved manuals or SOPs available? | D | H+6 |
| Presentation length and repository rules | D | H+6 |
